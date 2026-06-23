"""测试爬虫内容质量检测"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from crawler.financial_crawler import FinancialCrawler


class TestContentQuality:
    """爬虫应能区分文章正文和导航页"""

    def setup_method(self):
        self.crawler = FinancialCrawler()

    def test_article_has_paragraph_structure(self):
        """文章正文应有段落结构（句号、长句）"""
        article = "2024年中国银行业整体经营稳健，资产规模持续增长。商业银行净利润同比增长3.2%。这主要得益于利息净收入的增加。"
        assert self.crawler._has_paragraph_structure(article), "Article should have paragraph structure"

    def test_nav_lacks_paragraph_structure(self):
        """导航页不应有段落结构"""
        nav = "首页\n财经\n股票\n新股\n基金\n债券\nEnglish\nSiteMap\n登录\n注册"
        assert not self.crawler._has_paragraph_structure(nav), "Nav should lack paragraph structure"

    def test_article_has_high_chinese_ratio(self):
        """文章正文的中文字符占比应高"""
        article = "2024年中国银行业整体经营稳健，资产规模持续增长。商业银行净利润同比增长3.2%。"
        ratio = self.crawler._chinese_ratio(article)
        assert ratio > 0.5, f"Article should have >50% Chinese chars, got {ratio:.2%}"

    def test_short_content_rejected(self):
        """内容太短应返回 None"""
        text = self.crawler.fetch_url("https://example.com/fake")
        assert text is None or len(text) >= 200

    def test_nav_content_extraction_returns_none(self):
        """仅有导航文字的内容提取应返回 None"""
        nav_html = """<html><body>
            <div class="nav">首页 财经 股票 新股 基金 债券 English SiteMap</div>
            <div class="footer">Copyright 2024 关于我们 联系我们 友情链接</div>
        </body></html>"""
        text = self.crawler._extract_text_bs4(nav_html, "https://test.com")
        assert text is None, "Navigation-only content extraction should return None (no paragraph structure)"

    def test_article_with_nav_should_extract(self):
        """有正文内容的页面即使有导航也应该提取到正文"""
        mixed_html = """<html><body>
            <div class="nav">首页 财经 股票 新股 基金 债券</div>
            <div class="content">
                <p>2024年中国银行业整体经营稳健，资产规模持续增长。</p>
                <p>商业银行净利润同比增长3.2%。这主要得益于利息净收入的增加。</p>
            </div>
            <div class="footer">Copyright 2024 关于我们</div>
        </body></html>"""
        text = self.crawler._extract_text_bs4(mixed_html, "https://test.com")
        assert text is not None, "Article with content should be extracted"
        assert "银行业" in text, "Should contain article text"