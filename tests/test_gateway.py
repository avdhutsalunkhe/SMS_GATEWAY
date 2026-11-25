import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import DESCENDING, ReturnDocument
import pytest
from starlette.websockets import WebSocketDisconnect

import database
import main


class InsertOneResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched_count: int, modified_count: int) -> None:
        self.matched_count = matched_count
        self.modified_count = modified_count


def _match_filter(doc: dict[str, Any], flt: dict[str, Any]) -> bool:
    for key, expected in flt.items():
        val = doc.get(key)
        if isinstance(expected, dict):
            for op, target in expected.items():
                if op == "$lt" and not (val < target):
                    return False
                if op == "$gte" and not (val >= target):
                    return False
        else:
            if val != expected:
                return False
    return True


def _apply_update(doc: dict[str, Any], update: dict[str, Any]) -> None:
    if "$set" in update:
        for k, v in update["$set"].items():
            doc[k] = v
    if "$inc" in update:
        for k, v in update["$inc"].items():
            doc[k] = doc.get(k, 0) + v


class FakeAsyncCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, key_or_list: list[tuple[str, int]]) -> "FakeAsyncCursor":
        for field, direction in reversed(key_or_list):
            self._docs.sort(
                key=lambda d: d.get(field),
                reverse=(direction == DESCENDING),
            )
        return self

    def limit(self, count: int) -> "FakeAsyncCursor":
        self._docs = self._docs[:count]
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        if length is None:
            return [deepcopy(d) for d in self._docs]
        return [deepcopy(d) for d in self._docs[:length]]


class FakeAsyncCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def create_index(self, *_args: Any, **_kwargs: Any) -> str:
        return "ok"

    async def count_documents(self, flt: dict[str, Any]) -> int:
        return sum(1 for d in self.docs if _match_filter(d, flt))

    async def insert_one(self, doc: dict[str, Any]) -> InsertOneResult:
        stored = deepcopy(doc)
        stored.setdefault("_id", ObjectId())
        self.docs.append(stored)
        return InsertOneResult(stored["_id"])

    async def find_one(self, flt: dict[str, Any]) -> dict[str, Any] | None:
        for d in self.docs:
            if _match_filter(d, flt):
                return deepcopy(d)
        return None

    def find(self, flt: dict[str, Any]) -> FakeAsyncCursor:
        matched = [deepcopy(d) for d in self.docs if _match_filter(d, flt)]
        return FakeAsyncCursor(matched)

    async def find_one_and_update(
        self,
        flt: dict[str, Any],
        update: dict[str, Any],
        sort: list[tuple[str, int]] | None = None,
        return_document: Any = ReturnDocument.AFTER,
    ) -> dict[str, Any] | None:
        matches = [d for d in self.docs if _match_filter(d, flt)]
        if not matches:
            return None
        if sort:
            for field, direction in reversed(sort):
                matches.sort(
                    key=lambda d: d.get(field),
                    reverse=(direction == DESCENDING),
                )
        target = matches[0]
        before = deepcopy(target)
        _apply_update(target, update)
        return deepcopy(target) if return_document == ReturnDocument.AFTER else before

    async def update_one(self, flt: dict[str, Any], update: dict[str, Any]) -> UpdateResult:
        for d in self.docs:
            if _match_filter(d, flt):
                _apply_update(d, update)
                return UpdateResult(1, 1)
        return UpdateResult(0, 0)

    async def update_many(self, flt: dict[str, Any], update: dict[str, Any]) -> UpdateResult:
        matched = 0
        for d in self.docs:
            if _match_filter(d, flt):
                _apply_update(d, update)
                matched += 1
        return UpdateResult(matched, matched)

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> FakeAsyncCursor:
        counts: dict[str, int] = {}
        for d in self.docs:
            status_val = d.get("status")
            counts[status_val] = counts.get(status_val, 0) + 1
        rows = [{"_id": k, "count": v} for k, v in counts.items()]
        return FakeAsyncCursor(rows)


class FakeAdmin:
    async def command(self, name: str) -> dict[str, Any]:
        return {"ok": 1}


class FakeAsyncMongoClient:
    def __init__(self) -> None:
        self.admin = FakeAdmin()

    async def close(self) -> None:
        pass


class FakeDatabase(database.Database):
    def __init__(self) -> None:
        super().__init__()
        self._projects = FakeAsyncCollection()
        self._sms_queue = FakeAsyncCollection()

    @property
    def projects(self) -> FakeAsyncCollection:  # type: ignore[override]
        return self._projects

    @property
    def sms_queue(self) -> FakeAsyncCollection:  # type: ignore[override]
        return self._sms_queue

    async def connect(self) -> None:
        self.client = FakeAsyncMongoClient()  # type: ignore[assignment]
        await self.ensure_indexes()
        await self.ensure_default_project()

    async def close(self) -> None:
        self.client = None


@pytest.fixture()
def gateway_env(monkeypatch: pytest.MonkeyPatch):
    fake_db = FakeDatabase()
    monkeypatch.setattr(database, "db", fake_db)
    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setattr(database.settings, "device_secret", "test-device-secret")
    monkeypatch.setattr(database.settings, "send_delay_seconds", 0.05)
    monkeypatch.setattr(database.settings, "worker_poll_interval_seconds", 0.05)
    monkeypatch.setattr(database.settings, "admin_api_key", "")
    main.device_manager = main.DeviceConnectionManager()
    return fake_db


def test_default_project_seeded_and_projects_crud(gateway_env: FakeDatabase) -> None:
    with TestClient(main.app) as client:
        res = client.get("/api/v1/admin/projects")
        assert res.status_code == 200
        projects = res.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "Project 1"
        assert projects[0]["api_key"].startswith("sms_")
        assert projects[0]["is_active"] is True

        create_res = client.post(
            "/api/v1/admin/projects",
            json={"name": "Alerts App", "rate_limit_per_min": 120},
        )
        assert create_res.status_code == 201
        created = create_res.json()
        assert created["name"] == "Alerts App"
        assert created["rate_limit_per_min"] == 120
        assert created["api_key"] != projects[0]["api_key"]


def test_send_sms_validation_auth_rate_limit_and_status(gateway_env: FakeDatabase) -> None:
    with TestClient(main.app) as client:
        # Missing API key
        assert (
            client.post(
                "/api/v1/send-sms",
                json={"to": "+919876543210", "message": "Hello"},
            ).status_code
            == 401
        )

        # Create rate-limited project
        proj = client.post(
            "/api/v1/admin/projects",
            json={"name": "Limited", "rate_limit_per_min": 2},
        ).json()
        headers = {"X-API-Key": proj["api_key"]}

        # Invalid phone numbers rejected
        for bad_phone in ["9876543210", "+9112345", "+0123456789", "not-a-phone"]:
            r = client.post(
                "/api/v1/send-sms",
                headers=headers,
                json={"to": bad_phone, "message": "Test"},
            )
            assert r.status_code == 422

        # Valid +91 (with spaces normalized) and E.164 accepted
        r1 = client.post(
            "/api/v1/send-sms",
            headers=headers,
            json={"to": "+91 98765-43210", "message": "OTP 1234", "priority": 5},
        )
        assert r1.status_code == 201
        body1 = r1.json()
        assert body1["status"] == "pending"
        assert body1["device_online"] is False

        r2 = client.post(
            "/api/v1/send-sms",
            headers=headers,
            json={"to": "+14155552671", "message": "Hello US"},
        )
        assert r2.status_code == 201

        # 3rd request within 1 minute hits rate limit
        r3 = client.post(
            "/api/v1/send-sms",
            headers=headers,
            json={"to": "+919876543210", "message": "Blocked"},
        )
        assert r3.status_code == 429

        # Status check by owning project
        status_res = client.get(f"/api/v1/status/{body1['message_id']}", headers=headers)
        assert status_res.status_code == 200
        status_body = status_res.json()
        assert status_body["to"] == "+919876543210"
        assert status_body["priority"] == 5
        assert status_body["status"] == "pending"

        # Status check from Project 1 cannot access Limited's message
        default_key = client.get("/api/v1/admin/projects").json()[1]["api_key"]
        other_res = client.get(
            f"/api/v1/status/{body1['message_id']}",
            headers={"X-API-Key": default_key},
        )
        assert other_res.status_code == 404


def test_websocket_priority_dispatch_acks_and_disconnect_recovery(
    gateway_env: FakeDatabase,
) -> None:
    with TestClient(main.app) as client:
        api_key = client.get("/api/v1/admin/projects").json()[0]["api_key"]
        headers = {"X-API-Key": api_key}

        # Bad device secret rejected
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/device?token=wrong-secret"):
                pass

        # Queue low priority first, high priority second
        low = client.post(
            "/api/v1/send-sms",
            headers=headers,
            json={"to": "+919876543211", "message": "Low priority", "priority": 1},
        ).json()
        high = client.post(
            "/api/v1/send-sms",
            headers=headers,
            json={"to": "+919876543212", "message": "High priority", "priority": 5},
        ).json()

        with client.websocket_connect("/ws/device?token=test-device-secret") as ws:
            # Highest priority must arrive first
            msg1 = ws.receive_json()
            assert msg1["message_id"] == high["message_id"]
            assert msg1["to"] == "+919876543212"
            assert msg1["message"] == "High priority"

            ws.send_json({"message_id": msg1["message_id"], "status": "sent"})

            # Next message arrives
            msg2 = ws.receive_json()
            assert msg2["message_id"] == low["message_id"]
            # Disconnect WITHOUT ACKing msg2 to test mid-send recovery!

        # Give disconnect handler a brief moment to run
        high_status = client.get(f"/api/v1/status/{high['message_id']}", headers=headers).json()
        assert high_status["status"] == "sent"
        assert high_status["sent_at"] is not None

        low_status = client.get(f"/api/v1/status/{low['message_id']}", headers=headers).json()
        assert low_status["status"] == "pending"
        assert low_status["retry_count"] == 1

        # Reconnect and ACK low_status as failed
        with client.websocket_connect("/ws/device?token=test-device-secret") as ws:
            requeued = ws.receive_json()
            assert requeued["message_id"] == low["message_id"]
            ws.send_json(
                {
                    "message_id": requeued["message_id"],
                    "status": "failed",
                    "error": "SIM card error",
                }
            )

        # Wait briefly for ACK write before checking logs
        for _ in range(20):
            s = client.get(f"/api/v1/status/{low['message_id']}", headers=headers).json()
            if s["status"] == "failed":
                break

        logs_res = client.get("/api/v1/admin/logs")
        assert logs_res.status_code == 200
        logs_body = logs_res.json()
        assert logs_body["counts"]["sent"] == 1
        assert logs_body["counts"]["failed"] == 1
        assert logs_body["counts"]["pending"] == 0
        assert logs_body["counts"]["total"] == 2
        assert len(logs_body["logs"]) == 2
