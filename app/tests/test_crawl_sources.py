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