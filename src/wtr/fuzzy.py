"""Fuzzy search helpers for branch filtering."""

from thefuzz import fuzz


def is_subsequence(query: str, text: str) -> bool:
    """Check if query is a subsequence of text (chars in order, not necessarily adjacent)."""
    it = iter(text)
    return all(char in it for char in query)


def fuzzy_filter(
    items: list[str],
    query: str,
    threshold: int = 95,
) -> list[tuple[str, int]]:
    """
    Filter items by fuzzy matching against query.

    Returns list of (item, score) tuples sorted by score descending.
    Only items with score >= threshold are returned.
    """
    if not query:
        return [(item, 100) for item in items]

    query_lower = query.lower()
    results = []

    for item in items:
        item_lower = item.lower()

        # Exact substring match gets highest priority
        if query_lower in item_lower:
            results.append((item, 100))
            continue

        # Subsequence match (chars in order, e.g. "ES5" matches "ENS-325")
        if is_subsequence(query_lower, item_lower):
            results.append((item, 95))
            continue

        # Fuzzy match using partial ratio for substring-like matching
        score = fuzz.partial_ratio(query_lower, item_lower)

        # Also consider token sort for multi-word queries
        token_score = fuzz.token_sort_ratio(query_lower, item_lower)
        score = max(score, token_score)

        if score >= threshold:
            results.append((item, score))

    # Sort by score descending, then alphabetically
    results.sort(key=lambda x: (-x[1], x[0]))

    return results


def fuzzy_match(items: list[str], query: str, threshold: int = 95) -> list[str]:
    """
    Filter items by fuzzy matching, returning only item names.

    Convenience wrapper around fuzzy_filter.
    """
    return [item for item, _ in fuzzy_filter(items, query, threshold)]
