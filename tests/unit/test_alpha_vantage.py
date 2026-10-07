import pytest

from finlit.tools.alpha_vantage import (
    MOCK_SOURCE,
    AlphaVantageClient,
    MarketDataError,
    RateLimitError,
    SymbolNotFoundError,
)


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        p = self.payloads.pop(0)
        return p if isinstance(p, FakeResp) else FakeResp(p)


def live(session):
    c = AlphaVantageClient(api_key="demo", mock=False, session=session)
    c.limiter.calls = 1000  # don't throttle tests
    return c


QUOTE = {"Global Quote": {"01. symbol": "IBM", "02. open": "180.0", "03. high": "182.5",
                          "04. low": "179.1", "05. price": "181.20", "06. volume": "3456789",
                          "07. latest trading day": "2025-01-10", "08. previous close": "179.90",
                          "09. change": "1.30", "10. change percent": "0.7226%"}}


def test_parses_global_quote_and_caches():
    s = FakeSession(QUOTE)
    c = live(s)
    q = c.get_quote("ibm")
    assert q["price"] == 181.2 and q["change_percent"] == pytest.approx(0.7226)
    assert q["volume"] == 3456789 and q["source"] == "Alpha Vantage"
    c.get_quote("IBM")  # served from cache
    assert len(s.calls) == 1
    assert s.calls[0]["function"] == "GLOBAL_QUOTE" and s.calls[0]["apikey"] == "demo"


def test_rate_limit_note_raises():
    c = live(FakeSession({"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is..."}))
    with pytest.raises(RateLimitError):
        c.get_quote("IBM")


def test_information_payload_raises_rate_limit():
    c = live(FakeSession({"Information": "We have detected your API key ... 25 requests per day."}))
    with pytest.raises(RateLimitError):
        c.get_quote("IBM")


def test_error_message_is_symbol_not_found():
    c = live(FakeSession({"Error Message": "Invalid API call."}))
    with pytest.raises(SymbolNotFoundError):
        c.get_overview("ZZZZ")


def test_empty_quote_is_not_found():
    c = live(FakeSession({"Global Quote": {}}))
    with pytest.raises(SymbolNotFoundError):
        c.get_quote("ZZZZ")


def test_http_error():
    c = live(FakeSession(FakeResp({}, status=403)))
    with pytest.raises(MarketDataError):
        c.get_quote("IBM")


def test_get_quotes_collects_partial_errors_and_dedupes():
    c = live(FakeSession(QUOTE, {"Global Quote": {}}))
    r = c.get_quotes(["IBM", "ibm", "BAD"])
    assert [q["symbol"] for q in r["quotes"]] == ["IBM"]
    assert r["errors"][0]["symbol"] == "BAD"


def test_daily_series_sorted_oldest_first():
    payload = {"Time Series (Daily)": {"2025-01-03": {"4. close": "12"}, "2025-01-02": {"4. close": "11"},
                                       "2025-01-06": {"4. close": "13"}}}
    h = live(FakeSession(payload)).get_daily_closes("X")
    assert h["dates"] == ["2025-01-02", "2025-01-03", "2025-01-06"]
    assert h["closes"] == [11, 12, 13]


def test_news_parsing():
    payload = {"feed": [{"title": "T", "url": "u", "time_published": "20250101T000000", "summary": "s",
                         "source": "src", "overall_sentiment_score": "0.2",
                         "overall_sentiment_label": "Somewhat-Bullish",
                         "ticker_sentiment": [{"ticker": "AAPL"}]}]}
    n = live(FakeSession(payload)).get_news(["AAPL"])
    assert n["articles"][0]["tickers"] == ["AAPL"] and n["articles"][0]["sentiment_score"] == 0.2


def test_mock_mode_is_deterministic_and_labelled():
    c = AlphaVantageClient(api_key="", mock=False)  # no key forces mock
    assert c.mock
    a, b = c.get_quote("AAPL"), c.get_quote("AAPL")
    assert a["price"] == b["price"] and a["source"] == MOCK_SOURCE
    assert all(art["title"].startswith("[SAMPLE]") for art in c.get_news(["AAPL"])["articles"])
