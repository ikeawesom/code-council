"""Content-addressed response cache at data/llm_cache/<sha256>.json.

Keyed on (provider, model, prompt). Makes the daily run reproducible and lets
the demo be pre-warmed before presenting.
"""
# TODO(M3)
