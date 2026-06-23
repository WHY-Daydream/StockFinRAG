"""AKShare 金融数据采集封装"""
from typing import List, Dict, Optional
from datetime import datetime, date
from loguru import logger
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_mysql


def fetch_index_daily(index_code: str, index_name: str) -> List[Dict]:
    """
    获取指数日线行情
    Args:
        index_code: 指数代码，如 "000001"
        index_name: 指数名称，如 "上证指数"
    Returns:
        list[dict]: 行情记录列表
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare not installed, returning empty")
        return []

    try:
        df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
        if df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            records.append({
                "index_code": index_code,
                "index_name": index_name,
                "date": str(row.get("date", datetime.now().date()))[:10],
                "open": float(row.get("open", 0)),
                "close": float(row.get("close", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "volume": int(row.get("volume", 0)),
            })
        # 只返回最近 5 条
        return records[-5:]
    except Exception as e:
        logger.error(f"Failed to fetch {index_code}: {e}")
        return []


def save_indices(records: List[Dict]) -> int:
    """
    批量保存指数数据到 MySQL（幂等）
    Returns: 插入的记录数
    """
    if not records:
        return 0
    conn = get_mysql()
    inserted = 0
    try:
        with conn.cursor() as cur:
            for r in records:
                cur.execute(
                    """INSERT IGNORE INTO stock_indices
                       (index_code, index_name, date, open, close, high, low, volume)
                       VALUES (%(index_code)s, %(index_name)s, %(date)s,
                               %(open)s, %(close)s, %(high)s, %(low)s, %(volume)s)""",
                    r,
                )
                if cur.rowcount > 0:
                    inserted += 1
        conn.commit()
        logger.info(f"Saved {inserted} index records")
    finally:
        conn.close()
    return inserted


def update_all_indices():
    """更新所有核心指数（便捷入口）"""
    indices = [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指"),
        ("000688", "科创50"),
    ]
    total = 0
    for code, name in indices:
        records = fetch_index_daily(code, name)
        total += save_indices(records)
    logger.info(f"Updated all indices: {total} new records")
    return total