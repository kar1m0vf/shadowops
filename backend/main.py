"""Minimal browser-event recording API for ShadowOps."""

import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager, closing, contextmanager
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import FastAPI, Path as PathParameter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints


NonEmptyText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
BrowserURL = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]


class TargetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str | None = Field(default=None, max_length=64)
    role: str | None = Field(default=None, max_length=128)
    label: str | None = Field(default=None, max_length=1024)
    selector: str | None = Field(default=None, max_length=4096)


class BrowserEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: NonEmptyText
    timestamp: AwareDatetime
    url: BrowserURL
    action: NonEmptyText
    target: TargetMetadata


class RecordedEvent(BrowserEvent):
    id: int


@contextmanager
def database_connection(path: Path) -> Iterator[sqlite3.Connection]:
    # Each request owns its connection; the inner context commits or rolls back.
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            yield connection


def create_app(
    database_path: Path | None = None, *, development: bool | None = None
) -> FastAPI:
    database_path = (
        Path(database_path)
        if database_path is not None
        else Path(__file__).resolve().parent / "data" / "events.sqlite3"
    )
    if development is None:
        development = os.getenv("SHADOWOPS_ENV", "production") == "development"

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with database_connection(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS events_session_order "
                "ON events (session_id, id)"
            )
        yield

    application = FastAPI(title="ShadowOps Backend", lifespan=lifespan)

    if development:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            allow_credentials=False,
        )

    @application.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, error: sqlite3.Error) -> JSONResponse:
        logging.getLogger(__name__).error(
            "SQLite operation failed", exc_info=(type(error), error, error.__traceback__)
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Event storage is temporarily unavailable. Try again."},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "shadowops-backend"}

    @application.post(
        "/api/events", response_model=RecordedEvent, status_code=status.HTTP_201_CREATED
    )
    def record_event(event: BrowserEvent) -> RecordedEvent:
        with database_connection(database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO events (session_id, payload) VALUES (?, ?)",
                (event.session_id, event.model_dump_json()),
            )
            event_id = cursor.lastrowid
        return RecordedEvent(id=event_id, **event.model_dump())

    @application.get("/api/events/{session_id}", response_model=list[RecordedEvent])
    def get_events(
        session_id: Annotated[str, PathParameter(min_length=1, max_length=128)],
    ) -> list[RecordedEvent]:
        with database_connection(database_path) as connection:
            rows = connection.execute(
                "SELECT id, payload FROM events WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [RecordedEvent(id=row[0], **json.loads(row[1])) for row in rows]

    return application


app = create_app()
