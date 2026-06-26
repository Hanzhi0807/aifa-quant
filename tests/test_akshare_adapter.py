"""Tests for AkShare adapter."""

import pandas as pd
import pytest

from aifa_quant.data.adapters import AkShareAdapter


@pytest.fixture
def adapter():
    return AkShareAdapter()


class TestSymbolConversion:
    def test_to_akshare_symbol(self, adapter):
        assert adapter._to_akshare_symbol("000001.SZ") == "sz000001"
        assert adapter._to_akshare_symbol("600519.SH") == "sh600519"
        assert adapter._to_akshare_symbol("sz000001") == "sz000001"

    def test_to_standard_symbol(self, adapter):
        assert adapter._to_standard_symbol("sz000001") == "000001.SZ"
        assert adapter._to_standard_symbol("sh600519") == "600519.SH"
        assert adapter._to_standard_symbol("000001") == "000001.SZ"
        assert adapter._to_standard_symbol("600519") == "600519.SH"


class TestCleanDailyData:
    def test_clean_daily_data(self, adapter):
        df = pd.DataFrame(
            {
                "date": ["2024-12-02", "2024-12-03"],
                "open": [10.0, 11.0],
                "high": [10.5, 11.5],
                "low": [9.8, 10.8],
                "close": [10.2, 11.2],
                "volume": [1000, 2000],
                "amount": [10000.0, 22000.0],
                "outstanding_share": [1e9, 1e9],
                "turnover": [0.01, 0.02],
            }
        )
        cleaned = adapter._clean_daily_data(df, "000001.SZ")
        assert set(cleaned.columns) >= {"symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"}
        assert cleaned.iloc[0]["symbol"] == "000001.SZ"
        assert cleaned.iloc[0]["close"] == 10.2


class TestStockUniverseExtraction:
    def test_extract_symbols(self, adapter):
        df = pd.DataFrame(
            {
                "日期": ["2024-01-01", "2024-01-01"],
                "指数代码": ["000300", "000300"],
                "指数名称": ["沪深300", "沪深300"],
                "指数英文名称": ["CSI 300", "CSI 300"],
                "成分券代码": ["000001", "600519"],
                "成分券名称": ["平安银行", "贵州茅台"],
                "成分券英文名称": ["Ping An Bank", "Kweichow Moutai"],
                "交易所": ["深圳证券交易所", "上海证券交易所"],
                "交易所英文名称": ["Shenzhen Stock Exchange", "Shanghai Stock Exchange"],
                "权重": [0.5, 0.5],
            }
        )
        symbols = adapter._extract_symbols(df)
        assert set(symbols) == {"000001.SZ", "600519.SH"}


@pytest.mark.skip(reason="Requires network and AkShare availability")
def test_get_daily_data_live(adapter):
    df = adapter.get_daily_data("000001.SZ", start_date="20241201", end_date="20241231")
    assert not df.empty
    assert "close" in df.columns
