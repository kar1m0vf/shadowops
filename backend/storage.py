"""SQLite connection and ordered event reads shared by the API and compiler."""

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from event_models import RecordedEvent


@contextmanager
def database_connection(path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            yield connection


def load_events(path: Path, session_id: str) -> list[RecordedEvent]:
    with database_connection(path) as connection:
        rows = connection.execute(
            "SELECT id, payload FROM events WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [RecordedEvent(id=row[0], **json.loads(row[1])) for row in rows]
