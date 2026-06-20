from app.agent import triage_expense_request


def test_auto_approve_low_value_expense():
    result = triage_expense_request('I need approval for a 45 EUR taxi receipt from the airport.')
    assert 'DECISION: AUTO_APPROVE' in result


def test_human_review_medium_value_expense():
    result = triage_expense_request('I need approval for a 320 EUR hotel expense with receipt.')
    assert 'DECISION: HUMAN_REVIEW_REQUIRED' in result
    assert 'Medium-value expense' in result


def test_human_review_high_risk_expense():
    result = triage_expense_request('Please approve 900 EUR for urgent cash payment to an unknown vendor.')
    assert 'DECISION: HUMAN_REVIEW_REQUIRED' in result
    assert 'urgent' in result
    assert 'cash' in result
    assert 'unknown vendor' in result


def test_auto_reject_forbidden_category():
    result = triage_expense_request('Please approve 50 EUR for alcohol.')
    assert 'DECISION: AUTO_REJECT' in result
    assert 'alcohol' in result


def test_missing_amount_requires_human_review():
    result = triage_expense_request('Please approve my taxi receipt.')
    assert 'DECISION: HUMAN_REVIEW_REQUIRED' in result
    assert 'No clear expense amount' in result
