"""Split a parsed document into clauses with stable anchors.

Anchors must survive re-ingest and edits, because proposals, edits and graph
edges all reference them: "warehouse-lease#7-2".
"""
# TODO(M1): split_clauses(parsed) -> list[Clause]
