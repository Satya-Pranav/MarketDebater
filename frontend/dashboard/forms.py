"""Forms for the MarketDebater dashboard."""

from __future__ import annotations

import re

from django import forms


ROUND_CHOICES = [
    (1, "1 round (opening only)"),
    (2, "2 rounds (case + rebuttal)"),
    (3, "3 rounds (case + rebuttal + closing)"),
    (4, "4 rounds"),
    (5, "5 rounds"),
]

# Single source of truth for ticker shape — reused by the form and by the
# scan-now POST handler. Anchored fullmatch elsewhere.
TICKER_REGEX = re.compile(r"[A-Z0-9]{1,10}(\.[A-Z]{1,2})?")
MAX_SCAN_TICKERS = 25  # cap to prevent quota / runtime abuse from the scan POST


class TickerForm(forms.Form):
    """Form for submitting a stock ticker symbol."""

    ticker = forms.CharField(
        label="Enter US ticker (e.g., AAPL)",
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "ticker-input",
                "placeholder": "Pick or type a ticker (e.g. AAPL)",
                # `list=` binds the input to the <datalist id="ticker-options">
                # rendered by the home template. Gives us a native dropdown +
                # filter-as-you-type with zero JS and proper mobile pickers.
                # `autocomplete=off` would suppress the dropdown on some
                # browsers, so we leave it on.
                "list": "ticker-options",
            }
        ),
    )
    rounds = forms.TypedChoiceField(
        label="Debate rounds",
        choices=ROUND_CHOICES,
        coerce=int,
        initial=2,
        required=False,
        widget=forms.Select(attrs={"class": "rounds-select"}),
    )

    def clean_ticker(self) -> str:
        """Validate ticker format (US plain symbol; legacy NSE/BSE suffix still allowed)."""
        ticker = self.cleaned_data.get("ticker", "").strip().upper()

        if not ticker:
            raise forms.ValidationError("Please enter a ticker symbol.")

        # Accept US-style plain tickers (AAPL, GOOGL, BRK.B) and the legacy NSE/BSE
        # suffix shape (RELIANCE.NS) — the backend pivoted to US but the regex
        # stays permissive so old bookmarks don't 400.
        if not TICKER_REGEX.fullmatch(ticker):
            raise forms.ValidationError(
                "Invalid ticker format. Use a US symbol like AAPL or MSFT."
            )

        return ticker
