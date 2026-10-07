"""Alpha Vantage client with caching, rate limiting, retries and a mock mode.

Mock mode (no key, or ALPHA_VANTAGE_MOCK=true) returns deterministic synthetic
data that is clearly labelled `"source": "mock"` so it is never mistaken for a
live quote. Live errors are never silently replaced with mock data.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from finlit.config import get_settings

log = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
MOCK_SOURCE = "mock (sample data, not live)"
LIVE_SOURCE = "Alpha Vantage"


class MarketDataError(RuntimeError):
    """Base error; message is safe to show to users."""


class RateLimitError(MarketDataError):
    pass


class SymbolNotFoundError(MarketDataError):
    pass


class _TransientError(Exception):
    pass


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[tuple, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple):
        with self._lock:
            hit = self._data.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
            self._data.pop(key, None)
            return None

    def set(self, key: tuple, value, ttl: float) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class _RateLimiter:
    """Sliding-window limiter: at most `calls` per `period` seconds (free tier is ~5/min)."""

    def __init__(self, calls: int = 5, period: float = 60.0, max_wait: float = 15.0) -> None:
        self.calls, self.period, self.max_wait = calls, period, max_wait
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._stamps and now - self._stamps[0] > self.period:
                self._stamps.popleft()
            if len(self._stamps) >= self.calls:
                wait = self.period - (now - self._stamps[0])
                if wait > self.max_wait:
                    raise RateLimitError(
                        "Alpha Vantage per-minute limit reached; please try again in about a minute."
                    )
                time.sleep(max(0.0, wait))
            self._stamps.append(time.monotonic())


TTL = {"GLOBAL_QUOTE": 60, "TIME_SERIES_DAILY": 3600, "OVERVIEW": 86400, "NEWS_SENTIMENT": 900}


class AlphaVantageClient:
    def __init__(self, api_key: str | None = None, mock: bool | None = None,
                 session: requests.Session | None = None, timeout: float = 15.0) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.alpha_vantage_api_key
        self.mock = settings.use_mock_market_data if mock is None else mock
        if not self.api_key:
            self.mock = True
        self.session = session or requests.Session()
        self.timeout = timeout
        self.cache = _TTLCache()
        self.limiter = _RateLimiter()

    # ------------------------------------------------------------------ http
    @retry(retry=retry_if_exception_type(_TransientError), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=0.5, max=4), reraise=True)
    def _get(self, params: dict) -> dict:
        self.limiter.acquire()
        try:
            resp = self.session.get(BASE_URL, params={**params, "apikey": self.api_key},
                                    timeout=self.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise _TransientError(str(exc)) from exc
        if resp.status_code >= 500:
            raise _TransientError(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise MarketDataError(f"Alpha Vantage returned HTTP {resp.status_code}.")
        try:
            data = resp.json()
        except ValueError as exc:
            raise MarketDataError("Alpha Vantage returned a non-JSON response.") from exc
        return self._check_payload(data)

    @staticmethod
    def _check_payload(data: dict) -> dict:
        if not isinstance(data, dict):
            raise MarketDataError("Unexpected Alpha Vantage response format.")
        for key in ("Note", "Information"):
            if key in data and len(data) <= 2:
                raise RateLimitError(
                    "Alpha Vantage rate limit reached (free tier: 25 requests/day, 5/minute). "
                    "Try again later or enable ALPHA_VANTAGE_MOCK=true for sample data."
                )
        if "Error Message" in data:
            raise SymbolNotFoundError("Alpha Vantage could not find that symbol or request.")
        return data

    def _cached(self, function: str, key: str, params: dict) -> dict:
        ck = (function, key)
        hit = self.cache.get(ck)
        if hit is not None:
            return hit
        data = self._get({"function": function, **params})
        self.cache.set(ck, data, TTL.get(function, 300))
        return data

    # ------------------------------------------------------------------ api
    def get_quote(self, symbol: str) -> dict:
        symbol = _clean_symbol(symbol)
        if self.mock:
            return _mock_quote(symbol)
        data = self._cached("GLOBAL_QUOTE", symbol, {"symbol": symbol})
        q = data.get("Global Quote") or {}
        if not q.get("05. price"):
            raise SymbolNotFoundError(f"No quote found for '{symbol}'.")
        return {
            "symbol": q.get("01. symbol", symbol),
            "price": _f(q.get("05. price")),
            "open": _f(q.get("02. open")),
            "high": _f(q.get("03. high")),
            "low": _f(q.get("04. low")),
            "previous_close": _f(q.get("08. previous close")),
            "change": _f(q.get("09. change")),
            "change_percent": _f(str(q.get("10. change percent", "0")).rstrip("%")),
            "volume": int(_f(q.get("06. volume")) or 0),
            "latest_trading_day": q.get("07. latest trading day"),
            "source": LIVE_SOURCE,
        }

    def get_quotes(self, symbols: list[str]) -> dict:
        """Quotes for several symbols; per-symbol errors are reported, not raised."""
        out: dict = {"quotes": [], "errors": []}
        seen = []
        for s in symbols:
            s = _clean_symbol(s)
            if s and s not in seen:
                seen.append(s)
        for s in seen[:10]:
            try:
                out["quotes"].append(self.get_quote(s))
            except RateLimitError as exc:
                out["errors"].append({"symbol": s, "error": str(exc)})
                break
            except MarketDataError as exc:
                out["errors"].append({"symbol": s, "error": str(exc)})
        return out

    def get_daily_closes(self, symbol: str, days: int = 100) -> dict:
        """Oldest-to-newest closing prices."""
        symbol = _clean_symbol(symbol)
        if self.mock:
            return _mock_series(symbol, days)
        data = self._cached("TIME_SERIES_DAILY", symbol, {"symbol": symbol, "outputsize": "compact"})
        series = data.get("Time Series (Daily)") or {}
        if not series:
            raise SymbolNotFoundError(f"No price history for '{symbol}'.")
        dates = sorted(series)[-days:]
        return {
            "symbol": symbol,
            "dates": dates,
            "closes": [_f(series[d].get("4. close")) for d in dates],
            "source": LIVE_SOURCE,
        }

    def get_overview(self, symbol: str) -> dict:
        symbol = _clean_symbol(symbol)
        if self.mock:
            return _mock_overview(symbol)
        d = self._cached("OVERVIEW", symbol, {"symbol": symbol})
        if not d.get("Symbol"):
            raise SymbolNotFoundError(f"No company overview for '{symbol}'.")
        return {
            "symbol": d.get("Symbol"),
            "name": d.get("Name"),
            "sector": d.get("Sector"),
            "industry": d.get("Industry"),
            "market_cap": _f(d.get("MarketCapitalization")),
            "pe_ratio": _f(d.get("PERatio")),
            "dividend_yield": _f(d.get("DividendYield")),
            "beta": _f(d.get("Beta")),
            "week52_high": _f(d.get("52WeekHigh")),
            "week52_low": _f(d.get("52WeekLow")),
            "description": (d.get("Description") or "")[:600],
            "source": LIVE_SOURCE,
        }

    def get_news(self, tickers: list[str] | None = None, topics: str | None = None, limit: int = 8) -> dict:
        tickers = [_clean_symbol(t) for t in (tickers or []) if _clean_symbol(t)]
        if self.mock:
            return _mock_news(tickers, limit)
        params: dict = {"limit": 50, "sort": "LATEST"}
        if tickers:
            params["tickers"] = ",".join(tickers[:5])
        if topics:
            params["topics"] = topics
        data = self._cached("NEWS_SENTIMENT", f"{params.get('tickers')}|{topics}", params)
        items = []
        for it in (data.get("feed") or [])[:limit]:
            items.append({
                "title": it.get("title"),
                "source": it.get("source"),
                "url": it.get("url"),
                "published": it.get("time_published"),
                "summary": (it.get("summary") or "")[:500],
                "sentiment_label": it.get("overall_sentiment_label"),
                "sentiment_score": _f(it.get("overall_sentiment_score")),
                "tickers": [t.get("ticker") for t in it.get("ticker_sentiment", [])][:5],
            })
        return {"articles": items, "source": LIVE_SOURCE}


# ---------------------------------------------------------------- helpers
def _f(v) -> float | None:
    try:
        if v in (None, "", "None", "-"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean_symbol(s: str) -> str:
    return "".join(ch for ch in str(s).upper().strip() if ch.isalnum() or ch in ".-")[:12]


def _seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)


def _mock_series(symbol: str, days: int = 100) -> dict:
    seed = _seed(symbol)
    base = 20 + seed % 480
    drift = ((seed >> 4) % 11 - 3) / 10000
    vol = 0.008 + ((seed >> 8) % 15) / 1000
    closes, price = [], float(base)
    for i in range(days):
        shock = math.sin(seed % 97 + i * 1.7) * vol + math.cos(i * 0.31 + seed % 13) * vol / 2
        price = max(1.0, price * (1 + drift + shock))
        closes.append(round(price, 2))
    today = date.today()
    dates = [(today - timedelta(days=days - i)).isoformat() for i in range(days)]
    return {"symbol": symbol, "dates": dates, "closes": closes, "source": MOCK_SOURCE}


def _mock_quote(symbol: str) -> dict:
    s = _mock_series(symbol, 30)["closes"]
    price, prev = s[-1], s[-2]
    return {
        "symbol": symbol, "price": price, "open": prev, "high": round(max(price, prev) * 1.01, 2),
        "low": round(min(price, prev) * 0.99, 2), "previous_close": prev,
        "change": round(price - prev, 2), "change_percent": round((price / prev - 1) * 100, 3),
        "volume": 1_000_000 + _seed(symbol) % 9_000_000,
        "latest_trading_day": date.today().isoformat(), "source": MOCK_SOURCE,
    }


def _mock_overview(symbol: str) -> dict:
    seed = _seed(symbol)
    sectors = ["TECHNOLOGY", "HEALTHCARE", "FINANCIALS", "ENERGY", "CONSUMER", "INDUSTRIALS"]
    return {
        "symbol": symbol, "name": f"{symbol} (sample company)", "sector": sectors[seed % len(sectors)],
        "industry": "Sample", "market_cap": float(1e9 * (1 + seed % 900)), "pe_ratio": round(8 + seed % 40, 1),
        "dividend_yield": round((seed % 40) / 1000, 3), "beta": round(0.6 + (seed % 120) / 100, 2),
        "week52_high": None, "week52_low": None,
        "description": "Sample overview generated in mock mode; not real company data.",
        "source": MOCK_SOURCE,
    }


def _mock_news(tickers: list[str], limit: int) -> dict:
    now = datetime.now(timezone.utc)
    names = tickers or ["MARKET"]
    templates = [
        ("{t} shares move as investors weigh interest-rate outlook", "Neutral", 0.02),
        ("Analysts discuss {t} earnings expectations ahead of report", "Somewhat-Bullish", 0.21),
        ("{t} faces questions over slowing growth in key segment", "Somewhat-Bearish", -0.18),
        ("Index funds holding {t} see steady inflows, data shows", "Bullish", 0.36),
    ]
    articles = []
    for i in range(min(limit, 8)):
        t = names[i % len(names)]
        title, label, score = templates[i % len(templates)]
        articles.append({
            "title": "[SAMPLE] " + title.format(t=t), "source": "FinLit mock feed", "url": None,
            "published": (now - timedelta(hours=3 * i)).strftime("%Y%m%dT%H%M%S"),
            "summary": "Sample headline generated in mock mode for demonstration; not a real news story.",
            "sentiment_label": label, "sentiment_score": score, "tickers": [t],
        })
    return {"articles": articles, "source": MOCK_SOURCE}


_client: AlphaVantageClient | None = None
_client_settings = None


def get_client() -> AlphaVantageClient:
    """Shared client; rebuilt when settings are reloaded (e.g. a key was added to .env)."""
    global _client, _client_settings
    settings = get_settings()
    if _client is None or _client_settings is not settings:
        _client, _client_settings = AlphaVantageClient(), settings
    return _client


def reset_client() -> None:
    global _client
    _client = None
