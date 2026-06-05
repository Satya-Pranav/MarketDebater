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
