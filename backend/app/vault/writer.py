"""Write the Obsidian-compatible markdown vault.

Layout:
  vault/documents/<slug>.md    frontmatter + `## <n> <heading>` per clause
  vault/concepts/<slug>.md     graph hubs, e.g. "Notice Period"
  vault/parliament/<date>-<slug>.md
  vault/index.md

Clauses link to concepts with [[wikilinks]] so the vault opens natively in
Obsidian - the knowledge base is plain files, not a database blob.
"""
# TODO(M1): write_document(), write_concept(), write_parliament_item(), apply_clause_edit()
