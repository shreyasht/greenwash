"""astroturf — deterministic verification for AI coding agents.

Answers one question by experiment, not inference:
    does the source change, on its own, still satisfy the checks?

No LLM, no network in this package (NFR-1, NFR-2). Python stdlib only (NFR-3).
"""

__version__ = "0.3.0"

# Bumped only on a breaking change to the JSON report (see REQUIREMENTS.md §6.7).
JSON_SCHEMA_VERSION = 1
