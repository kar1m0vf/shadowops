"""Explicit local-origin and field-value policy."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


def local_origin(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Only HTTP(S) URLs on 127.0.0.1, localhost or ::1 are allowed.")
    # Accessing port also validates invalid or out-of-range ports.
    port = parsed.port
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")


def clean_url(url: str) -> str:
    """Do not serialize queries, fragments or credential-like path segments."""
    parsed = urlsplit(url)
    path = re.sub(
        r"[^/]*(?:@|%40|[0-9]{6,}|[A-Za-z0-9_-]{24,})[^/]*",
        "[redacted]",
        parsed.path,
        flags=re.IGNORECASE,
    )
    if re.search(r"password|secret|token|oauth|authorize|login|sign[-_]?in", path, re.I):
        path = "/[redacted]"
    return urlunsplit((parsed.scheme, parsed.netloc, path or "/", "", ""))


class AllowedValueField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str
    selector: str = Field(min_length=1, max_length=1024)
    # Permits a short synthetic identifier, never passwords, tokens or private data.
    synthetic_identifier: bool = False


class RecorderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_url: str = "http://127.0.0.1:5173"
    api_url: str = "http://127.0.0.1:8000"
    allowed_origins: list[str] = Field(min_length=1)
    value_allowlist: list[AllowedValueField] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_local_urls(self):
        for origin in self.allowed_origins:
            if local_origin(origin) != origin:
                raise ValueError("allowed_origins must contain exact origins without paths.")
        if local_origin(self.start_url) not in self.allowed_origins:
            raise ValueError("start_url must belong to an allowed origin.")
        for url in (self.start_url, self.api_url):
            parsed = urlsplit(url)
            local_origin(url)
            if parsed.query or parsed.fragment:
                raise ValueError("Configured URLs must not contain queries or fragments.")
        if urlsplit(self.api_url).path not in {"", "/"}:
            raise ValueError("api_url must be an origin, without a path.")
        for field in self.value_allowlist:
            if field.origin not in self.allowed_origins:
                raise ValueError("Every value_allowlist origin must be an allowed origin.")
        return self

    def allows(self, url: str) -> bool:
        try:
            return local_origin(url) in self.allowed_origins
        except ValueError:
            return False

    @classmethod
    def load(cls, path: Path):
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
