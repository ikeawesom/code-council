"""Build graph.json: document <-> clause <-> concept <-> parliament_item edges.

Concept nodes are the hubs that make retrieval cheap: a parliament item about
"notice period" reaches every clause tagged with that concept without a full scan.
"""
# TODO(M1): build_graph() -> vault/graph.json
