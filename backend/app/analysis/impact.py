"""The LLM judge.

Input:  parliament item text + one candidate clause + its document context
Output: {impacted: bool, severity: low|medium|high, rationale: str,
         suggested_clause_text: str | null}

Only impacted results become proposals. The rationale is what the lawyer reads
first, so it must cite the specific part of the parliamentary item.
"""
# TODO(M3): assess(item, clause) -> ImpactAssessment
