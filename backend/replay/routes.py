"""Loopback-only replay API; a pending draft can be inspected but never executed."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from compiler.models import DraftRecord, SavedSkill
from compiler.routes import UTF8JSONResponse
from storage import database_connection
from .models import ReplayInput, ReplayRecord, ResumeRequest, StartRequest, StepResult
from .policy import preflight


def local_client(request: Request):
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Replay API is available only to loopback clients.")
    if request.url.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(403, "Use the loopback backend address.")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin replay requests are forbidden. Use the backend Swagger UI or PowerShell.")


def load_skill(path, skill_id):
    with database_connection(path) as connection:
        row = connection.execute("SELECT payload FROM skills WHERE id=?", (skill_id,)).fetchone()
        draft = connection.execute("SELECT payload FROM skill_drafts WHERE id=?", (skill_id,)).fetchone() if not row else None
    if row:
        try:
            return SavedSkill.model_validate_json(row[0]), True
        except ValidationError:
            raise HTTPException(422, "Stored skill has an invalid schema/action. Replay was rejected.") from None
    if draft:
        return DraftRecord.model_validate_json(draft[0]), False
    raise HTTPException(404, "Saved skill or draft not found.")


def replay_router(path, manager):
    router = APIRouter(prefix="/api/replays", tags=["Local Replay"], dependencies=[Depends(local_client)],
                       default_response_class=UTF8JSONResponse)

    @router.post("/preflight", summary="Read-only structural check; draft previews are never executable")
    def inspect(request: ReplayInput):
        record, confirmed = load_skill(path, request.skill_id)
        return preflight(record.skill, request, manager.policy, confirmed=confirmed)

    @router.post("", response_model=ReplayRecord, status_code=202)
    def start(request: StartRequest):
        saved, confirmed = load_skill(path, request.skill_id)
        if not confirmed:
            raise HTTPException(409, "Draft is pending_review; explicitly review and confirm it first.")
        report = preflight(saved.skill, request, manager.policy, confirmed=True)
        if report["errors"]:
            raise HTTPException(422, report["errors"])
        try:
            return manager.start(saved, request)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.get("/{replay_id}", response_model=ReplayRecord)
    def status(replay_id: str):
        record = manager.get(replay_id)
        if record is None:
            raise HTTPException(404, "Replay not found.")
        return record

    @router.get("/{replay_id}/steps", response_model=list[StepResult])
    def steps(replay_id: str):
        return status(replay_id).results

    @router.post("/{replay_id}/resume", response_model=ReplayRecord)
    def resume(replay_id: str, changes: ResumeRequest):
        record = status(replay_id)
        saved, confirmed = load_skill(path, record.skill_id)
        if not confirmed:
            raise HTTPException(409, "Confirmed skill required.")
        try:
            return manager.resume(replay_id, changes, saved)
        except ValidationError:
            raise HTTPException(422, "Invalid or sensitive resume parameters; nothing was saved.") from None
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/{replay_id}/stop", status_code=202)
    def stop(replay_id: str):
        status(replay_id)
        try:
            manager.stop(replay_id)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        return {"id": replay_id, "stop_requested": True}

    return router
