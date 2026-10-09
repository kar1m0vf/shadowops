"""Strict, bounded JSON models for proposed and human-confirmed workflows."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from event_models import NonEmptyText, TargetMetadata

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
VariableName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
TEMPLATE = re.compile(r"\{\{([a-z][a-z0-9_]{0,63})\}\}")
ACTION_PARAMETERS = {
    "navigate": {"url"}, "click": {"target"}, "fill": {"target", "value"},
    "set_checked": {"target", "checked"}, "assert_visible": {"target"},
    "ask_human": {"question"},
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SkillVariable(StrictModel):
    name: VariableName
    description: Text
    source_event_id: int = Field(gt=0)
    example_value: str | None = Field(max_length=4096)
    source: Literal["human_input"]
    requires_human_input: StrictBool
    default_value: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def needs_human(self):
        if not self.requires_human_input:
            raise ValueError("A variable's source is unknown; human input is required.")
        return self


class SkillStep(StrictModel):
    action: Literal["navigate", "click", "fill", "set_checked", "assert_visible", "ask_human"]
    description: Text
    source_event_id: int | None = Field(default=None, gt=0)
    target: TargetMetadata | None = None
    url: str | None = Field(default=None, max_length=4096)
    value: str | None = Field(default=None, max_length=4096)
    checked: StrictBool | None = None
    question: Text | None = None
    uncertainty: Text | None = None

    @model_validator(mode="after")
    def action_parameters(self):
        allowed = ACTION_PARAMETERS[self.action]
        supplied = {name for name in ("target", "url", "value", "checked", "question")
                    if getattr(self, name) is not None}
        if supplied != allowed:
            raise ValueError(f"{self.action} requires exactly these parameters: {sorted(allowed)}")
        if self.action != "ask_human" and self.source_event_id is None:
            raise ValueError("UI steps must reference a recorded event.")
        if self.action == "assert_visible" and not self.uncertainty:
            raise ValueError("assert_visible is a proposed check, not an observed outcome.")
        return self


class OmittedEvent(StrictModel):
    event_id: int = Field(gt=0)
    reason: Text


class SuccessCondition(StrictModel):
    description: Text
    requires_human_verification: StrictBool

    @model_validator(mode="after")
    def unverified(self):
        if not self.requires_human_verification:
            raise ValueError("The recorder does not verify success conditions.")
        return self


class SkillDraft(StrictModel):
    name: NonEmptyText
    description: Text
    steps: list[SkillStep] = Field(min_length=1, max_length=500)
    variables: list[SkillVariable] = Field(max_length=100)
    uncertainties: list[Text] = Field(min_length=1, max_length=100)
    success_conditions: list[SuccessCondition] = Field(min_length=1, max_length=20)
    omitted_events: list[OmittedEvent] = Field(max_length=500)

    @model_validator(mode="after")
    def variable_references(self):
        names = [variable.name for variable in self.variables]
        if len(set(names)) != len(names):
            raise ValueError("Variable names must be unique.")
        used = set()
        for step in self.steps:
            if step.value is not None and ("{{" in step.value or "}}" in step.value):
                match = TEMPLATE.fullmatch(step.value)
                if not match or match[1] not in names:
                    raise ValueError("Values must use an existing variable as {{variable_name}}.")
                used.add(match[1])
        if used != set(names):
            raise ValueError("Every proposed variable must be used by a fill step.")
        return self


class CompileRequest(StrictModel):
    session_id: NonEmptyText
    task_description: Text


class ConfirmRequest(StrictModel):
    confirmed: StrictBool
    skill: SkillDraft

    @model_validator(mode="after")
    def explicit_review(self):
        if not self.confirmed:
            raise ValueError("Inspect and correct the skill, then explicitly set confirmed to true.")
        return self


class DraftRecord(StrictModel):
    id: str
    session_id: str
    task_description: str
    created_at: str
    model: str
    status: Literal["pending_review"] = "pending_review"
    source_event_ids: list[int]
    skill: SkillDraft


class SavedSkill(StrictModel):
    id: str
    draft_id: str
    session_id: str
    confirmed_at: str
    status: Literal["confirmed"] = "confirmed"
    skill: SkillDraft
