"""Shared event schema; the existing API and recorder use these same models."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StringConstraints

NonEmptyText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
BrowserURL = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]


class LocatorCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["role", "label", "placeholder", "test_id", "css"]
    value: str = Field(min_length=1, max_length=4096)
    name: str | None = Field(default=None, max_length=1024)
    match_count: int | None = Field(
        default=None, ge=0, exclude_if=lambda value: value is None
    )


class TargetContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str | None = Field(default=None, max_length=64)
    role: str | None = Field(default=None, max_length=128)
    label: str | None = Field(default=None, max_length=1024)
    selector: str | None = Field(default=None, max_length=4096)


class TargetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str | None = Field(default=None, max_length=64)
    role: str | None = Field(default=None, max_length=128)
    label: str | None = Field(default=None, max_length=1024)
    selector: str | None = Field(default=None, max_length=4096)
    placeholder: str | None = Field(
        default=None, max_length=1024, exclude_if=lambda value: value is None
    )
    locator_candidates: list[LocatorCandidate] | None = Field(
        default=None, max_length=8, exclude_if=lambda value: value is None
    )
    context: TargetContext | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class BrowserEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: NonEmptyText
    timestamp: AwareDatetime
    url: BrowserURL
    action: NonEmptyText
    target: TargetMetadata
    value: str | None = Field(
        default=None, max_length=4096, exclude_if=lambda value: value is None
    )
    checked: StrictBool | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class RecordedEvent(BrowserEvent):
    id: int
