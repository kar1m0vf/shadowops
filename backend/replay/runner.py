"""One local worker owns its browser. SQLite holds durable status and attempt logs."""

import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from storage import database_connection
from .browser import BrowserExecutor, ExecutionFailure, PauseReplay
from .models import ReplayRecord, ResumeRequest, StepResult
from .policy import preflight


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize_replay_storage(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS replays (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")


class ReplayManager:
    def __init__(self, database_path, policy):
        self.path, self.policy = database_path, policy
        self.lock = threading.RLock()
        self.active = None
        self.signal = threading.Event()
        self.stopped = threading.Event()
        self.thread = None
        self.request = None
        self.human_verified = set()
        self.acknowledged = set()
        self.outcome_verified = False
        self.executor = None

    def save(self, record):
        with database_connection(self.path) as connection:
            connection.execute("INSERT INTO replays(id,payload) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                               (record.id, record.model_dump_json()))

    def get(self, replay_id):
        with database_connection(self.path) as connection:
            row = connection.execute("SELECT payload FROM replays WHERE id=?", (replay_id,)).fetchone()
        return ReplayRecord.model_validate_json(row[0]) if row else None

    def recover(self):
        # Never repeat a possibly executed action after a process restart.
        with database_connection(self.path) as connection:
            rows = connection.execute("SELECT payload FROM replays").fetchall()
        for row in rows:
            record = ReplayRecord.model_validate_json(row[0])
            if record.status in ("pending", "running", "paused"):
                record.status = "failed"
                record.error = "Backend restarted; browser state was lost. Inspect logs and app state before starting a new replay."
                self.save(record)

    def start(self, saved, request):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("Another replay owns the browser. Stop it before starting a new replay.")
            record = ReplayRecord(id="replay-" + str(uuid4()), skill_id=saved.id,
                                  parameters=request.parameters, context_selection=request.context_selection,
                                  step_contexts=request.step_contexts, approved_steps=request.approved_steps,
                                  status="pending", created_at=now())
            self.request = request.model_copy(deep=True)
            self.active = record
            self.signal.clear()
            self.stopped.clear()
            self.human_verified, self.acknowledged = set(), set()
            self.outcome_verified = False
            self.executor = None
            self.save(record)
            self.thread = threading.Thread(target=self.run, args=(saved,), daemon=True, name="shadowops-replay")
            self.thread.start()
            return record.model_copy(deep=True)

    def resume(self, replay_id, changes: ResumeRequest, saved):
        with self.lock:
            record = self.active
            if not record or record.id != replay_id or record.status != "paused":
                raise ValueError("Only the currently paused live replay can be resumed.")
            number = record.current_step
            if changes.human_verified_step is not None:
                if (changes.human_verified_step != number or not number or number > len(saved.skill.steps)
                        or saved.skill.steps[number - 1].action != "set_checked"
                        or saved.skill.steps[number - 1].checked is not True):
                    raise ValueError("Human verification must refer to the currently paused checked=true step.")
            if changes.acknowledged_step is not None:
                if (changes.acknowledged_step != number or not number or number > len(saved.skill.steps)
                        or saved.skill.steps[number - 1].action != "ask_human"):
                    raise ValueError("Acknowledgment must refer to the currently paused ask_human step.")
            if changes.outcome_verified and number != len(saved.skill.steps) + 1:
                raise ValueError("Verify the outcome only after all browser steps have finished.")
            if changes.parameters and number != 0:
                raise ValueError("Parameters cannot change after browser execution has started. Stop and start a new replay.")
            updated = self.request.model_copy(deep=True)
            updated.parameters.update(changes.parameters)
            updated.step_contexts.update(changes.step_contexts)
            updated.approved_steps = sorted(set(updated.approved_steps + changes.approved_steps))
            # Revalidate merged requests so secrets or malformed hints never reach storage.
            updated = type(self.request).model_validate(updated.model_dump())
            report = preflight(saved.skill, updated, self.policy, confirmed=True)
            if report["errors"]:
                raise ValueError("Resume input failed preflight: " + "; ".join(report["errors"]))
            self.request = updated
            if changes.human_verified_step:
                self.human_verified.add(number)
            if changes.acknowledged_step:
                self.acknowledged.add(number)
            self.outcome_verified = changes.outcome_verified
            record.parameters = dict(updated.parameters)
            record.step_contexts = dict(updated.step_contexts)
            record.approved_steps = list(updated.approved_steps)
            record.status, record.pause_reason = "running", None
            self.save(record)
            self.signal.set()
            return record.model_copy(deep=True)

    def stop(self, replay_id=None):
        with self.lock:
            if replay_id and (not self.active or self.active.id != replay_id):
                raise ValueError("Replay is not active in this process.")
            self.stopped.set()
            self.signal.set()

    def log(self, number, action, source, status, detail):
        with self.lock:
            self.active.results.append(StepResult(step=number, action=action, source_event_id=source,
                                                   status=status, detail=detail, timestamp=now()))
            self.save(self.active)

    def pause(self, number, action, source, reason):
        # Capture on the browser's owning thread. Only the isolated synthetic
        # demo verifier exposes review facts; generic sites get no screenshot/data.
        screenshot, evidence = None, None
        if self.executor and self.executor.verifier:
            try:
                evidence = self.executor.verifier.review_evidence(self.executor.page)
                if evidence is not None:
                    directory = Path(__file__).resolve().parents[1] / "data" / self.active.id
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory / f"review-step-{number}.png"
                    self.executor.page.screenshot(path=str(path), full_page=True)
                    screenshot = str(path)
            except PlaywrightError:
                reason += " Review screenshot unavailable; inspect the visible browser."
        with self.lock:
            self.signal.clear()
            self.active.status = "paused"
            self.active.current_step = number
            self.active.pause_reason = reason
            self.active.review_screenshot = screenshot
            self.active.review_evidence = evidence
            self.log(number, action, source, "paused", reason)
        deadline = time.monotonic() + self.policy.pause_seconds
        while not self.signal.wait(0.1):
            if time.monotonic() >= deadline:
                raise ExecutionFailure("Paused replay expired. Browser closed; no automatic retry.")
        if self.stopped.is_set():
            raise ExecutionFailure("Replay stopped by human/backend shutdown.")

    def attempt(self, number, action, source, callback):
        while True:
            if self.stopped.is_set():
                raise ExecutionFailure("Replay stopped by human/backend shutdown.")
            with self.lock:
                self.active.status, self.active.current_step = "running", number
                self.active.pause_reason = None
                self.save(self.active)
            try:
                detail = callback()
            except PauseReplay as error:
                self.pause(number, action, source, str(error))
                continue  # Paused actions were not performed; retry only that step.
            except (PlaywrightError, AssertionError):
                self.log(number, action, source, "failed", "Browser action/assertion failed; inspect visible app state. No retry was made.")
                raise ExecutionFailure("Browser action/assertion failed at step " + str(number)) from None
            except ExecutionFailure as error:
                self.log(number, action, source, "failed", str(error))
                raise
            self.log(number, action, source, "succeeded", detail)
            return

    def run(self, saved):
        try:
            while True:
                report = preflight(saved.skill, self.request, self.policy, confirmed=True)
                if not report["missing_parameters"]:
                    break
                self.pause(0, "parameters", None, "Human input required: " + ", ".join(report["missing_parameters"]))
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.policy.headless)
                try:
                    context = browser.new_context(service_workers="block", accept_downloads=False)
                    blocked = []

                    def route_request(route):
                        if not self.policy.recording.allows(route.request.url):
                            blocked.append(True)
                            route.abort("blockedbyclient")
                            return
                        # Never follow redirects outside the loopback policy. For
                        # this minimal local engine all HTTP redirects are blocked.
                        response = route.fetch(max_redirects=0, timeout=self.policy.timeout_ms)
                        if 300 <= response.status < 400:
                            blocked.append(True)
                            route.abort("blockedbyclient")
                        else:
                            route.fulfill(response=response)

                    context.route("**/*", route_request)
                    def websocket(route):
                        url = route.url.replace("ws://", "http://", 1).replace("wss://", "https://", 1)
                        if self.policy.recording.allows(url):
                            route.connect_to_server()
                        else:
                            blocked.append(True)
                            route.close()
                    context.route_web_socket("**/*", websocket)
                    page = context.new_page()
                    page.set_default_timeout(self.policy.timeout_ms)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    context.on("page", lambda extra: extra.close() if extra != page else None)
                    executor = BrowserExecutor(page, self.policy, saved.skill)
                    self.executor = executor
                    for number, step in enumerate(saved.skill.steps, 1):
                        self.attempt(number, step.action, step.source_event_id,
                                     lambda n=number, s=step: executor.execute(
                                         n, s, self.request, human_verified=n in self.human_verified,
                                         acknowledged=n in self.acknowledged))
                        if blocked:
                            raise ExecutionFailure("A request/redirect outside the local browser policy was blocked; execution stopped.")
                        if number == 1 and self.request.context_selection:
                            self.attempt(0, "select_context", None, lambda: executor.select_context(self.request))
                    if executor.outcome_verified:
                        self.log(len(saved.skill.steps) + 1, "verify_outcome", None, "succeeded",
                                 "Synthetic demo confirmation independently matched the verified request/payment. Case: " + executor.verifier.confirmation)
                    # SavedSkill requires human verification of every success
                    # condition; an adapter cannot interpret arbitrary prose.
                    while not self.outcome_verified:
                        self.pause(len(saved.skill.steps) + 1, "verify_outcome", None,
                                   "Browser steps finished. Inspect the visible app, verification logs and every saved success condition; explicitly submit outcome_verified=true only if all are satisfied.")
                    self.log(len(saved.skill.steps) + 1, "verify_outcome", None, "succeeded", "Human explicitly verified all saved success conditions.")
                    with self.lock:
                        self.active.status = "completed"
                        self.active.outcome_verified = True
                        self.active.pause_reason = None
                        self.save(self.active)
                finally:
                    browser.close()
        except Exception as error:
            with self.lock:
                self.active.status = "failed"
                self.active.error = str(error) if isinstance(error, ExecutionFailure) else "Replay worker failed (" + type(error).__name__ + "). Inspect local configuration/browser installation; no retry was made."
                self.active.pause_reason = None
                self.save(self.active)
