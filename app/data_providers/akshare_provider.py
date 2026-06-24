"""AKShare 金融数据采集封装"""
from typing import List, Dict, Optional
from datetime import datetime, date
import hashlib
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
    except Exception as e:
        conn.rollback()
        logger.error(f"Save indices failed, rolled back: {e}")
        return 0
    finally:
        conn.close()
    return inserted


def fetch_latest_news(limit: int = 10) -> List[Dict]:
    """
    获取东方财富最新财经新闻，返回结构化数据。
    每条新闻包含：标题、摘要、发布时间、URL、正文（通过爬虫获取）
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare not installed, returning empty")
        return []

    try:
        df = ak.stock_info_global_em()
        if df.empty:
            return []

        records = []
        for _, row in df.head(limit).iterrows():
            vals = [row.iloc[i] for i in range(len(row))]
            title = str(vals[0]) if len(vals) > 0 else ""
            summary = str(vals[1]) if len(vals) > 1 else ""
            pub_time = str(vals[2]) if len(vals) > 2 else ""
            url = str(vals[3]) if len(vals) > 3 else ""

            # 标题和摘要合并作为正文
            content = f"{title}\n\n{summary}" if summary else title
            records.append({
                "title": title[:200],
                "doc_type": "新闻",
                "source": url,
                "raw_text": content,
                "summary": summary[:300],
                "file_hash": hashlib.md5(content.encode("utf-8")).hexdigest(),
                "publish_date": datetime.now().date(),
            })
        logger.info(f"Fetched {len(records)} news from akshare")
        return records
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        return []


def save_news(news_list: List[Dict]) -> int:
    """保存新闻到 MySQL documents 表（自动去重）"""

    if not news_list:
        return 0
    conn = get_mysql()
    saved = 0
    try:
        with conn.cursor() as cur:
            for news in news_list:
                cur.execute("SELECT id FROM documents WHERE file_hash=%s", (news["file_hash"],))
                if cur.fetchone():
                    continue
                cur.execute(
                    """INSERT INTO documents
                       (doc_type, title, source, publish_date, summary, raw_text, file_hash, chunk_count)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 0)""",
                    (news["doc_type"], news["title"], news["source"],
                     news["publish_date"], news["summary"], news["raw_text"],
                     news["file_hash"]),
                )
                saved += 1
        conn.commit()
        logger.info(f"Saved {saved} new news articles")
    except Exception as e:
        conn.rollback()
        logger.error(f"Save news failed, rolled back: {e}")
        return 0
    finally:
        conn.close()
    return saved


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


def fetch_macro_gdp() -> List[Dict]:
    """获取中国GDP季度数据"""
    import akshare as ak
    try:
        df = ak.macro_china_gdp()
        records = df.tail(20).to_dict("records")
        logger.info(f"Fetched {len(records)} GDP records")
        return records
    except Exception as e:
        logger.error(f"fetch_macro_gdp failed: {e}")
        return []


def fetch_macro_cpi() -> List[Dict]:
    """获取中国CPI月度数据"""
    import akshare as ak
    try:
        df = ak.macro_china_cpi_yearly()
        records = df.tail(24).to_dict("records")
        logger.info(f"Fetched {len(records)} CPI records")
        return records
    except Exception as e:
        logger.error(f"fetch_macro_cpi failed: {e}")
        return []