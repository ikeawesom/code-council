"""Hybrid retrieval: BM25 over clause text + concept-tag overlap from the graph.

This is the cost filter. Only the top-K (default 5) candidate clauses per
parliament item ever reach the LLM, which keeps a full daily run cheap enough
to re-run live on stage.
"""
# TODO(M3): candidates(item, k=5) -> list[Clause]
