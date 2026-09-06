"""Question-shape detectors: cheap regex checks, never a model call.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import re
from datetime import datetime

# §16: detects count/enumeration questions to widen retrieval, not to add a
# reasoning step -- a structured aggregation LLM pass was tried by a published
# 90.8%-LongMemEval system and made accuracy WORSE (91.2%->86.0%; "each
# additional LLM call is an opportunity to corrupt a correct answer"). A plain
# regex against the raw question, deliberately not a model call.
_COUNT_QUERY_PATTERN = re.compile(
    r"\bhow (many|much)\b|\btotal\b|\bcount\b|\baverage\b|\ball (of )?(the|my)\b|\bevery\b|"
    r"\blist all\b|\bhow often\b|\bnumber of\b|\bsum\b",
    re.IGNORECASE,
)


def looks_like_count_query(question: str) -> bool:
    return bool(_COUNT_QUERY_PATTERN.search(question))


# §20: duration/elapsed-time questions get extra in-prompt arithmetic guidance.
# Requires a time UNIT (or an explicit elapsed-time phrase) so that "how many
# properties" / "how many subscriptions" stay count queries and never pick this
# up -- the two heuristics are deliberately disjoint on the cases measured.
_DURATION_QUERY_PATTERN = re.compile(
    r"\bhow long\b|\bhow much time\b|"
    r"\bhow many\s+(days|weeks|months|years|hours|minutes)\b|"
    r"\b(days|weeks|months|years|hours)\s+(ago|passed|elapsed|between|since)\b|"
    r"\bhow many\s+\w+\s+(ago|passed|elapsed)\b|"
    r"\b(since|between)\b.*\b(and|until)\b.*\b(days|weeks|months|years)\b",
    re.IGNORECASE,
)


def looks_like_duration_query(question: str) -> bool:
    return bool(_DURATION_QUERY_PATTERN.search(question))


def format_number(value: float) -> str:
    """Whole numbers print without a trailing '.0' (e.g. gold answers say '4
    days', never '4.0 days')."""
    return str(int(value)) if value == int(value) else str(value)


def date_diff_in_unit(start_date: str, end_date: str, unit: str) -> float | None:
    """Parse two ISO (YYYY-MM-DD) dates and return |end - start| expressed in
    `unit`. Returns None on any unparseable input -- the caller then leaves
    the model's own answer unchanged rather than risk a bogus correction (see
    DurationAnswer's docstring for the two live failure modes this replaced:
    garbled date-as-float operands, and a stated_result/unit mismatch)."""
    try:
        start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    if start > end:
        start, end = end, start
    if unit == "days":
        return float((end - start).days)
    if unit == "weeks":
        return (end - start).days / 7.0
    if unit == "months":
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day < start.day:
            months -= 1
        return float(max(months, 0))
    if unit == "years":
        years = end.year - start.year
        if (end.month, end.day) < (start.month, start.day):
            years -= 1
        return float(max(years, 0))
    return None
