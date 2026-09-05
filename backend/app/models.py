"""SQLModel tables.

users            - seeded demo lawyers (no auth; a switcher picks the active one)
documents        - one row per contract/policy in the vault
clauses          - one row per addressable clause, anchored as <doc-slug>#<anchor>
parliament_items - one row per scraped Hansard item
proposals        - (parliament_item x clause) -> impacted? severity, rationale, suggested text
edits            - applied changes, before/after, who and when
notifications    - fan-out to other users linked to an edited document
"""
# TODO(M1): define the tables above.
