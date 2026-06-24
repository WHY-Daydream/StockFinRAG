"""测试爬虫源配置文件"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pytest

SOURCES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "crawler", "crawl_sources.json"
)


class TestCrawlSources:
    """crawl_sources.json 配置验证"""

    def load_sources(self) -> list:
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_crawl_sources_file_exists(self):
        """JSON 可解析，至少 5 个源"""
        sources = self.load_sources()
        assert isinstance(sources, list), "sources should be a list"
        assert len(sources) >= 5, f"Expected at least 5 sources, got {len(sources)}"

    def test_crawl_sources_has_new_entries(self):
        """包含 pbc / sse / sina 三个新源"""
        sources = self.load_sources()
        urls = [s["url"] for s in sources]
        assert any("pbc.gov.cn" in u for u in urls), "Missing PBC source"
        assert any("sse.com.cn" in u for u in urls), "Missing SSE source"
        assert any("finance.sina.com.cn" in u for u in urls), "Missing Sina Finance source"

    def test_crawl_sources_valid_structure(self):
        """每个源有 url / type / discover 字段"""
        sources = self.load_sources()
        for i, s in enumerate(sources):
            assert "url" in s, f"Source {i} missing 'url'"
            assert "type" in s, f"Source {i} missing 'type'"
            assert "discover" in s, f"Source {i} missing 'discover'"
            assert isinstance(s["discover"], bool), f"Source {i} 'discover' should be bool"
            assert isinstance(s["url"], str) and len(s["url"]) > 0, f"Source {i} 'url' invalid"
            assert isinstance(s["type"], str) and len(s["type"]) > 0, f"Source {i} 'type' invalid"


SEED_DOCS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "seed_financial_docs.json"
)


class TestSeedDocs:
    """seed_financial_docs.json 文档验证"""

    def load_docs(self) -> list:
        with open(SEED_DOCS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_seed_docs_count(self):
        """至少 20 篇文档"""
        docs = self.load_docs()
        assert len(docs) >= 20, f"Only {len(docs)} seed docs"

    def test_seed_docs_have_content(self):
        """每篇文档有 title、doc_type、content 且正文超过 100 字"""
        docs = self.load_docs()
        for doc in docs:
            assert len(doc["raw_text"]) > 100, f"{doc['title']} raw_text too short"
            assert doc["doc_type"], f"{doc['title']} missing doc_type"
            assert doc["title"], f"Doc missing title"
            assert doc["source"], f"{doc['title']} missing source"


def test_akshare_provider_has_macro_functions():
    with open("data_providers/akshare_provider.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "fetch_macro_gdp" in source
    assert "fetch_macro_cpi" in source


def test_scheduler_has_macro_job():
    with open("scheduler.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "sched_macro" in source