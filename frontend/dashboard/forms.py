"""Forms for the MarketDebater dashboard."""

from __future__ import annotations

import re

from django import forms

from backend.marketdebater import config


class TickerForm(forms.Form):
    ticker = forms.ChoiceField(
        label="Select a stock",
        choices=[(ticker, ticker) for ticker in config.DEFAULT_TICKERS],
        widget=forms.Select(attrs={"class": "ticker-input"}),
    )

    def clean_ticker(self) -> str:
        ticker = self.cleaned_data["ticker"].strip().upper()
        if not ticker:
            raise forms.ValidationError("Enter a ticker such as RELIANCE.NS.")
        if not re.fullmatch(r"[A-Z0-9._-]+", ticker):
            raise forms.ValidationError("Use a valid NSE/BSE style ticker.")
        return ticker
