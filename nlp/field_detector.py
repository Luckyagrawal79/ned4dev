from difflib import SequenceMatcher


# Ordered longest first so "churn deviation" matches before "deviation"
VALUE_FIELDS = [
    "churn_deviation",
    "churn_previous",
    "churn_current",
    "deviation",
    "previous",
    "current",
]


def detect_value_field(query_lower):
    """
    Detect which data field the user wants to plot.
    Returns dict with:
      - match: the field name
      - confident: True if exact/high match, False if suggestion
      - suggestions: list of all fields (only when not confident)
    """

    # Step 1: Exact match (longest first)
    for f in VALUE_FIELDS:
        # Match both "churn_deviation" and "churn deviation"
        if f in query_lower or f.replace("_", " ") in query_lower:
            return {"match": f, "confident": True}

    # Step 2: Fuzzy match against query words
    query_words = query_lower.split()

    # Build variants: "churn_deviation" and "churn deviation" both map to "churn_deviation"
    field_variants = {}
    for f in VALUE_FIELDS:
        field_variants[f] = f
        field_variants[f.replace("_", " ")] = f
        # Also add individual words for single-word fields
        for part in f.split("_"):
            if part not in field_variants:
                field_variants[part] = f

    best_match = None
    best_score = 0

    # Ignore common non-field words
    ignore_words = ['plot', 'trend', 'chart', 'graph', 'pie', 'bar', 'barchart',
                    'show', 'display', 'the', 'for', 'and', 'past', 'last',
                    'weeks', 'week']

    for word in query_words:
        if word in ignore_words or len(word) < 3:
            continue
        for variant, field in field_variants.items():
            score = SequenceMatcher(None, word, variant).ratio()
            if score > best_score:
                best_score = score
                best_match = field

    if best_match and best_score >= 0.8:
        # High confidence — use it
        return {"match": best_match, "confident": True}
    elif best_match and best_score >= 0.6:
        # Not sure — suggest options
        return {"match": best_match, "confident": False, "suggestions": VALUE_FIELDS}

    # No match — default to current
    return {"match": "current", "confident": True}