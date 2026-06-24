"""
多源金融数据采集器

支持：
- 通用网页抓取（自动提取正文）
- 多级重试 + 回退 URL 机制
- 请求限速（礼貌间隔）
- 增量去重
- 多种内容提取策略（HTML / JSON / 纯文本）
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import hashlib
import time
import json
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from db import get_mysql


class FinancialCrawler:
    """多源金融数据采集器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        # 请求超时设置
        self.timeout = 30
        # 最大重试次数
        self.max_retries = 2

    def _discover_article_links(self, html: str, base_url: str) -> List[str]:
        """
        从 HTML 中发现文章链接。
        通过 URL 模式、锚文本长度等信号评分，>= 30 分视为文章。
        """
        import re
        from urllib.parse import urljoin, urlparse

        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            text = a_tag.get_text(strip=True)
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            path = parsed.path

            # 跳过特殊文件
            if re.search(r'\.(pdf|jpg|png|gif|css|js|zip|rar|docx?)$', path, re.I):
                continue
            # 跳过站外链接
            if parsed.netloc and base_url not in full_url:
                continue

            score = 0
            # URL 包含年份模式
            if re.search(r'/20\d{2}/', path):
                score += 20
            # URL 包含数字路径段（5位以上数字）
            if re.search(r'/\d{5,}', path):
                score += 20
            # URL 路径层级 >= 3
            segments = [s for s in path.split('/') if s]
            if len(segments) >= 3:
                score += 10
            # 锚文本长度 >= 8 个字
            if len(text) >= 8:
                score += 15
            # 锚文本含关键词
            keywords = ['政策', '法规', '通知', '意见', '解读', '办法', '条例',
                        '规定', '公告', '指引', '管理', '发展', '改革']
            if any(kw in text for kw in keywords):
                score += 10
            # 排除导航路径
            if re.search(r'/(list|index|page|search|tag)/', path, re.I):
                score -= 20
            # 排除导航锚文本（精确匹配短语，避免误伤文章标题）
            nav_phrases = ['首页', '关于我们', '联系我们', '帮助中心', '登录',
                           '注册', 'English', '网站地图', '友情链接', '设为首页']
            if any(kw == text.strip() for kw in nav_phrases):
                score -= 30

            # 去重
            if not any(c[0] == full_url for c in candidates):
                candidates.append((full_url, score, text))

        # 排序、过滤低分
        candidates.sort(key=lambda c: c[1], reverse=True)
        seen = set()
        result = []
        for url, score, text in candidates:
            if score >= 30 and url not in seen:
                seen.add(url)
                result.append(url)
        return result

    def _chinese_ratio(self, text: str) -> float:
        """计算文本中中文字符的占比"""
        if not text.strip():
            return 0.0
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        return chinese_chars / max(len(text), 1)

    def _has_paragraph_structure(self, text: str) -> bool:
        """检测文本是否有段落结构（文章正文有完整句子，导航页只有孤立词）"""
        if len(text) < 50:
            return False
        # 文章正文包含句号/逗号等句子结构
        sentence_endings = sum(1 for c in text if c in '。！？；')
        # 正文的标点密度通常 > 1 个句尾标点/200字
        punctuation_ratio = sentence_endings / max(len(text), 1)
        # 也要检查至少有一些超过 15 个字的"长行"
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        long_lines = sum(1 for l in lines if len(l) > 15)
        has_sentences = punctuation_ratio > 0.005  # 每 200 字至少 1 个句号
        has_long_lines = long_lines >= 2
        return has_sentences or has_long_lines

    def _extract_text_bs4(self, html: str, url: str = "") -> Optional[str]:
        """使用 BeautifulSoup 提取正文。返回 None 表示无法提取到有效内容。"""
        soup = BeautifulSoup(html, "html.parser")

        # 移除无用标签
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "noscript", "iframe", "svg", "form",
                          "button", "select", "input", "textarea"]):
            tag.decompose()

        # 尝试按正文容器提取
        for selector in ["article", "main", ".article", ".content",
                         "#content", ".main-content", ".article-content",
                         ".detail-content", ".news-content", ".text-content",
                         ".article-body", ".news_text", ".cont_text"]:
            container = soup.select_one(selector)
            if container:
                text = container.get_text(separator="\n", strip=True)
                if len(text) > 200 and self._has_paragraph_structure(text):
                    return text

        # 回退：整页提取 — 必须通过段落检测
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 500 and self._has_paragraph_structure(text):
            return text
        return None

    def _extract_text_json(self, data: dict) -> str:
        """从 JSON 响应中提取文本"""
        texts = []

        def _walk(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, dict):
                for key, val in obj.items():
                    if isinstance(val, str) and len(val) > 30:
                        texts.append(val)
                    else:
                        _walk(val, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item, depth + 1)

        _walk(data)
        return "\n".join(texts)

    def fetch_url(self, url: str, retry: int = 0) -> Optional[str]:
        """
        抓取 URL，返回提取的纯文本。
        支持自动重试和 JSON 响应处理。
        """
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()

            # 自动检测编码
            if resp.encoding and resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"

            content_type = resp.headers.get("Content-Type", "").lower()

            if "application/json" in content_type or url.endswith(".json"):
                data = resp.json()
                text = self._extract_text_json(data)
            else:
                text = self._extract_text_bs4(resp.text, url)

            # _extract_text_bs4 可能返回 None（无法提取有效正文）
            if text is None:
                logger.warning(f"No valid content extracted from {url}")
                if retry < self.max_retries:
                    time.sleep(2)
                    return self.fetch_url(url, retry + 1)
                return None

            # 过滤太短的内容
            if len(text.strip()) < 200:
                logger.warning(f"Content too short ({len(text)} chars) from {url}")
                if retry < self.max_retries:
                    time.sleep(2)
                    return self.fetch_url(url, retry + 1)
                return None

            # 过滤无段落结构的内容（导航页/列表页）
            if not self._has_paragraph_structure(text):
                logger.warning(f"No paragraph structure detected from {url}")
                if retry < self.max_retries:
                    time.sleep(2)
                    return self.fetch_url(url, retry + 1)
                return None

            logger.info(f"Fetched {len(text)} chars from {url}")
            return text

        except requests.exceptions.Timeout:
            logger.error(f"Timeout: {url}")
            if retry < self.max_retries:
                time.sleep(3)
                return self.fetch_url(url, retry + 1)
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP {e.response.status_code}: {url}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {url} — {e}")
            if retry < self.max_retries:
                time.sleep(5)
                return self.fetch_url(url, retry + 1)
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def fetch_report(self, url: str, doc_type: str, title: str,
                     fallback_url: str = None) -> Optional[dict]:
        """
        抓取一篇报告/文章

        参数:
            url: 主 URL
            doc_type: 文档类型（财报/研报/政策/法规/新闻）
            title: 文档标题
            fallback_url: 主 URL 失败时的备用 URL
        """
        text = self.fetch_url(url)

        # 主 URL 失败，尝试备用
        if text is None and fallback_url:
            logger.info(f"Trying fallback URL: {fallback_url}")
            text = self.fetch_url(fallback_url)

        if text is None:
            logger.error(f"All URLs failed for: {title}")
            return None

        return {
            "title": title,
            "doc_type": doc_type,
            "source": url,
            "raw_text": text,
            "summary": text[:300],
            "file_hash": hashlib.md5(text.encode("utf-8")).hexdigest(),
            "publish_date": datetime.now().date(),
        }

    def save_document(self, doc: dict) -> int:
        """
        保存文档到 MySQL，自动去重。
        返回 doc_id（新建或已存在）。
        """
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM documents WHERE file_hash=%s", (doc["file_hash"],))
                existing = cur.fetchone()
                if existing:
                    logger.info(f"Duplicate (skipped): {doc['title']} (doc_id={existing['id']})")
                    return existing["id"]

                cur.execute(
                    """INSERT INTO documents
                       (doc_type, title, source, publish_date, summary, raw_text, file_hash, chunk_count)
                       VALUES (%(doc_type)s, %(title)s, %(source)s, %(publish_date)s,
                               %(summary)s, %(raw_text)s, %(file_hash)s, 0)""",
                    doc,
                )
                conn.commit()
                doc_id = cur.lastrowid
                logger.info(f"Saved doc_id={doc_id}: {doc['title']}")
                return doc_id
        finally:
            conn.close()


def batch_crawl(config_path: str = None) -> List[int]:
    """
    批量爬取：读取配置，逐篇抓取并保存。
    支持 discover 模式：从列表页发现文章链接后逐个抓取。
    返回新入库的 doc_id 列表。
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "crawl_sources.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        sources: List[dict] = json.load(f)

    logger.info(f"Starting batch crawl: {len(sources)} sources")
    crawler = FinancialCrawler()
    doc_ids = []

    for i, source in enumerate(sources):
        logger.info(f"[{i + 1}/{len(sources)}] Crawling: {source['title']}")

        if source.get("discover", False):
            # --- 发现模式：从列表页找文章链接 ---
            max_articles = source.get("max_articles", 5)
            html = None
            try:
                resp = crawler.session.get(source["url"], timeout=crawler.timeout)
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                logger.error(f"Failed to fetch index page {source['url']}: {e}")
                continue

            article_urls = crawler._discover_article_links(html, source["url"])
            article_urls = article_urls[:max_articles]
            logger.info(f"  Discovered {len(article_urls)} article links")

            for j, article_url in enumerate(article_urls):
                logger.info(f"  [{j+1}/{len(article_urls)}] Fetching: {article_url}")
                text = crawler.fetch_url(article_url)
                if text is None:
                    continue
                # 从文章链接提取标题后缀
                prefix = source.get("title_prefix", "") or source["title"]
                doc = {
                    "title": f"{prefix} #{j+1}",
                    "doc_type": source.get("type", "知识"),
                    "source": article_url,
                    "raw_text": text,
                    "summary": text[:300],
                    "file_hash": hashlib.md5(text.encode("utf-8")).hexdigest(),
                    "publish_date": datetime.now().date(),
                }
                doc_id = crawler.save_document(doc)
                if doc_id:
                    doc_ids.append(doc_id)
                time.sleep(1.0)

        else:
            # --- 单页模式（原有逻辑）---
            doc = crawler.fetch_report(
                url=source["url"],
                doc_type=source.get("type", "知识"),
                title=source["title"],
                fallback_url=source.get("fallback_url"),
            )
            if doc:
                doc_id = crawler.save_document(doc)
                doc_ids.append(doc_id)

        time.sleep(1.5)

    logger.info(f"Batch crawl complete: {len(doc_ids)} new documents")
    return doc_ids


if __name__ == "__main__":
    # 命令行模式
    import argparse
    parser = argparse.ArgumentParser(description="金融数据爬虫")
    parser.add_argument("--config", default=None, help="爬取配置 JSON 路径")
    parser.add_argument("--limit", type=int, default=10, help="最大爬取数")
    args = parser.parse_args()

    ids = batch_crawl(args.config)
    print(f"Crawled doc_ids: {ids}")
