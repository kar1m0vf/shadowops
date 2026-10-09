"""Compile, inspect, explicitly confirm and retrieve. Nothing runs in a browser."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from event_models import RecordedEvent
from storage import database_connection, load_events
from compiler.models import CompileRequest, ConfirmRequest, DraftRecord, SavedSkill
from compiler.provider import CompilerError, LLMProvider, OpenAICompatibleProvider
from compiler.service import compile_events, validate_evidence


class UTF8JSONResponse(JSONResponse):
    # Windows PowerShell 5 needs the explicit charset when decoding Unicode JSON.
    media_type = "application/json; charset=utf-8"


def initialize_compiler_storage(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS skill_drafts (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            evidence TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL
        )
    """)


def compiler_router(database_path: Path, provider: LLMProvider | None = None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["Skill Compiler"], default_response_class=UTF8JSONResponse)

    @router.post("/skills/compile", response_model=DraftRecord, status_code=201,
                 summary="Call the real LLM to create a workflow draft")
    def compile_recording(request: CompileRequest) -> DraftRecord:
        events = load_events(database_path, request.session_id)
        if not events:
            raise HTTPException(404, "Recording session has no events.")
        try:
            active_provider = provider if provider is not None else OpenAICompatibleProvider.from_environment()
            skill = compile_events(active_provider, request.task_description, events)
        except CompilerError as error:
            raise HTTPException(error.status_code, error.detail) from None
        record = DraftRecord(
            id="draft-" + str(uuid4()), session_id=request.session_id,
            task_description=request.task_description, created_at=datetime.now(timezone.utc).isoformat(),
            model=active_provider.model, source_event_ids=[event.id for event in events], skill=skill,
        )
        with database_connection(database_path) as connection:
            connection.execute("INSERT INTO skill_drafts (id, payload, evidence) VALUES (?, ?, ?)",
                               (record.id, record.model_dump_json(),
                                json.dumps([event.model_dump(mode="json") for event in events])))
        return record

    @router.get("/skill-drafts/{draft_id}", response_model=DraftRecord)
    def get_draft(draft_id: str) -> DraftRecord:
        with database_connection(database_path) as connection:
            row = connection.execute("SELECT payload FROM skill_drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Skill draft not found.")
        return DraftRecord.model_validate_json(row[0])

    @router.post("/skill-drafts/{draft_id}/confirm", response_model=SavedSkill, status_code=201,
                 summary="Save only after human review; send the complete corrected skill")
    def confirm_draft(draft_id: str, request: ConfirmRequest) -> SavedSkill:
        with database_connection(database_path) as connection:
            row = connection.execute("SELECT payload, evidence FROM skill_drafts WHERE id = ?", (draft_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Skill draft not found.")
            draft = DraftRecord.model_validate_json(row[0])
            events = [RecordedEvent.model_validate(event) for event in json.loads(row[1])]
            try:
                validate_evidence(request.skill, events, reviewed=True)
            except ValueError as error:
                raise HTTPException(422, str(error)) from None
            saved = SavedSkill(
                id="skill-" + str(uuid4()), draft_id=draft_id, session_id=draft.session_id,
                confirmed_at=datetime.now(timezone.utc).isoformat(), skill=request.skill,
            )
            try:
                connection.execute("INSERT INTO skills (id, draft_id, payload) VALUES (?, ?, ?)",
                                   (saved.id, draft_id, saved.model_dump_json()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "This draft has already been confirmed.") from None
        return saved

    @router.get("/skills/{skill_id}", response_model=SavedSkill)
    def get_skill(skill_id: str) -> SavedSkill:
        with database_connection(database_path) as connection:
            row = connection.execute("SELECT payload FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Confirmed skill not found.")
        return SavedSkill.model_validate_json(row[0])

    return router
