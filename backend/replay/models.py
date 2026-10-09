"""Replay inputs are separate from the immutable demonstration and saved skill."""

import re
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from compiler.models import StrictModel, VariableName

AUTH = re.compile(r"password|passwd|passphrase|secret|token|auth|login|sign.?in|username|\b(pin|otp|cvv|cvc|ssn)\b", re.I)
PRIVATE = re.compile(r"email|phone|telephone|address|birth|credit|debit|card|iban|account|customer|payment|amount|balance|social.?security", re.I)
PRIVATE_VALUE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d[\d ()+-]{8,}\d\b|\bbearer\s+|\beyJ[\w-]+\.|\b[A-Za-z0-9_-]{24,}\b|[$€£]\s*\d", re.I)


def safe_text(value: str) -> bool:
    return len(value) <= 4096 and not AUTH.search(value) and not PRIVATE_VALUE.search(value)


def css_valid(selector: str) -> bool:
    # Deliberately limited CSS subset: no Playwright pseudo-selectors, XPath,
    # positional selectors, custom engines, or executable strings.
    attribute = r'''\[[A-Za-z_][\w-]*(?:=(?:"[A-Za-z0-9_-]+"|'[A-Za-z0-9_-]+'|[A-Za-z0-9_-]+))?\]'''
    suffix = r"[.#][A-Za-z_][\w-]*|" + attribute
    compound = r"(?:[A-Za-z][\w-]*(?:" + suffix + r")*|(?:" + suffix + r")+)"
    return bool(re.fullmatch(compound + r"(?:\s*(?:[>+~]|\s)\s*" + compound + r")*", selector.strip()))


class ContextHint(StrictModel):
    selector: str = Field(min_length=1, max_length=1024)
    text: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def safe_hint(self):
        if not css_valid(self.selector) or not safe_text(self.selector) or (self.text and not safe_text(self.text)):
            raise ValueError("Use simple CSS and non-sensitive local demo context.")
        return self


class ReplayInput(StrictModel):
    skill_id: str = Field(min_length=1, max_length=128)
    parameters: dict[VariableName, str] = Field(default_factory=dict, max_length=100)
    # One optional human-requested setup click after the first navigate. Logged as step 0.
    context_selection: ContextHint | None = None
    step_contexts: dict[str, ContextHint] = Field(default_factory=dict, max_length=500)
    approved_steps: list[int] = Field(default_factory=list, max_length=501)

    @model_validator(mode="after")
    def privacy(self):
        if any(AUTH.search(name) or PRIVATE.search(name.replace('_', ' ')) or not safe_text(value)
               for name, value in self.parameters.items()):
            raise ValueError("Replay parameters must be non-sensitive local demo values; credentials are forbidden.")
        if any(not key.isdigit() or int(key) < 1 for key in self.step_contexts):
            raise ValueError("step_contexts keys must be positive, one-based step numbers.")
        if any(type(number) is not int or number < 0 for number in self.approved_steps):
            raise ValueError("approved_steps must contain non-negative step numbers (0 is context selection).")
        return self


class StartRequest(ReplayInput):
    approved: StrictBool

    @model_validator(mode="after")
    def explicit_approval(self):
        if not self.approved:
            raise ValueError("Explicit approval of this replay is required.")
        return self


class ResumeRequest(StrictModel):
    parameters: dict[VariableName, str] = Field(default_factory=dict, max_length=100)
    step_contexts: dict[str, ContextHint] = Field(default_factory=dict, max_length=500)
    approved_steps: list[int] = Field(default_factory=list, max_length=501)
    human_verified_step: int | None = Field(default=None, ge=1)
    acknowledged_step: int | None = Field(default=None, ge=1)
    outcome_verified: StrictBool = False


class StepResult(StrictModel):
    step: int
    action: str
    source_event_id: int | None = None
    status: Literal["succeeded", "paused", "failed"]
    detail: str
    timestamp: str


class ReplayRecord(StrictModel):
    id: str
    skill_id: str
    parameters: dict[str, str]
    context_selection: ContextHint | None = None
    step_contexts: dict[str, ContextHint] = Field(default_factory=dict)
    approved_steps: list[int] = Field(default_factory=list)
    status: Literal["pending", "running", "paused", "failed", "completed"]
    created_at: str
    current_step: int | None = None
    pause_reason: str | None = None
    error: str | None = None
    outcome_verified: StrictBool = False
    review_screenshot: str | None = None
    review_evidence: dict | None = None
    results: list[StepResult] = Field(default_factory=list)
