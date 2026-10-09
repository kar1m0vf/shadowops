"""Minimal browser-event recording API for ShadowOps."""

import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Path as PathParameter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from event_models import BrowserEvent, RecordedEvent
from storage import database_connection, load_events
from compiler.provider import LLMProvider
from compiler.routes import compiler_router, initialize_compiler_storage


def create_app(
    database_path: Path | None = None, *, development: bool | None = None,
    llm_provider: LLMProvider | None = None,
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
            initialize_compiler_storage(connection)
        yield

    application = FastAPI(title="ShadowOps Backend", lifespan=lifespan)
    application.include_router(compiler_router(database_path, llm_provider))

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
        return load_events(database_path, session_id)

    return application


app = create_app()
