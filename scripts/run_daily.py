"""The 07:00 pipeline, runnable by hand (this is what the demo invokes).

    python scripts/run_daily.py [--date YYYY-MM-DD] [--offline]

scrape -> normalize into vault/parliament/ -> retrieve candidate clauses ->
LLM impact assessment -> write proposals. Prints a summary table.
"""
# TODO(M2/M3)
