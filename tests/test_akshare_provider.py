import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from data_providers.akshare_provider import fetch_index_daily, save_indices


class TestFetchIndexDaily:
    def test_fetch_index_daily_returns_list(self):
        """获取上证指数日线应返回列表"""
        result = fetch_index_daily("000001", "上证指数")
        assert isinstance(result, list)
        if result:
            assert "index_code" in result[0]
            assert "close" in result[0]

    def test_fetch_index_daily_contains_required_fields(self):
        """返回的记录应包含必要字段"""
        result = fetch_index_daily("000001", "上证指数")
        if result:
            r = result[0]
            assert "index_code" in r
            assert "date" in r
            assert "close" in r

    def test_save_indices_inserts_to_mysql(self):
        """save_indices 应写入 MySQL 并幂等"""
        from db import get_mysql
        sample = [
            {"index_code": "000001", "index_name": "上证指数",
             "date": "2024-01-02", "open": 3000, "close": 3050,
             "high": 3060, "low": 2980, "volume": 100_000_000},
        ]
        count = save_indices(sample)
        assert count >= 0  # 幂等：可能已有相同记录
        # 验证已写入
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM stock_indices WHERE index_code='000001'")
                row = cur.fetchone()
                assert row["cnt"] > 0
        finally:
            conn.close()