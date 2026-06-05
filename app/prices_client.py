"""Price + technicals client.

Pulls EOD OHLCV for a US ticker via yfinance and computes technical indicators
in pure pandas (no pandas-ta, to avoid numpy-2 incompatibilities). The structured
snapshot returned here is the **ground-truth** that the Chair fact-checks agent
claims against.

CLI:  python -m app.prices_client AAPL
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


# --------------------------------------------------------------------------- #
# Technical indicators (pure pandas)                                          #
# --------------------------------------------------------------------------- #
def _sma(s: pd.Series, n: int) -> float:
    return float(s.rolling(n).mean().iloc[-1]) if len(s) >= n else float("nan")


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> float:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def _macd(close: pd.Series) -> dict[str, float]:
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd_line, 9)
    hist = macd_line - signal
    return {
        "macd": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal.iloc[-1]), 4),
        "histogram": round(float(hist.iloc[-1]), 4),
    }


def _bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> dict[str, float]:
    if len(close) < n:
        return {"upper": float("nan"), "middle": float("nan"), "lower": float("nan")}
    mid = close.rolling(n).mean().iloc[-1]
    std = close.rolling(n).std().iloc[-1]
    return {
        "upper": round(float(mid + k * std), 2),
        "middle": round(float(mid), 2),
        "lower": round(float(mid - k * std), 2),
    }


# --------------------------------------------------------------------------- #
# Snapshot                                                                    #
# --------------------------------------------------------------------------- #
@dataclass
class MarketSnapshot:
    ticker: str
    company: str
    as_of: str
    currency: str
    price: float
    prev_close: float
    change_pct: float
    day_high: float
    day_low: float
    week52_high: float
    week52_low: float
    volume: int
    avg_volume_20d: float
    volume_vs_avg_pct: float
    rsi_14: float
    macd: dict[str, float]
    sma_20: float
    sma_50: float
    sma_200: float
    bollinger: dict[str, float]
    pe_ratio: float | None = None
    market_cap: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    """Fetch 1y EOD OHLCV + technicals for a US ticker (e.g. 'AAPL')."""
    tk = yf.Ticker(ticker)
    hist = tk.history(period="1y", interval="1d")
    if hist.empty:
        raise ValueError(f"No price data for '{ticker}'. Check the symbol.")

    close = hist["Close"].dropna()
    info: dict[str, Any] = {}
    try:
        info = tk.info or {}
    except Exception:  # yfinance .info is flaky; degrade gracefully
        info = {}

    price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else price
    avg_vol_20 = float(hist["Volume"].tail(20).mean())
    last_vol = int(hist["Volume"].iloc[-1])

    return MarketSnapshot(
        ticker=ticker,
        company=info.get("longName") or info.get("shortName") or ticker,
        as_of=str(hist.index[-1].date()),
        currency=info.get("currency", "USD"),
        price=round(price, 2),
        prev_close=round(prev_close, 2),
        change_pct=round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        day_high=round(float(hist["High"].iloc[-1]), 2),
        day_low=round(float(hist["Low"].iloc[-1]), 2),
        week52_high=round(float(close.tail(252).max()), 2),
        week52_low=round(float(close.tail(252).min()), 2),
        volume=last_vol,
        avg_volume_20d=round(avg_vol_20, 0),
        volume_vs_avg_pct=round((last_vol - avg_vol_20) / avg_vol_20 * 100, 1) if avg_vol_20 else 0.0,
        rsi_14=round(_rsi(close), 2),
        macd=_macd(close),
        sma_20=round(_sma(close, 20), 2),
        sma_50=round(_sma(close, 50), 2),
        sma_200=round(_sma(close, 200), 2),
        bollinger=_bollinger(close),
        pe_ratio=info.get("trailingPE"),
        market_cap=info.get("marketCap"),
    )


def _main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    s = get_market_snapshot(ticker).to_dict()
    print(f"\n=== {s['company']} ({s['ticker']}) — as of {s['as_of']} ===")
    print(f"  Price {s['currency']} {s['price']}  ({s['change_pct']:+}% vs prev close)")
    print(f"  52w range: {s['week52_low']} – {s['week52_high']}")
    print(f"  RSI(14): {s['rsi_14']}   MACD: {s['macd']}")
    print(f"  SMA 20/50/200: {s['sma_20']} / {s['sma_50']} / {s['sma_200']}")
    print(f"  Bollinger: {s['bollinger']}")
    print(f"  Volume vs 20d avg: {s['volume_vs_avg_pct']:+}%   P/E: {s['pe_ratio']}")
    assert 0 <= s["rsi_14"] <= 100, "RSI out of range"
    assert s["price"] > 0, "Non-positive price"
    print("\nOK: snapshot valid, RSI in range.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
