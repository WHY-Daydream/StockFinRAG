import requests
from bs4 import BeautifulSoup
import hashlib
import time
import json
from datetime import datetime
from typing import Optional
from loguru import logger
import sys; sys.path.insert(0, "..")
from config import Config
from db import get_mysql


class FinancialCrawler:
    """多源金融数据采集器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/json,*/*",
        })

    def fetch_report(self, url: str, doc_type: str, title: str) -> Optional[dict]:
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)

            return {
                "title": title,
                "doc_type": doc_type,
                "source": url,
                "raw_text": text,
                "summary": text[:200],
                "file_hash": hashlib.md5(text.encode()).hexdigest(),
                "publish_date": datetime.now().date(),
            }
        except Exception as e:
            logger.error(f"Fetch failed: {url} — {e}")
            return None

    def save_document(self, doc: dict) -> int:
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM documents WHERE file_hash=%s", (doc["file_hash"],))
                existing = cur.fetchone()
                if existing:
                    return existing["id"]
                cur.execute(
                    """INSERT INTO documents (doc_type, title, source, publish_date, summary, raw_text, file_hash)
                       VALUES (%(doc_type)s, %(title)s, %(source)s, %(publish_date)s, %(summary)s, %(raw_text)s, %(file_hash)s)""",
                    doc,
                )
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()


def batch_crawl(config_path: str = "crawler/crawl_sources.json"):
    with open(config_path, "r") as f:
        sources = json.load(f)
    crawler = FinancialCrawler()
    for source in sources:
        logger.info(f"Crawling: {source['title']}")
        doc = crawler.fetch_report(source["url"], source["type"], source["title"])
        if doc:
            doc_id = crawler.save_document(doc)
            logger.info(f"Saved doc_id={doc_id}")
        time.sleep(1)
