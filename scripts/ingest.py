"""Ingest every document in data/inbox/ into the vault + database.

    python scripts/ingest.py [--force]

parse -> chunk into clauses -> LLM-tag with legal concepts -> write vault
markdown -> rebuild graph.json. Idempotent: re-running updates in place.
"""
# TODO(M1)
