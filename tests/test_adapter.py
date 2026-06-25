"""Tests for iFind MCP adapters."""

import json

import pandas as pd
import pytest

from aifa_quant.data.adapters.stock_mcp import StockMCPAdapter


def test_parse_markdown_table():
    markdown = """
|证券代码|证券简称|日期|收盘价（单位：元）|
|---|---|---|---|
|600519.SH|贵州茅台|20240329|1702.9|
|600519.SH|贵州茅台|20240328|1701.64|
"""
    df = StockMCPAdapter._parse_markdown_table(markdown)
    assert len(df) == 2
    assert list(df.columns) == ["证券代码", "证券简称", "日期", "收盘价（单位：元）"]
    assert df.iloc[0]["收盘价（单位：元）"] == "1702.9"


def test_parse_chinese_number():
    assert StockMCPAdapter._parse_chinese_number("1.2万") == pytest.approx(12000)
    assert StockMCPAdapter._parse_chinese_number("3.5亿") == pytest.approx(350000000)
    assert StockMCPAdapter._parse_chinese_number(100) == pytest.approx(100)
    assert pd.isna(StockMCPAdapter._parse_chinese_number("abc"))


def test_clean_daily_data():
    df = pd.DataFrame(
        {
            "证券代码": ["600519.SH", "600519.SH"],
            "证券简称": ["贵州茅台", "贵州茅台"],
            "日期": ["2024-03-29", "2024-03-28"],
            "开盘价（单位：元）": ["1701.64", "1695.0"],
            "最高价（单位：元）": ["1710.99", "1718.0"],
            "最低价（单位：元）": ["1698.1", "1693.2"],
            "收盘价（单位：元）": ["1702.9", "1701.64"],
            "成交量": ["134.5655万", "246.4218万"],
            "成交额（单位：元）": ["22.9058亿", "42.0186亿"],
        }
    )
    cleaned = StockMCPAdapter._clean_daily_data(df)
    assert list(cleaned.columns) == ["symbol", "name", "trade_date", "open", "high", "low", "close", "volume", "amount"]
    assert cleaned["volume"].iloc[0] == pytest.approx(1345655)
    assert cleaned["amount"].iloc[0] == pytest.approx(2290580000)


def test_content_to_dataframe_with_ifind_payload():
    payload = {
        "code": 1,
        "data": {"answer": "|证券代码|日期|收盘价（单位：元）|\n|---|---|---|\n|600519.SH|20240329|1702.9|"},
    }
    content = [{"type": "text", "text": json.dumps(payload)}]
    df = StockMCPAdapter._content_to_dataframe(content)
    assert len(df) == 1
    assert "证券代码" in df.columns
