"""Ticker → company name lookup for the dropdown autocomplete.

Kept as a static mapping for the curated 25-ticker watchlist — small enough that
hardcoding is simpler than parsing the watchlist file + a separate name source.
When the universe grows (Nasdaq 100, S&P 500) move this behind a CSV reader.
"""
from __future__ import annotations


COMPANIES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corporation",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "MA": "Mastercard Inc.",
    "BAC": "Bank of America Corp.",
    "GS": "Goldman Sachs Group Inc.",
    "UNH": "UnitedHealth Group Inc.",
    "JNJ": "Johnson & Johnson",
    "LLY": "Eli Lilly and Company",
    "PFE": "Pfizer Inc.",
    "WMT": "Walmart Inc.",
    "COST": "Costco Wholesale Corp.",
    "HD": "Home Depot Inc.",
    "KO": "Coca-Cola Company",
    "PG": "Procter & Gamble Co.",
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "CAT": "Caterpillar Inc.",
    "NFLX": "Netflix Inc.",
}


def ticker_options() -> list[tuple[str, str]]:
    """Return `[(ticker, "TICKER — Company Name")]` sorted by ticker.

    The display string is what shows in the dropdown; the value submitted by the
    form is just the ticker. Native <datalist> uses the option value when typed.
    """
    return sorted(((t, f"{t} — {name}") for t, name in COMPANIES.items()), key=lambda x: x[0])
