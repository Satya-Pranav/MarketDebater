"""Forms for the MarketDebater dashboard."""

from __future__ import annotations

import re

from django import forms


class TickerForm(forms.Form):
    """Form for submitting a stock ticker symbol."""
    
    ticker = forms.CharField(
        label="Enter NSE ticker (e.g., RELIANCE.NS)",
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "ticker-input",
                "placeholder": "e.g. RELIANCE.NS",
                "autocomplete": "off",
            }
        ),
    )

    def clean_ticker(self) -> str:
        """Validate ticker format (NSE/BSE style: SYMBOL.NS or SYMBOL.BO)."""
        ticker = self.cleaned_data.get("ticker", "").strip().upper()
        
        if not ticker:
            raise forms.ValidationError("Please enter a ticker symbol.")
        
        # Allow NSE (.NS) or BSE (.BO) suffix, or custom format
        if not re.fullmatch(r"[A-Z0-9]{1,10}(\.[A-Z]{2})?", ticker):
            raise forms.ValidationError(
                "Invalid ticker format. Use format like RELIANCE.NS or TCS.NS"
            )
        
        return ticker
