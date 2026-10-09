"""Export the explicitly approved synthetic acceptance run, never a mock.

Run locally with Python. Vercel builds use the already exported static files.
The source database is opened read-only and all original evidence stays intact.
"""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/data"
OUTPUT = ROOT / "web/public/demo"
SESSION = "teach-ebf67b9d-591b-481e-82f6-bebb2fa6f4b3"
REPLAY = "replay-97072aef-1e0c-471d-a6c5-8acd0748e398"
ARTIFACTS = DATA / REPLAY


def read(name):
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8-sig"))


def sanitize(value):
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()
                if key not in {"review_screenshot", "confirmation_screenshot", "before_dispute_screenshot"}}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and ("C:\\" in value or "C:/" in value):
        return "[local path omitted]"
    return value


def main():
    replay = read("final-replay-state.json")
    confirmed = read("confirmed-skill.json")
    verification = read("final-verification-evidence.json")
    report = read("final-report.json")
    with sqlite3.connect((DATA / "events.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        events = [{**json.loads(payload), "id": event_id} for event_id, payload in
                  db.execute("SELECT id, payload FROM events WHERE session_id=? ORDER BY id", (SESSION,))]
        draft = json.loads(db.execute("SELECT payload FROM skill_drafts WHERE id=?", (confirmed["draft_id"],)).fetchone()[0])
        stored_replay = json.loads(db.execute("SELECT payload FROM replays WHERE id=?", (REPLAY,)).fetchone()[0])
    assert replay == stored_replay, "Archived replay must match the saved completed record"
    assert [event["id"] for event in events] == list(range(26, 35))
    assert replay["status"] == "completed" and replay["outcome_verified"] is True
    assert confirmed["status"] == "confirmed" and len(confirmed["skill"]["steps"]) == 9
    assert verification["human_confirmation"]["confirmed"] is True
    assert all(verification["actual_visible_confirmation"]["field_matches"].values())
    assert report["case_id"] == "DSP-1002"
    assert [event.get("value") for event in events if "value" in event] == ["TXN-81001"]
    assert confirmed["skill"]["steps"][5]["checked"] is False
    assert draft["skill"]["variables"][0]["name"] == "transaction_id"
    hashes = [{"file": name, "sha256": hashlib.sha256((ARTIFACTS / name).read_bytes()).hexdigest()}
              for name in ("final-replay-state.json", "confirmed-skill.json", "execution-logs.json",
                           "final-verification-evidence.json", "review-step-8.png", "review-step-9.png")]
    archive = sanitize({
        "archive_version": 1,
        "mode": "archived_verified_read_only",
        "synthetic_data": True,
        "events": events,
        "draft": draft,
        "confirmed_skill": confirmed,
        "replay": replay,
        "verification": verification,
        "outcome": {key: report[key] for key in ("case_id", "customer", "customer_id", "transaction_id", "amount", "currency")},
        "provenance": {"session_id": SESSION, "generated_at_baku": report["generated_at_baku"], "source_artifact_hashes": hashes},
        "screenshots": {"before_dispute": "/demo/before-dispute.png", "confirmation": "/demo/dispute-confirmation.png"},
    })
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "archive.json").write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # These two inspected screenshots contain only fictional local sandbox data.
    shutil.copyfile(ARTIFACTS / "review-step-8.png", OUTPUT / "before-dispute.png")
    shutil.copyfile(ARTIFACTS / "review-step-9.png", OUTPUT / "dispute-confirmation.png")
    print(f"Exported {len(events)} original events and {len(replay['results'])} real log entries; no source data changed.")


if __name__ == "__main__":
    main()
