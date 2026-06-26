"""Tests for news MCP adapter and sentiment features."""

import json

import pandas as pd
import pytest

from aifa_quant.data.adapters.news_mcp import NewsMCPAdapter
from aifa_quant.features.sentiment import build_sentiment_features, merge_sentiment_to_daily


class FakeNewsAdapter(NewsMCPAdapter):
    """NewsMCPAdapter subclass with network calls mocked out."""

    def __init__(self):
        # Bypass BaseSettings and network initialization.
        object.__setattr__(self, "_tools", None)
        object.__setattr__(self, "_tool_map", None)
        object.__setattr__(self, "url", "")
        object.__setattr__(self, "token", "")
        object.__setattr__(self, "session", None)

    def list_tools(self):
        return [{"name": "ifind_news_search", "description": ""}]

    def call_tool(self, name, arguments=None):
        query = (arguments or {}).get("query", "")
        # Return different fake articles for positive/negative symbols.
        if "positive" in query:
            articles = [
                {
                    "标题": "上涨 大涨 利好",
                    "发布时间": "2024-03-29 10:00:00",
                },
                {
                    "标题": "增长 超预期",
                    "发布时间": "2024-03-30 11:00:00",
                },
            ]
        elif "negative" in query:
            articles = [
                {
                    "标题": "下跌 利空 亏损",
                    "发布时间": "2024-03-29 10:00:00",
                },
                {
                    "标题": "暴跌 风险",
                    "发布时间": "2024-03-30 11:00:00",
                },
            ]
        else:
            articles = []

        payload = {"code": 1, "data": {"data": json.dumps(articles)}}
        return [{"type": "text", "text": json.dumps(payload)}]


def test_compute_sentiment_positive():
    texts = ["上涨", "大涨", "利好"]
    scores = NewsMCPAdapter.compute_sentiment(texts)
    assert scores["positive_ratio"] == pytest.approx(1.0)
    assert scores["negative_ratio"] == pytest.approx(0.0)
    assert scores["score"] > 0


def test_compute_sentiment_negative():
    texts = ["下跌", "暴跌", "风险"]
    scores = NewsMCPAdapter.compute_sentiment(texts)
    assert scores["positive_ratio"] == pytest.approx(0.0)
    assert scores["negative_ratio"] == pytest.approx(1.0)
    assert scores["score"] < 0


def test_compute_sentiment_neutral():
    texts = ["公司公告", "今日收盘"]
    scores = NewsMCPAdapter.compute_sentiment(texts)
    assert scores["neutral_ratio"] == pytest.approx(1.0)
    assert scores["article_count"] == 2


def test_get_daily_sentiment(monkeypatch):
    adapter = FakeNewsAdapter()
    df = adapter.get_daily_sentiment("positive_symbol", start_date="20240329", end_date="20240330")
    assert not df.empty
    assert set(df.columns) >= {
        "trade_date",
        "news_score",
        "news_positive_ratio",
        "news_negative_ratio",
        "news_neutral_ratio",
        "news_polarity",
        "news_article_count",
    }
    assert df["news_positive_ratio"].iloc[0] == pytest.approx(1.0)


def test_merge_sentiment_to_daily_ffill():
    daily = pd.DataFrame(
        {
            "symbol": ["A", "A", "A"],
            "trade_date": pd.to_datetime(["2024-03-29", "2024-03-30", "2024-04-01"]),
            "close": [1.0, 2.0, 3.0],
        }
    )
    sentiment = pd.DataFrame(
        {
            "symbol": ["A", "A"],
            "trade_date": pd.to_datetime(["2024-03-29", "2024-03-30"]),
            "news_score": [0.5, -0.5],
            "news_positive_ratio": [1.0, 0.0],
            "news_negative_ratio": [0.0, 1.0],
            "news_neutral_ratio": [0.0, 0.0],
            "news_polarity": [1.0, -1.0],
            "news_article_count": [2, 2],
        }
    )
    merged = merge_sentiment_to_daily(daily, sentiment)
    assert "news_score" in merged.columns
    # 2024-03-31 是周末无数据，4/1 应该被 ffill（在 limit=5 内）
    april_score = merged.loc[merged["trade_date"] == pd.Timestamp("2024-04-01"), "news_score"].iloc[0]
    assert april_score == pytest.approx(-0.5)


def test_build_sentiment_features_empty(monkeypatch):
    """If adapter returns no data, build_sentiment_features returns an empty DataFrame with the right schema."""

    class EmptyAdapter(NewsMCPAdapter):
        def __init__(self, settings=None):
            object.__setattr__(self, "_tools", None)
            object.__setattr__(self, "_tool_map", None)
            object.__setattr__(self, "url", "")
            object.__setattr__(self, "token", "")
            object.__setattr__(self, "session", None)

        def list_tools(self):
            return [{"name": "ifind_news_search", "description": ""}]

        def call_tool(self, name, arguments=None):
            payload = {"code": 1, "data": {"data": json.dumps([])}}
            return [{"type": "text", "text": json.dumps(payload)}]

    monkeypatch.setattr("aifa_quant.features.sentiment.NewsMCPAdapter", EmptyAdapter)
    df = build_sentiment_features(["000001.SZ"], start_date="20240101", end_date="20241231")
    assert df.empty
    assert "news_score" in df.columns
