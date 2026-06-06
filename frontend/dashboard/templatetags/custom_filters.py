"""Custom template filters for the MarketDebater dashboard."""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key.
    
    Usage: {{ dict|get_item:"key" }}
    """
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def mul(value, arg):
    """Multiply a value by an argument.
    
    Usage: {{ value|mul:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def floatformat(value, arg=1):
    """Format a float to a specific number of decimal places.

    Usage: {{ value|floatformat:2 }}
    """
    try:
        decimals = int(arg) if arg else 1
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return value


@register.filter
def round_label(round_num, total_rounds):
    """Map a 1-indexed round number to its phase label given the debate length.

    1 round: ``Round 1`` (only one — no case/rebuttal split)
    2 rounds: Case · Rebuttal
    3+ rounds: Case · Rebuttal · ... · Closing (last)
    """
    try:
        r = int(round_num)
        n = int(total_rounds)
    except (TypeError, ValueError):
        return f"Round {round_num}"
    if n <= 1:
        return f"Round {r}"
    if r == 1:
        return f"Round 1 · Case"
    if r == n:
        return f"Round {r} · Closing"
    if r == 2:
        return f"Round 2 · Rebuttal"
    return f"Round {r}"


@register.filter
def starts_with(value, prefix):
    """True when the string starts with the given prefix. Tolerates non-strings."""
    if not isinstance(value, str):
        return False
    return value.startswith(prefix)


@register.filter
def pct_of(value, total):
    """Return value/total as a percent string ('31%'). Used for timing bars."""
    try:
        v = float(value)
        t = float(total)
        if t <= 0:
            return "0%"
        return f"{(v / t) * 100:.0f}%"
    except (TypeError, ValueError):
        return "0%"
