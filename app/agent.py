# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0

import os
import re
from typing import Optional

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


# Use Gemini API key mode, not Google Cloud / Vertex AI.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"


FORBIDDEN_CATEGORIES = [
    "alcohol",
    "gambling",
    "weapons",
    "personal entertainment",
    "gift card",
    "crypto",
]

HIGH_RISK_KEYWORDS = [
    "urgent",
    "wire transfer",
    "cash",
    "personal account",
    "no receipt",
    "missing receipt",
    "split payment",
    "unknown vendor",
]


def _extract_amount(query: str) -> Optional[float]:
    """Extracts the largest numeric amount from a user expense request."""
    matches = re.findall(r"(\d+(?:[.,]\d{1,2})?)", query)
    if not matches:
        return None

    amounts = []
    for match in matches:
        normalized = match.replace(",", ".")
        try:
            amounts.append(float(normalized))
        except ValueError:
            continue

    if not amounts:
        return None

    return max(amounts)


def triage_expense_request(query: str) -> str:
    """Triage an expense request according to a simple local policy.

    Policy:
    - Missing amount: human review required.
    - Forbidden categories: auto reject.
    - Amount up to 100 EUR: auto approve if low risk.
    - Amount from 100.01 to 500 EUR: human review required.
    - Amount above 500 EUR: human review required.
    - High-risk wording: human review required.

    Args:
        query: The user's expense approval request.

    Returns:
        A structured triage decision.
    """
    query_lower = query.lower()
    amount = _extract_amount(query)

    forbidden_hits = [
        category for category in FORBIDDEN_CATEGORIES if category in query_lower
    ]
    risk_hits = [keyword for keyword in HIGH_RISK_KEYWORDS if keyword in query_lower]

    if forbidden_hits:
        return (
            "DECISION: AUTO_REJECT\n"
            f"REASON: Forbidden expense category detected: {', '.join(forbidden_hits)}.\n"
            "NEXT_STEP: Inform the user that this expense cannot be approved."
        )

    if amount is None:
        return (
            "DECISION: HUMAN_REVIEW_REQUIRED\n"
            "REASON: No clear expense amount was found.\n"
            "NEXT_STEP: Ask the user for the amount, currency, category, vendor, and receipt status."
        )

    if risk_hits:
        return (
            "DECISION: HUMAN_REVIEW_REQUIRED\n"
            f"AMOUNT: {amount:.2f}\n"
            f"REASON: High-risk wording detected: {', '.join(risk_hits)}.\n"
            "NEXT_STEP: Route this request to a human reviewer."
        )

    if amount <= 100:
        return (
            "DECISION: AUTO_APPROVE\n"
            f"AMOUNT: {amount:.2f}\n"
            "REASON: Low-value expense and no risk indicators detected.\n"
            "NEXT_STEP: Approve the expense and remind the user to keep the receipt."
        )

    if amount <= 500:
        return (
            "DECISION: HUMAN_REVIEW_REQUIRED\n"
            f"AMOUNT: {amount:.2f}\n"
            "REASON: Medium-value expense requires manual approval.\n"
            "NEXT_STEP: Route this request to a human reviewer."
        )

    return (
        "DECISION: HUMAN_REVIEW_REQUIRED\n"
        f"AMOUNT: {amount:.2f}\n"
        "REASON: Expense exceeds the automatic approval limit.\n"
        "NEXT_STEP: Route this request to a human reviewer."
    )


def create_human_review_ticket(query: str) -> str:
    """Simulates creating a human-in-the-loop review ticket.

    Args:
        query: The original user request.

    Returns:
        A simulated review ticket confirmation.
    """
    amount = _extract_amount(query)
    amount_text = "unknown" if amount is None else f"{amount:.2f}"

    return (
        "HUMAN_REVIEW_TICKET_CREATED\n"
        "ticket_id: EXP-LOCAL-REVIEW-001\n"
        f"amount: {amount_text}\n"
        "status: waiting_for_human_reviewer\n"
        "note: This is a local simulation. No external system was contacted."
    )


def explain_expense_policy(query: str) -> str:
    """Explains the local expense approval policy."""
    return (
        "Local expense policy:\n"
        "- Expenses up to 100 EUR can be auto-approved if low risk.\n"
        "- Expenses between 100.01 and 500 EUR require human review.\n"
        "- Expenses above 500 EUR require human review.\n"
        "- Forbidden categories are rejected.\n"
        "- Missing amount, missing receipt, urgent payment, cash, or unknown vendor require human review."
    )


root_agent = Agent(
    name="expense_approval_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a secure expense approval triage agent.\n\n"
        "Your job is to evaluate employee expense requests using the local policy tools.\n"
        "Always use triage_expense_request before making an approval decision.\n\n"
        "Rules:\n"
        "1. Do not approve high-risk or unclear expenses.\n"
        "2. If the tool returns HUMAN_REVIEW_REQUIRED, do not approve the expense yourself.\n"
        "3. If human review is required, call create_human_review_ticket and tell the user the request is waiting for review.\n"
        "4. If the tool returns AUTO_REJECT, explain the rejection briefly and professionally.\n"
        "5. If the tool returns AUTO_APPROVE, approve it and remind the user to keep receipts.\n"
        "6. Do not execute code, access files, or contact external systems.\n"
        "7. If the user asks for something unrelated to expense approval, politely explain that you only handle expense requests.\n"
    ),
    tools=[
        triage_expense_request,
        create_human_review_ticket,
        explain_expense_policy,
    ],
)


app = App(
    root_agent=root_agent,
    name="app",
)