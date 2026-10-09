"""Explicit loopback policy and static preflight. No browser actions here."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from compiler.models import SkillDraft, TEMPLATE
from recorder.config import RecorderConfig, clean_url, local_origin
from .models import AUTH, PRIVATE, ReplayInput, css_valid, safe_text


@dataclass
class ReplayPolicy:
    recording: RecorderConfig
    verifier: str | None = None
    timeout_ms: int = 5000
    pause_seconds: float = 900
    headless: bool = False  # Only changed by isolated automated tests.

    @classmethod
    def default(cls):
        return cls(RecorderConfig.load(Path(__file__).resolve().parents[1] / "recorder_config.json"),
                   verifier="shadowbank")

    def allows(self, url):
        try:
            parsed = urlsplit(url)
            return (self.recording.allows(url) and not parsed.query and not parsed.fragment
                    and clean_url(url) == url)
        except ValueError:
            return False


def candidates(target):
    values = list(target.locator_candidates or [])
    from event_models import LocatorCandidate
    if target.role and target.label:
        values.append(LocatorCandidate(strategy="role", value=target.role, name=target.label))
    if target.label:
        values.append(LocatorCandidate(strategy="label", value=target.label))
    if target.placeholder:
        values.append(LocatorCandidate(strategy="placeholder", value=target.placeholder))
    if target.selector:
        values.append(LocatorCandidate(strategy="css", value=target.selector))
    return values


def resolve_value(step, parameters):
    match = TEMPLATE.fullmatch(step.value)
    if match:
        if match[1] not in parameters:
            raise ValueError("Missing required parameter: " + match[1])
        return parameters[match[1]]
    return step.value


def preflight(skill: SkillDraft, request: ReplayInput, policy: ReplayPolicy, *, confirmed: bool):
    errors, warnings, missing, steps = [], list(skill.uncertainties), [], []
    if not confirmed:
        errors.append("Skill is pending_review. Human correction and confirmation are required before replay.")
    names = {variable.name for variable in skill.variables}
    if set(request.parameters) - names:
        errors.append("Unknown input parameters; only saved skill variables are accepted.")
    missing = sorted(names - set(request.parameters))
    if missing:
        warnings.append("Human input required: " + ", ".join(missing) + ". Examples/defaults are never substituted.")
    if not skill.steps or skill.steps[0].action != "navigate":
        errors.append("Replay requires an explicit initial navigate step; no destination is guessed.")
    if request.context_selection:
        warnings.append("Explicit setup click (step 0) selects the supplied context; it is not recorded evidence.")
    valid_numbers = set(range(1, len(skill.steps) + 1)) | ({0} if request.context_selection else set())
    if set(request.approved_steps) - valid_numbers or {int(key) for key in request.step_contexts} - valid_numbers:
        errors.append("Approval/context references an unknown step.")
    current_origin = None
    for number, step in enumerate(skill.steps, 1):
        item = {"step": number, "action": step.action, "source_event_id": step.source_event_id,
                "description": step.description, "target": step.target,
                "checked": step.checked,
                "requires_click_approval": step.action == "click",
                "requires_verification": step.action == "set_checked" and step.checked is True}
        if step.action == "navigate":
            if not policy.allows(step.url):
                errors.append(f"Step {number}: destination must be an explicitly allowed local URL without secrets/query/fragment.")
            else:
                current_origin = local_origin(step.url)
        elif step.target:
            locators = candidates(step.target)
            if not locators:
                errors.append(f"Step {number}: no usable locator.")
            for candidate in locators:
                if (candidate.strategy == "css" and not css_valid(candidate.value)) or (
                    candidate.strategy == "role" and (not candidate.name or not candidate.value.isalpha())
                ):
                    errors.append(f"Step {number}: unsupported or incomplete locator structure.")
            if step.target.context and step.target.context.selector and not css_valid(step.target.context.selector):
                errors.append(f"Step {number}: unsupported recorded context selector.")
            if any(c.match_count is not None and c.match_count > 1 for c in locators):
                warnings.append(f"Step {number}: recording reports repeated targets; live uniqueness must be checked.")
            if step.action == "fill":
                hints = " ".join(filter(None, (step.target.label, step.target.placeholder, step.target.selector)))
                if AUTH.search(hints) or PRIVATE.search(hints):
                    errors.append(f"Step {number}: sensitive input target is forbidden.")
                # Exact recorded CSS candidate must be in the value allowlist.
                allowed = [rule for rule in policy.recording.value_allowlist
                           if rule.origin == current_origin and (rule.selector == step.target.selector or any(
                               c.strategy == "css" and c.value == rule.selector for c in locators))]
                if not allowed:
                    errors.append(f"Step {number}: field is not explicitly allowlisted for values.")
                try:
                    value = resolve_value(step, request.parameters)
                    if not safe_text(value):
                        errors.append(f"Step {number}: sensitive input value is forbidden.")
                    if allowed and any(rule.synthetic_identifier for rule in allowed):
                        import re
                        if value and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
                            errors.append(f"Step {number}: expected a short synthetic identifier.")
                    item["resolved_value"] = value if safe_text(value) else "[blocked]"
                except ValueError:
                    item["resolved_value"] = None
        if step.action == "set_checked" and step.checked is False and "to confirm" in step.description.lower():
            warnings.append(f"Step {number}: unchecked=false does not confirm verification. Human must review the description.")
        steps.append(item)
    warnings.append("Static preflight cannot prove live locator uniqueness or business success. Clicks require explicit step approval; completion requires independent or human outcome verification.")
    return {"skill_id": request.skill_id, "confirmed": confirmed, "ready": not errors and not missing,
            "can_start": confirmed and not errors, "errors": errors, "missing_parameters": missing,
            "warnings": warnings, "steps": steps, "context_selection": request.context_selection,
            "allowed_origins": policy.recording.allowed_origins}
