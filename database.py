from datetime import datetime, timezone
import logging
import secrets
from typing import Any

from bson import ObjectId
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from models import ProjectResponse, SMSStatus, SMSStatusResponse

logger = logging.getLogger("sms_gateway.database")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="sms_gateway", alias="MONGODB_DB_NAME")
    device_secret: str = Field(
        default="replace-with-a-long-random-device-secret",
        alias="DEVICE_SECRET",
    )
    default_project_name: str = Field(default="Project 1", alias="DEFAULT_PROJECT_NAME")
    default_project_api_key: str = Field(default="", alias="DEFAULT_PROJECT_API_KEY")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    send_delay_seconds: float = Field(default=4.0, ge=0.0, alias="SEND_DELAY_SECONDS")
    worker_poll_interval_seconds: float = Field(
        default=1.0, ge=0.1, alias="WORKER_POLL_INTERVAL_SECONDS"
    )
    max_retries: int = Field(default=3, ge=1, alias="MAX_RETRIES")

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]


settings = Settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_api_key() -> str:
    return f"sms_{secrets.token_urlsafe(24)}"


def serialize_project(doc: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        api_key=doc["api_key"],
        is_active=bool(doc["is_active"]),
        rate_limit_per_min=int(doc["rate_limit_per_min"]),
        created_at=doc["created_at"],
    )


def serialize_sms(doc: dict[str, Any]) -> SMSStatusResponse:
    return SMSStatusResponse(
        message_id=str(doc["_id"]),
        project_id=str(doc["project_id"]),
        project_name=doc["project_name"],
        to=doc["to"],
        message=doc["message"],
        priority=int(doc["priority"]),
        status=SMSStatus(doc["status"]),
        retry_count=int(doc.get("retry_count", 0)),
        error=doc.get("error"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        sent_at=doc.get("sent_at"),
    )


def parse_object_id(value: str) -> ObjectId | None:
    if not ObjectId.is_valid(value):
        return None
    return ObjectId(value)


class Database:
    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None
        self.db: AsyncDatabase | None = None

    @property
    def projects(self) -> AsyncCollection:
        if self.db is None:
            raise RuntimeError("Database is not initialized")
        return self.db["projects"]

    @property
    def sms_queue(self) -> AsyncCollection:
        if self.db is None:
            raise RuntimeError("Database is not initialized")
        return self.db["sms_queue"]

    async def connect(self) -> None:
        self.client = AsyncMongoClient(
            settings.mongodb_uri,
            tz_aware=True,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[settings.mongodb_db_name]
        await self.client.admin.command("ping")
        logger.info("Connected to MongoDB database '%s'", settings.mongodb_db_name)

        await self.ensure_indexes()
        await self.ensure_default_project()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None
            self.db = None
            logger.info("Closed MongoDB connection")

    async def ensure_indexes(self) -> None:
        await self.projects.create_index([("api_key", ASCENDING)], unique=True)
        await self.projects.create_index([("name", ASCENDING)])

        await self.sms_queue.create_index(
            [
                ("status", ASCENDING),
                ("retry_count", ASCENDING),
                ("priority", DESCENDING),
                ("created_at", ASCENDING),
            ],
            name="worker_dispatch_idx",
        )
        await self.sms_queue.create_index(
            [("created_at", DESCENDING)],
            name="recent_logs_idx",
        )
        await self.sms_queue.create_index(
            [("project_id", ASCENDING), ("created_at", DESCENDING)],
            name="project_rate_limit_idx",
        )

    async def ensure_default_project(self) -> None:
        existing_count = await self.projects.count_documents({})
        if existing_count > 0:
            return

        api_key = settings.default_project_api_key.strip() or generate_api_key()
        doc = {
            "name": settings.default_project_name,
            "api_key": api_key,
            "is_active": True,
            "rate_limit_per_min": 60,
            "created_at": utc_now(),
        }
        try:
            await self.projects.insert_one(doc)
            logger.warning(
                "Seeded default project '%s' with API key: %s",
                doc["name"],
                api_key,
            )
        except DuplicateKeyError:
            # Safe under concurrent multi-worker startup
            pass


db = Database()
