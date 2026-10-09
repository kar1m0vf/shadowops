"""Teach Mode records demonstrations; it does not learn or replay workflows."""

import os

# Keep the downloaded browser inside the virtual environment, not a global cache.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
