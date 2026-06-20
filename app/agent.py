# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0

import os
import re
from datetime import datetime
from typing import Optional

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


# Local Gemini API key mode. Do not use Google Cloud / Vertex AI for this prototype.
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'False'


CRITICAL_RISK_KEYWORDS = [
    'gas',
    'water',
    'power cable',
    'strom',
    'wasser',
    'gasleitung',
    'accident',
    'injury',
    'unsafe',
    'open trench',
    'verkehrssicherung',
    'permit missing',
    'missing permit',
    'no permit',
    'blocked road',
    'complaint',
    'police',
    'authority',
    'bauamt',
    'stop work',
]

MEDIUM_RISK_KEYWORDS = [
    'delay',
    'asphalt',
    'restoration',
    'subcontractor',
    'subunternehmer',
    'material missing',
    'documentation missing',
    'photo missing',
    'measurement missing',
    'hdd',
    'blowstop',
    'traffic management',
    'rsa',
    'weather',
    'rain',
    'crew',
]

DOCUMENTATION_KEYWORDS = [
    'photo',
    'photos',
    'measurement',
    'measurements',
    'aufmaß',
    'redline',
    'rotberichtigung',
    'gps',
    'gis',
    'qgis',
    'as-built',
    'documentation',
    'bohrprotokoll',
    'hdd protocol',
    'depth',
    'trench',
    'nvt',
    'hüp',
    'fiber',
    'splice',
]

COST_KEYWORDS = [
    'cost',
    'invoice',
    'rechnung',
    'claim',
    'extra work',
    'nachtrag',
    'budget',
    'approval',
    'approve',
    'payment',
    'hours',
    'crewmeister',
    'material',
    'subcontractor invoice',
]

A2A_SPECIALISTS = {
    'site_risk': 'Site Risk Agent',
    'documentation': 'Documentation QA Agent',
    'cost': 'Cost & Approval Agent',
    'daily_brief': 'Daily Brief Agent',
    'security': 'Security & Evaluation Guard',
}


def _extract_amount(query: str) -> Optional[float]:
    """Extracts the largest numeric amount from a text.

    Args:
        query: User request containing possible money or quantity values.

    Returns:
        The largest detected number as float, or None.
    """
    matches = re.findall(r'(\d+(?:[.,]\d{1,2})?)', query)
    if not matches:
        return None

    values = []
    for match in matches:
        try:
            values.append(float(match.replace(',', '.')))
        except ValueError:
            continue

    if not values:
        return None

    return max(values)


def _find_hits(query: str, keywords: list[str]) -> list[str]:
    """Finds configured keyword hits in the query.

    Args:
        query: User request.
        keywords: Keywords to check.

    Returns:
        List of matched keywords.
    """
    query_lower = query.lower()
    return [keyword for keyword in keywords if keyword in query_lower]


def analyze_site_risk(query: str) -> str:
    """Analyzes construction-site risk for FTTH / 5G infrastructure work.

    This tool classifies risks related to blocked segments, permits, road safety,
    utilities, subcontractors, asphalt restoration, documentation gaps, and public
    complaints.

    Args:
        query: Description of the site situation.

    Returns:
        A structured risk analysis with risk level, causes, and next actions.
    """
    critical_hits = _find_hits(query, CRITICAL_RISK_KEYWORDS)
    medium_hits = _find_hits(query, MEDIUM_RISK_KEYWORDS)

    if critical_hits:
        risk_level = 'CRITICAL'
        priority = 'Immediate Bauleiter / PM intervention required'
        next_actions = [
            'Stop or freeze the affected work section until the risk is clarified.',
            'Check permit status, traffic safety setup, and utility conflict immediately.',
            'Notify project manager and responsible subcontractor lead.',
            'Create a same-day action log with owner and deadline.',
            'Do not allow further excavation or restoration until the blocking issue is resolved.',
        ]
    elif medium_hits:
        risk_level = 'MEDIUM'
        priority = 'Same-day coordination required'
        next_actions = [
            'Clarify owner of the issue: Bauleiter, subcontractor, documentation, or authority.',
            'Request missing evidence such as photos, measurements, redlines, or daily report.',
            'Define one responsible person and one deadline.',
            'Monitor until the segment returns to in_progress or restored.',
        ]
    else:
        risk_level = 'LOW'
        priority = 'Normal monitoring'
        next_actions = [
            'Keep the segment in daily monitoring.',
            'Confirm that documentation, photos, and status updates are complete.',
            'No escalation required unless new blockers appear.',
        ]

    return (
        'SITE_RISK_ANALYSIS\n'
        f'risk_level: {risk_level}\n'
        f'priority: {priority}\n'
        f'critical_hits: {critical_hits}\n'
        f'medium_hits: {medium_hits}\n'
        'recommended_actions:\n'
        + '\n'.join(f'- {action}' for action in next_actions)
    )


def check_documentation_readiness(query: str) -> str:
    """Checks whether an FTTH / 5G infrastructure segment is documentation-ready.

    Args:
        query: Description of available documentation or missing documents.

    Returns:
        A documentation readiness assessment.
    """
    hits = _find_hits(query, DOCUMENTATION_KEYWORDS)
    query_lower = query.lower()

    missing_indicators = [
        'missing',
        'not available',
        'no photo',
        'no photos',
        'no measurement',
        'not measured',
        'unclear',
        'incomplete',
        'fehlt',
        'keine',
        'unvollständig',
    ]

    missing_hits = [word for word in missing_indicators if word in query_lower]

    if missing_hits:
        status = 'NOT_READY'
        next_actions = [
            'Request missing photos before/after restoration.',
            'Request measurements / Aufmaß with segment reference.',
            'Check redline / Rotberichtigung consistency.',
            'Verify GPS/GIS location if available.',
            'Do not mark the segment as fully documented until evidence is complete.',
        ]
    elif hits:
        status = 'PARTIALLY_READY'
        next_actions = [
            'Review provided documentation items.',
            'Validate that each segment has photos, measurements, and status.',
            'Check whether GIS/redline data matches field execution.',
        ]
    else:
        status = 'UNKNOWN'
        next_actions = [
            'Ask the user what documentation is available.',
            'Minimum required: photos, measurements, segment ID, street, status, and responsible crew.',
        ]

    return (
        'DOCUMENTATION_READINESS_CHECK\n'
        f'status: {status}\n'
        f'detected_documentation_terms: {hits}\n'
        f'missing_indicators: {missing_hits}\n'
        'recommended_actions:\n'
        + '\n'.join(f'- {action}' for action in next_actions)
    )


def triage_cost_or_approval(query: str) -> str:
    """Triage cost, invoice, subcontractor, and approval requests.

    Args:
        query: User request mentioning costs, invoices, claims, materials, or approvals.

    Returns:
        A structured cost / approval triage decision.
    """
    amount = _extract_amount(query)
    hits = _find_hits(query, COST_KEYWORDS)
    query_lower = query.lower()

    risk_terms = [
        'no receipt',
        'missing receipt',
        'unknown vendor',
        'cash',
        'urgent',
        'without approval',
        'extra work',
        'nachtrag',
        'claim',
    ]
    risk_hits = [term for term in risk_terms if term in query_lower]

    if amount is None and hits:
        decision = 'HUMAN_REVIEW_REQUIRED'
        reason = 'Cost-related request detected, but no clear amount was found.'
        next_step = 'Ask for amount, vendor, project segment, receipt, and approval basis.'
    elif amount is not None and amount <= 250 and not risk_hits:
        decision = 'LOW_RISK_APPROVAL_CANDIDATE'
        reason = 'Low-value cost item without obvious risk indicators.'
        next_step = 'Check receipt and project assignment before approval.'
    elif amount is not None and amount <= 1000:
        decision = 'HUMAN_REVIEW_REQUIRED'
        reason = 'Medium-value or risk-bearing item requires human approval.'
        next_step = 'Route to PM/Bauleiter for manual approval.'
    else:
        decision = 'SENIOR_REVIEW_REQUIRED'
        reason = 'High-value, unclear, or potentially contractual cost item.'
        next_step = 'Escalate to project management / commercial review.'

    return (
        'COST_APPROVAL_TRIAGE\n'
        f'decision: {decision}\n'
        f'amount_detected: {amount}\n'
        f'cost_terms_detected: {hits}\n'
        f'risk_terms_detected: {risk_hits}\n'
        f'reason: {reason}\n'
        f'next_step: {next_step}'
    )


def create_daily_project_brief(query: str) -> str:
    """Creates a daily Bauleiter-style project brief.

    Args:
        query: Situation description for one or more project segments.

    Returns:
        A structured daily project brief.
    """
    site_risk = analyze_site_risk(query)
    documentation = check_documentation_readiness(query)
    cost = triage_cost_or_approval(query)

    return (
        'INFRATWIN_DAILY_PROJECT_BRIEF\n'
        f'date: {datetime.now().strftime("%Y-%m-%d")}\n\n'
        '1. Situation Summary\n'
        '- The request describes an infrastructure coordination case for FTTH / 5G delivery.\n'
        '- The agent assessed operational risk, documentation readiness, and cost/approval impact.\n\n'
        '2. Site Risk\n'
        f'{site_risk}\n\n'
        '3. Documentation Status\n'
        f'{documentation}\n\n'
        '4. Cost / Approval Status\n'
        f'{cost}\n\n'
        '5. Recommended Bauleiter Actions Today\n'
        '- Identify the blocked segment and assign one owner.\n'
        '- Confirm permit / traffic safety / utility risk before work continues.\n'
        '- Request missing documentation evidence from the crew or subcontractor.\n'
        '- Escalate cost or claim-related items before approving any payment.\n'
        '- Update the project status board before end of day.'
    )


def security_and_evaluation_guard(query: str) -> str:
    """Runs a local safety and evaluation guard before recommendations are trusted.

    Args:
        query: User request or proposed agent action.

    Returns:
        Safety review result.
    """
    query_lower = query.lower()

    blocked_terms = [
        'delete all',
        'remove all',
        'drop table',
        'upload secret',
        'show api key',
        'print api key',
        'bypass approval',
        'ignore safety',
        'disable guard',
        'deploy to cloud',
        'gcloud run deploy',
        'billing',
    ]

    hits = [term for term in blocked_terms if term in query_lower]

    if hits:
        return (
            'SECURITY_GUARD_RESULT\n'
            'status: BLOCKED\n'
            f'blocked_terms: {hits}\n'
            'reason: The request contains potentially unsafe operations or production/cloud actions.\n'
            'next_step: Ask for explicit human approval and perform a separate security review.'
        )

    return (
        'SECURITY_GUARD_RESULT\n'
        'status: PASSED_LOCAL_SAFE_MODE\n'
        'reason: No destructive, secret-exposing, or cloud-deployment action detected.\n'
        'next_step: Continue with local analysis only.'
    )


def route_to_specialist_agent(query: str) -> str:
    """Simulates A2A-style routing to specialist agents.

    This is a local prototype. It does not contact external agents.
    It demonstrates how the project can evolve into Agent2Agent architecture.

    Args:
        query: User request.

    Returns:
        A simulated specialist routing decision.
    """
    query_lower = query.lower()

    if any(word in query_lower for word in ['permit', 'blocked', 'risk', 'unsafe', 'traffic', 'gas', 'water']):
        specialist = A2A_SPECIALISTS['site_risk']
    elif any(word in query_lower for word in ['photo', 'measurement', 'documentation', 'gis', 'redline', 'aufmaß']):
        specialist = A2A_SPECIALISTS['documentation']
    elif any(word in query_lower for word in ['invoice', 'cost', 'approval', 'budget', 'nachtrag', 'claim']):
        specialist = A2A_SPECIALISTS['cost']
    elif any(word in query_lower for word in ['daily', 'brief', 'status', 'summary', 'today']):
        specialist = A2A_SPECIALISTS['daily_brief']
    else:
        specialist = A2A_SPECIALISTS['security']

    return (
        'A2A_ROUTING_SIMULATION\n'
        f'specialist_agent: {specialist}\n'
        'mode: local_simulation_only\n'
        'note: This prototype is A2A-ready but does not call external agents yet.'
    )


root_agent = Agent(
    name='infratwin_control_center_agent',
    model=Gemini(
        model='gemini-flash-latest',
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        'You are InfraTwin Agent Control Center, a local AI agent prototype for FTTH and 5G infrastructure project coordination.\n\n'
        'Your role is to support a Bauleiter / Project Manager by triaging site risks, documentation gaps, cost approval issues, and daily project priorities.\n\n'
        'Always follow these rules:\n'
        '1. Use security_and_evaluation_guard before giving operational recommendations.\n'
        '2. Use analyze_site_risk for blocked segments, permits, traffic safety, utilities, subcontractor issues, or restoration delays.\n'
        '3. Use check_documentation_readiness for photos, measurements, redlines, GIS, Aufmaß, or as-built documentation.\n'
        '4. Use triage_cost_or_approval for invoices, claims, Nachtrag, approval, material cost, or budget questions.\n'
        '5. Use create_daily_project_brief when the user asks for a daily plan, project summary, or what to do today.\n'
        '6. Use route_to_specialist_agent to explain which future specialist agent would handle the task in an A2A architecture.\n'
        '7. Never expose secrets, API keys, credentials, or environment variables.\n'
        '8. Never run cloud deployment, billing, gcloud, destructive file, or production actions.\n'
        '9. If information is missing, ask for segment ID, street, current status, blocker, responsible crew, and available documentation.\n'
        '10. Keep recommendations practical, field-oriented, and suitable for infrastructure project coordination.\n\n'
        'Response style:\n'
        '- Start with a short operational verdict.\n'
        '- Then give risk level, affected area, recommended next actions, and owner suggestions.\n'
        '- If human approval is needed, say so clearly.\n'
        '- Keep the language concise and decision-oriented.'
    ),
    tools=[
        security_and_evaluation_guard,
        analyze_site_risk,
        check_documentation_readiness,
        triage_cost_or_approval,
        create_daily_project_brief,
        route_to_specialist_agent,
    ],
)


app = App(
    root_agent=root_agent,
    name='app',
)