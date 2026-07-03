"""Known-leaks fixture for canon_audit.sh PY_STRING_CONCAT self-test.

Every adjacent-string-literal pair below MUST be caught by the
audit's audit_python_strings function. If a pair stops matching,
either the cross-line flattening regex broke or a pattern family
got weakened. Both ship together with their corresponding text
fixture entries in canon_audit_known_leaks.txt.

This file is excluded from regular audits (both line-based and
Python-aware) via the EXCLUDES list in canon_audit.sh; the
self-test exercises it explicitly.
"""

# RIGID family: the operator's <strategic-noun> compound straddling lines.
GUIDANCE_LEAK = (
    "Does not compose with the operator's "
    "methodology unless wired explicitly."
)

# PRIVATE_FILES family: STRATEGY DD-N straddling lines.
DOC_LEAK = (
    "See STRATEGY "
    "DD-1 for the wrapper rationale."
)

# RIGID family: empire-modifier compound straddling lines.
POSITIONING_LEAK = (
    "The empire "
    "positioning section."
)

# CANON_VOCAB_EXTENDED family: construct-honesty <head> straddling lines.
HONESTY_LEAK = (
    "Pay the construct-honesty "
    "tax in every payload."
)

# RIGID family: docs/internal/ straddling lines (rare shape but possible).
INTERNAL_PATH_LEAK = (
    "Result publishes to "
    "docs/internal/AUDIT.md per the protocol."
)
