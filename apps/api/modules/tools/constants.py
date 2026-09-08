# Same tier vocabulary as policy/questions.py's q3_9_default_tier options -
# not redefined there as an importable constant, so kept in sync here by
# convention (both lists are small and rarely change).
TIER_KEYS = ("restricted", "confidential", "internal", "public")

# Milestone 18 (Request forms) - the tool-request wizard's "Use case" step
# won't advance past this word count, enforced server-side too (defense in
# depth, same "server is the real boundary" split used everywhere else).
MIN_USE_CASE_WORDS = 150
