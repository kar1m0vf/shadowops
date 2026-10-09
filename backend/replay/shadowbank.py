"""Optional verifier for the synthetic demo DOM, never a source of workflow steps.

Only visible request/result/confirmation data is read. No React state, seeded
domain data, app injection or validation bypass. Changed DOM fails closed.
"""

import re
from decimal import Decimal

from recorder.config import local_origin

ATTESTATION = "I have verified the transaction ID, customer ID, amount and currency against the customer request."


def facts(scope):
    if scope.count() != 1 or not scope.is_visible():
        raise ValueError("Expected one visible data panel.")
    result = {}
    for row in scope.locator("dl > div").all():
        if row.locator("dt").count() != 1 or row.locator("dd").count() != 1:
            raise ValueError("Unexpected detail structure.")
        if not row.is_visible():
            raise ValueError("Hidden data is not verification evidence.")
        key = row.locator("dt").inner_text().strip()
        if key in result:
            raise ValueError("Repeated facts are ambiguous.")
        result[key] = row.locator("dd").inner_text().strip()
    return result


def money(value):
    match = re.fullmatch(r"\$([0-9,]+\.[0-9]{2}) USD", value)
    if not match:
        raise ValueError("Only explicit USD demo amounts are supported by this verifier.")
    return Decimal(match[1].replace(",", "")), "USD"


class ShadowBankVerifier:
    def __init__(self):
        self.verified = None
        self.confirmation = None

    def verify_details(self, page, expected_transaction):
        self.verified = None
        if local_origin(page.url) != "http://127.0.0.1:5173":
            return False
        try:
            request = facts(page.locator("aside.panel.context"))
            transaction = facts(page.locator(".review-layout > section.panel"))
            if not expected_transaction or request["Transaction ID to find"] != expected_transaction:
                return False
            amount, currency = money(request["Disputed amount"])
            txn_amount, txn_currency = money(transaction["Amount"])
            if (transaction["Transaction ID"] != expected_transaction or
                    transaction["Customer ID"] != request["Customer ID"] or
                    txn_amount != amount or txn_currency != currency):
                return False
            validation = page.get_by_text("Validation passed: transaction ID, customer ID, amount and currency match the request.", exact=True)
            if validation.count() != 1 or not validation.is_visible():
                return False
            self.verified = (expected_transaction, request["Customer ID"], amount, currency)
            return True
        except (ValueError, KeyError):
            return False

    def observe_outcome(self, page):
        if not self.verified or local_origin(page.url) != "http://127.0.0.1:5173":
            return False
        try:
            status = page.get_by_role("status")
            if status.count() != 1 or not status.is_visible():
                return False
            if status.get_by_role("heading", name="Dispute case created", exact=True).count() != 1:
                return False
            confirmation = facts(status)
            amount, currency = money(confirmation["Amount"])
            actual = (confirmation["Transaction ID"], confirmation["Customer ID"], amount, currency)
            if actual != self.verified or not re.fullmatch(r"DSP-[0-9]+", confirmation["Case ID"]):
                return False
            self.confirmation = confirmation["Case ID"]
            return True
        except (ValueError, KeyError):
            return False

    def review_evidence(self, page):
        """Read-only review of this exact synthetic local demo, never a new attestation."""
        if local_origin(page.url) != "http://127.0.0.1:5173":
            return None
        try:
            request = facts(page.locator("aside.panel.context"))
            transaction = facts(page.locator(".review-layout > section.panel"))
            names = page.locator("aside.panel.context h3")
            checkbox = page.get_by_role("checkbox", name=ATTESTATION, exact=True)
            create = page.get_by_role("button", name="Create dispute case", exact=True)
            amount, currency = money(request["Disputed amount"])
            actual_amount, actual_currency = money(transaction["Amount"])
            matches = {
                "transaction_id": request["Transaction ID to find"] == transaction["Transaction ID"],
                "customer_id": request["Customer ID"] == transaction["Customer ID"],
                "amount": amount == actual_amount,
                "currency": currency == actual_currency,
            }
            return {"customer_name": names.inner_text() if names.count() == 1 else None,
                    "request": request, "transaction": transaction, "field_matches": matches,
                    "independently_verified_before_attestation": self.verified is not None,
                    "checkbox_matches": checkbox.count(),
                    "checkbox_checked": checkbox.is_checked() if checkbox.count() == 1 else None,
                    "create_button_matches": create.count(),
                    "create_button_enabled": create.is_enabled() if create.count() == 1 else None,
                    "dispute_confirmation_visible": page.get_by_role("heading", name="Dispute case created", exact=True).count() > 0}
        except (ValueError, KeyError):
            return None
