import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import logging
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pymongo import ASCENDING, DESCENDING, ReturnDocument

from database import (
    db,
    generate_api_key,
    parse_object_id,
    serialize_project,
    serialize_sms,
    settings,
    utc_now,
)
from models import (
    AdminLogsResponse,
    CreateProjectRequest,
    DeviceAckPayload,
    DevicePushPayload,
    ProjectResponse,
    QueueCounts,
    SendSMSRequest,
    SendSMSResponse,
    SMSStatus,
    SMSStatusResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sms_gateway")


async def revert_processing_jobs(reason: str) -> int:
    """Revert in-flight 'processing' jobs to 'pending' or 'failed' if max retries reached."""
    now = utc_now()
    retry_threshold = settings.max_retries - 1

    requeued = await db.sms_queue.update_many(
        {
            "status": SMSStatus.PROCESSING.value,
            "retry_count": {"$lt": retry_threshold},
        },
        {
            "$set": {
                "status": SMSStatus.PENDING.value,
                "error": reason,
                "updated_at": now,
            },
            "$inc": {"retry_count": 1},
        },
    )

    exhausted = await db.sms_queue.update_many(
        {
            "status": SMSStatus.PROCESSING.value,
            "retry_count": {"$gte": retry_threshold},
        },
        {
            "$set": {
                "status": SMSStatus.FAILED.value,
                "error": f"{reason}; max retries ({settings.max_retries}) reached",
                "updated_at": now,
            },
            "$inc": {"retry_count": 1},
        },
    )

    total_updated = requeued.modified_count + exhausted.modified_count
    if total_updated > 0:
        logger.warning(
            "Recovered %d processing job(s): %d re-queued, %d marked failed",
            total_updated,
            requeued.modified_count,
            exhausted.modified_count,
        )
    return total_updated


class DeviceConnectionManager:
    """Maintains a single active WebSocket connection to the Android gateway phone."""

    def __init__(self) -> None:
        self._ws: WebSocket | None = None
        self._conn_id: str | None = None
        self._lock = asyncio.Lock()

    @property
    def is_online(self) -> bool:
        return self._ws is not None

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        old_ws: WebSocket | None = None
        async with self._lock:
            old_ws = self._ws
            conn_id = secrets.token_hex(8)
            self._ws = websocket
            self._conn_id = conn_id

        if old_ws is not None:
            logger.info("Replacing existing device WebSocket connection")
            try:
                await old_ws.close(code=1001, reason="Replaced by new device connection")
            except Exception:
                pass
            await revert_processing_jobs("Device reconnected before acknowledgment")

        logger.info("Android device connected (conn_id=%s)", conn_id)
        return conn_id

    async def disconnect(self, conn_id: str) -> None:
        was_active = False
        async with self._lock:
            if self._conn_id == conn_id:
                self._ws = None
                self._conn_id = None
                was_active = True

        if was_active:
            logger.warning("Android device disconnected (conn_id=%s)", conn_id)
            await revert_processing_jobs("Device disconnected mid-send")

    async def close_active(self) -> None:
        async with self._lock:
            ws = self._ws
            self._ws = None
            self._conn_id = None
        if ws is not None:
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass

    async def send_job(self, payload: DevicePushPayload) -> bool:
        async with self._lock:
            ws = self._ws
            conn_id = self._conn_id
            if ws is None:
                return False
            try:
                await ws.send_json(payload.model_dump())
                return True
            except Exception as exc:
                logger.warning("Failed sending job %s to device: %s", payload.message_id, exc)
                if self._conn_id == conn_id:
                    self._ws = None
                    self._conn_id = None
                return False


device_manager = DeviceConnectionManager()


async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> bool:
    """Sleep up to `seconds`, returning True immediately if `stop_event` is set."""
    if seconds <= 0:
        return stop_event.is_set()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        return True
    except asyncio.TimeoutError:
        return False


async def sms_dispatch_worker(stop_event: asyncio.Event) -> None:
    """Poll MongoDB for highest-priority oldest pending SMS and dispatch to the device."""
    logger.info(
        "SMS dispatch worker started (send_delay=%.1fs, max_retries=%d)",
        settings.send_delay_seconds,
        settings.max_retries,
    )
    while not stop_event.is_set():
        try:
            if not device_manager.is_online:
                await _wait_or_stop(stop_event, settings.worker_poll_interval_seconds)
                continue

            job = await db.sms_queue.find_one_and_update(
                {
                    "status": SMSStatus.PENDING.value,
                    "retry_count": {"$lt": settings.max_retries},
                },
                {
                    "$set": {
                        "status": SMSStatus.PROCESSING.value,
                        "updated_at": utc_now(),
                    }
                },
                sort=[("priority", DESCENDING), ("created_at", ASCENDING)],
                return_document=ReturnDocument.AFTER,
            )

            if job is None:
                await _wait_or_stop(stop_event, settings.worker_poll_interval_seconds)
                continue

            payload = DevicePushPayload(
                message_id=str(job["_id"]),
                to=job["to"],
                message=job["message"],
            )
            pushed = await device_manager.send_job(payload)
            if not pushed:
                await revert_processing_jobs("Device unavailable during dispatch")
                await _wait_or_stop(stop_event, settings.worker_poll_interval_seconds)
                continue

            logger.info(
                "Dispatched SMS %s to %s (priority=%d)",
                payload.message_id,
                payload.to,
                job["priority"],
            )
            # Enforce delay between sends to prevent Android OS SMS rate-limit/spam blocks
            await _wait_or_stop(stop_event, settings.send_delay_seconds)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Error in SMS dispatch worker loop: %s", exc)
            await _wait_or_stop(stop_event, settings.worker_poll_interval_seconds)

    logger.info("SMS dispatch worker stopped")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.device_secret == "replace-with-a-long-random-device-secret":
        logger.warning(
            "Using default DEVICE_SECRET! Set a strong DEVICE_SECRET in .env before exposing externally."
        )

    await db.connect()
    await revert_processing_jobs("Server restarted while message was processing")

    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(sms_dispatch_worker(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await device_manager.close_active()
        await db.close()


app = FastAPI(
    title="RBPSSK Self-Hosted SMS Gateway",
    version="1.0.0",
    description="Free self-hosted SMS gateway backed by FastAPI, MongoDB (PyMongo AsyncMongoClient), and an Android WebSocket bridge.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials="*" not in settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_project(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    project = await db.projects.find_one({"api_key": x_api_key})
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not project.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project is inactive",
        )
    return project


async def verify_admin_access(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    if not settings.admin_api_key:
        return
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header",
        )


@app.get("/health")
async def health_check() -> dict[str, Any]:
    await db.client.admin.command("ping")
    return {
        "status": "ok",
        "database": "connected",
        "device_online": device_manager.is_online,
    }


@app.post(
    "/api/v1/send-sms",
    response_model=SendSMSResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_sms(
    payload: SendSMSRequest,
    project: dict[str, Any] = Depends(get_current_project),
) -> SendSMSResponse:
    now = utc_now()
    window_start = now - timedelta(minutes=1)
    rate_limit = int(project.get("rate_limit_per_min", 60))

    recent_count = await db.sms_queue.count_documents(
        {
            "project_id": project["_id"],
            "created_at": {"$gte": window_start},
        }
    )
    if recent_count >= rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({rate_limit} SMS/min)",
            headers={"Retry-After": "60"},
        )

    doc = {
        "project_id": project["_id"],
        "project_name": project["name"],
        "to": payload.to,
        "message": payload.message,
        "priority": payload.priority,
        "status": SMSStatus.PENDING.value,
        "retry_count": 0,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "sent_at": None,
    }
    result = await db.sms_queue.insert_one(doc)

    return SendSMSResponse(
        message_id=str(result.inserted_id),
        status=SMSStatus.PENDING,
        device_online=device_manager.is_online,
        queued_at=now,
    )


@app.get("/api/v1/status/{message_id}", response_model=SMSStatusResponse)
async def get_sms_status(
    message_id: str,
    project: dict[str, Any] = Depends(get_current_project),
) -> SMSStatusResponse:
    oid = parse_object_id(message_id)
    if oid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message_id format",
        )

    doc = await db.sms_queue.find_one({"_id": oid, "project_id": project["_id"]})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return serialize_sms(doc)


@app.get(
    "/api/v1/admin/logs",
    response_model=AdminLogsResponse,
    dependencies=[Depends(verify_admin_access)],
)
async def get_admin_logs() -> AdminLogsResponse:
    cursor = db.sms_queue.find({}).sort([("created_at", DESCENDING)]).limit(50)
    docs = await cursor.to_list(length=50)

    agg_cursor = await db.sms_queue.aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    )
    grouped = await agg_cursor.to_list(length=None)
    count_map = {row["_id"]: int(row["count"]) for row in grouped}

    pending = count_map.get(SMSStatus.PENDING.value, 0)
    processing = count_map.get(SMSStatus.PROCESSING.value, 0)
    sent = count_map.get(SMSStatus.SENT.value, 0)
    failed = count_map.get(SMSStatus.FAILED.value, 0)

    return AdminLogsResponse(
        device_online=device_manager.is_online,
        counts=QueueCounts(
            pending=pending,
            processing=processing,
            sent=sent,
            failed=failed,
            total=pending + processing + sent + failed,
        ),
        logs=[serialize_sms(doc) for doc in docs],
    )


@app.post(
    "/api/v1/admin/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_access)],
)
async def create_project(payload: CreateProjectRequest) -> ProjectResponse:
    doc = {
        "name": payload.name,
        "api_key": generate_api_key(),
        "is_active": payload.is_active,
        "rate_limit_per_min": payload.rate_limit_per_min,
        "created_at": utc_now(),
    }
    result = await db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_project(doc)


@app.get(
    "/api/v1/admin/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(verify_admin_access)],
)
async def list_projects() -> list[ProjectResponse]:
    cursor = db.projects.find({}).sort([("created_at", DESCENDING)])
    docs = await cursor.to_list(length=None)
    return [serialize_project(doc) for doc in docs]


async def _handle_device_ack(raw_message: str) -> None:
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning("Ignoring non-JSON message from device: %s", raw_message[:200])
        return

    try:
        ack = DeviceAckPayload.model_validate(data)
    except ValidationError as exc:
        logger.warning("Ignoring invalid device ACK payload: %s", exc.errors())
        return

    oid = parse_object_id(ack.message_id)
    if oid is None:
        logger.warning("Ignoring ACK with invalid message_id: %s", ack.message_id)
        return

    now = utc_now()
    update_fields: dict[str, Any] = {
        "status": ack.status,
        "updated_at": now,
    }
    if ack.status == SMSStatus.SENT.value:
        update_fields["sent_at"] = now
        update_fields["error"] = None
    else:
        update_fields["error"] = ack.error or "Failed to send on Android device"

    result = await db.sms_queue.update_one({"_id": oid}, {"$set": update_fields})
    if result.matched_count == 0:
        logger.warning("ACK received for unknown message_id: %s", ack.message_id)
    else:
        logger.info("Updated SMS %s -> %s", ack.message_id, ack.status)


@app.websocket("/ws/device")
async def device_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    if not token or not secrets.compare_digest(token, settings.device_secret):
        await websocket.close(code=1008, reason="Invalid device token")
        return

    conn_id = await device_manager.connect(websocket)
    try:
        while True:
            raw_message = await websocket.receive_text()
            await _handle_device_ack(raw_message)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Device WebSocket error (conn_id=%s): %s", conn_id, exc)
    finally:
        await device_manager.disconnect(conn_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)

