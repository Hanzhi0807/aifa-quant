"""iFind news MCP adapter with lexicon-based sentiment scoring."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ...config.settings import Settings
from .base import BaseMCPAdapter

# Simple Chinese financial sentiment lexicon.
# Positive / negative word lists for fast, dependency-free scoring.
_POSITIVE_WORDS = frozenset(
    [
        "上涨",
        "涨幅",
        "大涨",
        "飙升",
        "强劲",
        "利好",
        "优势",
        "突破",
        "创新高",
        "增长",
        "提升",
        "改善",
        "盈利",
        "净利润",
        "超预期",
        "回购",
        "增持",
        "买入",
        "推荐",
        "看好",
        "乐观",
        "复苏",
        "回暖",
        "景气",
        "扩张",
        "升级",
        "订单",
        "中标",
        "合作",
        "签约",
        "增长",
        "提高",
        "上升",
        "增加",
        "丰收",
        "红利",
        "成功",
        "领先",
        "冠军",
        "龙头",
        "标杆",
    ]
)

_NEGATIVE_WORDS = frozenset(
    [
        "下跌",
        "跌幅",
        "大跌",
        "暴跌",
        "崩盘",
        "跳水",
        "利空",
        "风险",
        "亏损",
        "亏损额",
        "亏损面",
        "暴雷",
        "违约",
        "减持",
        "卖出",
        "看空",
        "悲观",
        "衰退",
        "下滑",
        "萎缩",
        "下行",
        "压力",
        "拖累",
        "放缓",
        "停滞",
        "裁员",
        "诉讼",
        "处罚",
        "监管",
        "调查",
        "停产",
        "限产",
        "滞销",
        "库存",
        "贬值",
        "恶化",
        "不及预期",
        "低于预期",
        " miss",
        " miss",
        "衰退",
        "下降",
        "减少",
        "降低",
        "失败",
        "落后",
        "垫底",
    ]
)


class NewsMCPAdapter(BaseMCPAdapter):
    """Adapter for iFind news/sentiment MCP server."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        super().__init__(
            settings=s,
            url=s.ifind_news_mcp_url,
            token=s.ifind_news_mcp_token,
        )
        self._tool_map: dict[str, str] | None = None

    def discover_tools(self) -> dict[str, str]:
        """Map human-readable tool names to actual MCP tool names."""
        if self._tool_map is not None:
            return self._tool_map

        tools = self.list_tools()
        mapping: dict[str, str] = {}
        for tool in tools:
            name = tool.get("name", "")
            lower = name.lower()
            if "news" in lower and "trending" not in lower:
                mapping["news"] = name
            elif "trending" in lower:
                mapping["trending"] = name
            elif "notice" in lower:
                mapping["notice"] = name
            else:
                mapping[name] = name
        self._tool_map = mapping
        return mapping

    def _call_mapped(self, key: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        """Call a mapped tool by its human-readable key."""
        tools = self.discover_tools()
        tool_name = tools.get(key)
        if not tool_name:
            raise RuntimeError(f"No '{key}' tool found on news MCP server")
        return self.call_tool(tool_name, arguments)

    @staticmethod
    def _parse_news_content(content: list[dict[str, Any]]) -> pd.DataFrame:
        """Parse iFind news MCP response into a DataFrame.

        The news server wraps article arrays as a JSON-encoded string inside
        ``data.data``. This helper unwraps that layer.
        """
        if not content:
            return pd.DataFrame()

        first = content[0]
        if first.get("type") != "text":
            return BaseMCPAdapter._content_to_dataframe(content)

        text = first.get("text", "")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return BaseMCPAdapter._content_to_dataframe(content)

        if not isinstance(payload, dict):
            return BaseMCPAdapter._content_to_dataframe(content)

        data_obj = payload.get("data", {})
        articles = None
        if isinstance(data_obj, dict):
            # iFind sometimes returns the payload as a JSON string inside data.answer.
            answer = data_obj.get("answer")
            if isinstance(answer, str):
                answer = answer.strip()
                if answer.startswith("["):
                    try:
                        articles = json.loads(answer)
                    except json.JSONDecodeError:
                        articles = None
                elif "|" in answer:
                    return BaseMCPAdapter._parse_markdown_table(answer)
                else:
                    # Non-tabular answer (e.g. quota/limit message) -> no data.
                    return pd.DataFrame()

            raw = data_obj.get("data")
            if articles is None:
                if isinstance(raw, str):
                    try:
                        articles = json.loads(raw)
                    except json.JSONDecodeError:
                        articles = None
                elif isinstance(raw, list):
                    articles = raw
        elif isinstance(data_obj, list):
            articles = data_obj

        if isinstance(articles, list):
            return pd.DataFrame(articles)
        return BaseMCPAdapter._content_to_dataframe(content)

    def search_news(
        self,
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
        size: int = 20,
    ) -> pd.DataFrame:
        """Search news articles for a query.

        Args:
            query: Search query, e.g., stock name or symbol.
            start_date: Start date (YYYYMMDD).
            end_date: End date (YYYYMMDD).
            size: Max number of articles to return.
        """
        arguments: dict[str, Any] = {"query": query, "size": size}
        if start_date:
            arguments["time_start"] = self._normalize_date(start_date)
        if end_date:
            arguments["time_end"] = self._normalize_date(end_date)
        content = self._call_mapped("news", arguments)
        return self._parse_news_content(content)

    def search_notices(
        self,
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
        size: int = 20,
    ) -> pd.DataFrame:
        """Search company announcements / notices."""
        arguments: dict[str, Any] = {"query": query, "size": size}
        if start_date:
            arguments["time_start"] = self._normalize_date(start_date)
        if end_date:
            arguments["time_end"] = self._normalize_date(end_date)
        content = self._call_mapped("notice", arguments)
        return self._parse_news_content(content)

    def search_trending_news(
        self,
        keyword: str = "",
        industry_name: str = "",
        time_scope: str = "24小时",
        sensitive: str = "全部",
        size: int = 20,
    ) -> pd.DataFrame:
        """Search trending / hot news.

        Args:
            keyword: Keyword to search.
            industry_name: Industry filter, e.g., "半导体".
            time_scope: Time window string such as "24小时".
            sensitive: Sensitivity filter, e.g., "全部".
            size: Max number of articles.
        """
        arguments: dict[str, Any] = {
            "keyword": keyword,
            "industry_name": industry_name,
            "time_scope": time_scope,
            "sensitive": sensitive,
            "size": size,
        }
        content = self._call_mapped("trending", arguments)
        return self._parse_news_content(content)

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Convert YYYYMMDD to ISO date string accepted by iFind news API."""
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str

    @staticmethod
    def _extract_text(row: pd.Series) -> str:
        """Best-effort text extraction from a news DataFrame row."""
        candidates = ["标题", "内容", "摘要", "title", "content", "summary", "text"]
        for col in candidates:
            if col in row.index and pd.notna(row[col]):
                return str(row[col])
        return " ".join(str(v) for v in row.values if pd.notna(v))

    @staticmethod
    def _parse_publish_date(row: pd.Series) -> pd.Timestamp | None:
        """Best-effort publish date extraction."""
        candidates = ["发布时间", "日期", "publish_time", "date", "time"]
        for col in candidates:
            if col in row.index and pd.notna(row[col]):
                try:
                    return pd.to_datetime(row[col])
                except Exception:
                    continue
        return None

    @classmethod
    def compute_sentiment(cls, texts: list[str]) -> dict[str, float]:
        """Compute sentiment scores for a list of texts.

        Returns a dictionary with:
            - score: net sentiment in [-1, 1]
            - positive_ratio, negative_ratio, neutral_ratio
            - polarity: positive - negative
        """
        if not texts:
            return {
                "score": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
                "polarity": 0.0,
                "article_count": 0,
            }

        pos_count = 0
        neg_count = 0
        for text in texts:
            text = str(text)
            pos = sum(1 for w in _POSITIVE_WORDS if w in text)
            neg = sum(1 for w in _NEGATIVE_WORDS if w in text)
            if pos > neg:
                pos_count += 1
            elif neg > pos:
                neg_count += 1

        total = len(texts)
        pos_ratio = pos_count / total
        neg_ratio = neg_count / total
        neutral_ratio = 1 - pos_ratio - neg_ratio
        score = (pos_ratio - neg_ratio) / max(pos_ratio + neg_ratio, 1e-6)
        polarity = pos_ratio - neg_ratio
        return {
            "score": float(score),
            "positive_ratio": float(pos_ratio),
            "negative_ratio": float(neg_ratio),
            "neutral_ratio": float(neutral_ratio),
            "polarity": float(polarity),
            "article_count": total,
        }

    def get_daily_sentiment(
        self,
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
        size_per_symbol: int = 50,
    ) -> pd.DataFrame:
        """Aggregate news sentiment per calendar day for a query.

        Args:
            query: Search query (stock name, symbol, or industry keyword).
            start_date: Start date (YYYYMMDD).
            end_date: End date (YYYYMMDD).
            size_per_symbol: Max news articles to fetch.

        Returns:
            DataFrame with columns: trade_date, news_score, news_positive_ratio,
            news_negative_ratio, news_neutral_ratio, news_polarity, news_article_count.
        """
        df = self.search_news(query, start_date, end_date, size=size_per_symbol)
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "news_score",
                    "news_positive_ratio",
                    "news_negative_ratio",
                    "news_neutral_ratio",
                    "news_polarity",
                    "news_article_count",
                ]
            )

        rows = []
        for _, row in df.iterrows():
            text = self._extract_text(row)
            pub_date = self._parse_publish_date(row)
            if pub_date is None:
                continue
            rows.append({"trade_date": pub_date, "text": text})

        if not rows:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "news_score",
                    "news_positive_ratio",
                    "news_negative_ratio",
                    "news_neutral_ratio",
                    "news_polarity",
                    "news_article_count",
                ]
            )

        texts_df = pd.DataFrame(rows)
        texts_df["trade_date"] = pd.to_datetime(texts_df["trade_date"]).dt.normalize()

        grouped = []
        for date, group in texts_df.groupby("trade_date"):
            scores = self.compute_sentiment(group["text"].tolist())
            grouped.append(
                {
                    "trade_date": date,
                    "news_score": scores["score"],
                    "news_positive_ratio": scores["positive_ratio"],
                    "news_negative_ratio": scores["negative_ratio"],
                    "news_neutral_ratio": scores["neutral_ratio"],
                    "news_polarity": scores["polarity"],
                    "news_article_count": scores["article_count"],
                }
            )

        return pd.DataFrame(grouped).sort_values("trade_date").reset_index(drop=True)

    def get_sentiment_for_symbol(
        self,
        symbol: str,
        name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        size_per_symbol: int = 50,
    ) -> pd.DataFrame:
        """Fetch news sentiment for a single symbol.

        Uses both the symbol and (optionally) the company name as query terms
        to improve recall.
        """
        queries = [symbol]
        if name:
            queries.append(name)

        frames = []
        for q in queries:
            df = self.get_daily_sentiment(q, start_date, end_date, size_per_symbol)
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "news_score",
                    "news_positive_ratio",
                    "news_negative_ratio",
                    "news_neutral_ratio",
                    "news_polarity",
                    "news_article_count",
                ]
            )

        combined = pd.concat(frames, ignore_index=True)
        combined["trade_date"] = pd.to_datetime(combined["trade_date"]).dt.normalize()
        # Aggregate across query terms by date
        agg = (
            combined.groupby("trade_date")
            .agg(
                news_score=("news_score", "mean"),
                news_positive_ratio=("news_positive_ratio", "mean"),
                news_negative_ratio=("news_negative_ratio", "mean"),
                news_neutral_ratio=("news_neutral_ratio", "mean"),
                news_polarity=("news_polarity", "mean"),
                news_article_count=("news_article_count", "sum"),
            )
            .reset_index()
        )
        agg = agg.sort_values("trade_date").reset_index(drop=True)
        return agg
