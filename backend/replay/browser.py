"""Semantic Playwright actions; approvals and persistence are supplied by the runner."""

import time

from playwright.sync_api import Error as PlaywrightError, expect

from recorder.config import local_origin
from .models import AUTH, PRIVATE, safe_text
from .policy import candidates, resolve_value
from .shadowbank import ATTESTATION, ShadowBankVerifier


class PauseReplay(Exception):
    pass


class ExecutionFailure(Exception):
    pass


def hint_locator(page, hint):
    result = page.locator(hint.selector)
    return result.filter(has_text=hint.text) if hint.text else result


def candidate_locator(scope, candidate):
    if candidate.strategy == "role":
        return scope.get_by_role(candidate.value, name=candidate.name, exact=True)
    if candidate.strategy == "label":
        return scope.get_by_label(candidate.value, exact=True)
    if candidate.strategy == "placeholder":
        return scope.get_by_placeholder(candidate.value, exact=True)
    if candidate.strategy == "test_id":
        return scope.get_by_test_id(candidate.value)
    return scope.locator(candidate.value)


def unique_target(page, target, hint=None, timeout_ms=5000):
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        scope = page
        context = target.context
        if context and context.selector:
            scope = page.locator(context.selector)
        elif context and context.role and context.label:
            scope = page.get_by_role(context.role, name=context.label, exact=True)
        if scope != page and scope.count() > 1 and not hint:
            raise PauseReplay("Recorded context is ambiguous; supply a unique step context.")
        if hint:
            narrowed = hint_locator(page, hint)
            count = narrowed.count()
            if count > 1:
                raise PauseReplay("Context matches multiple containers; supply a more specific selector/text.")
            if count == 1:
                scope = narrowed
            else:
                scope = page.locator("[data-shadowops-context-does-not-exist]")
        matches = []
        for candidate in candidates(target):
            locator = candidate_locator(scope, candidate).filter(visible=True)
            if locator.count():
                matches.append(locator)
        if matches:
            locator = matches[0]
            for other in matches[1:]:
                locator = locator.and_(other)
            count = locator.count()
            if count == 1:
                return locator
            if count > 1:
                raise PauseReplay(f"Target is ambiguous: {count} visible matches. Supply step_contexts with a stable container and explicit context text. No first match was selected.")
            raise PauseReplay("Recorded locator candidates identify conflicting elements; human clarification is required.")
        if time.monotonic() >= deadline:
            raise ExecutionFailure("Target was not found before the locator timeout.")
        page.wait_for_timeout(50)


class BrowserExecutor:
    def __init__(self, page, policy, skill):
        self.page, self.policy, self.skill = page, policy, skill
        self.verifier = ShadowBankVerifier() if policy.verifier == "shadowbank" else None
        self.outcome_verified = False

    def check_url(self):
        if not self.policy.allows(self.page.url):
            raise ExecutionFailure("Browser left the explicitly allowed local destination.")

    def select_context(self, request):
        if 0 not in request.approved_steps:
            raise PauseReplay("Context selection (step 0) requires explicit click approval.")
        locator = hint_locator(self.page, request.context_selection).filter(visible=True)
        count = locator.count()
        if count != 1:
            raise PauseReplay(f"Context selection has {count} visible matches; supply a unique selection. No click was made.")
        locator.click()
        self.check_url()
        return "Exactly one visible setup target resolved. Explicit human-requested context selected; this setup action is separate from recorded steps."

    def execute(self, number, step, request, *, human_verified=False, acknowledged=False):
        if step.action == "navigate":
            if not self.policy.allows(step.url):
                raise ExecutionFailure("Navigation destination is not allowlisted.")
            self.page.goto(step.url, wait_until="domcontentloaded")
            self.check_url()
            return "Allowed local destination loaded."
        self.check_url()
        if self.verifier:
            self.outcome_verified = self.outcome_verified or self.verifier.observe_outcome(self.page)
        if step.action == "ask_human":
            if not acknowledged:
                raise PauseReplay("Human response required: " + step.question)
            return "Human explicitly acknowledged this question."
        locator = unique_target(self.page, step.target, request.step_contexts.get(str(number)), self.policy.timeout_ms)
        if step.action == "click":
            if number not in request.approved_steps:
                raise PauseReplay("Exactly one visible target resolved. Explicit click approval required for this step; clicking may change application state.")
            locator.click()
            # Actionability waits before clicks. Subsequent locators/assertions wait
            # for SPA results. Capture a demo confirmation before Back to inbox.
            if self.verifier:
                self.outcome_verified = self.outcome_verified or self.verifier.observe_outcome(self.page)
            detail = "Approved element clicked; click alone is not proof of business success."
        elif step.action == "fill":
            value = resolve_value(step, request.parameters)
            self.check_input(locator, step.target, value)
            tag = locator.evaluate("element => element.localName")  # Fixed code, no generated code/parameters.
            if tag == "select":
                locator.select_option(value=value)
            else:
                locator.fill(value)
            expect(locator).to_have_value(value)
            detail = "Allowlisted field updated and final value verified."
        elif step.action == "set_checked":
            actual_type = locator.get_attribute("type")
            if actual_type not in ("checkbox", "radio"):
                raise ExecutionFailure("set_checked target is not a checkbox/radio input.")
            hints = " ".join(filter(None, (step.target.label, locator.get_attribute("id"),
                                         locator.get_attribute("name"), locator.get_attribute("autocomplete"))))
            if AUTH.search(hints):
                raise ExecutionFailure("Authentication/sensitive checkbox targets are forbidden.")
            if step.checked:
                independently_verified = False
                if self.verifier and step.target.label == ATTESTATION:
                    expected = next((resolve_value(s, request.parameters) for s in self.skill.steps
                                     if s.action == "fill" and s.target.selector == "#transaction-id"), None)
                    independently_verified = self.verifier.verify_details(self.page, expected)
                if not independently_verified and not human_verified:
                    raise PauseReplay("Human verification required before checking: independently compare the intended request, transaction ID, customer ID, amount and currency. Checking is an attestation, not proof.")
            locator.set_checked(step.checked)
            expect(locator).to_be_checked(checked=step.checked)
            detail = "Final checked state verified: " + str(step.checked).lower() + "."
            if step.checked:
                detail += " Visible request/transaction details independently matched." if independently_verified else " Human explicitly verified the attestation."
        elif step.action == "assert_visible":
            expect(locator).to_be_visible()
            detail = "Target is visible; visibility alone does not establish the business outcome."
        else:
            raise ExecutionFailure("Unsupported action; no generated code was executed.")
        self.check_url()
        return "Exactly one visible target resolved. " + detail

    def check_input(self, locator, target, value):
        hints = " ".join(filter(None, (target.label, target.placeholder, locator.get_attribute("id"),
                                     locator.get_attribute("name"), locator.get_attribute("autocomplete"))))
        tag = locator.evaluate("element => element.localName")
        kind = locator.get_attribute("type") or "text"
        if (AUTH.search(hints) or PRIVATE.search(hints) or not safe_text(value) or
                tag not in ("input", "textarea", "select") or
                (tag == "input" and kind not in ("text", "search", "number"))):
            raise ExecutionFailure("Sensitive or unsupported input is forbidden regardless of the allowlist.")
        rules = [rule for rule in self.policy.recording.value_allowlist if rule.origin == local_origin(self.page.url)]
        if not any(locator.and_(self.page.locator(rule.selector)).count() == 1 for rule in rules):
            raise ExecutionFailure("Live input does not match the exact origin and allowlisted field.")
