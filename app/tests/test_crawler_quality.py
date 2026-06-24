"""测试爬虫内容质量检测"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from crawler.financial_crawler import FinancialCrawler
from typing import List


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
                <p>2024年中国银行业整体经营稳健，资产规模持续增长。商业银行净利润同比增长3.2%，这主要得益于利息净收入的增加。</p>
                <p>同时，不良贷款率保持在较低水平，资产质量持续改善。截至2024年末，银行业不良贷款率降至1.5%，较年初下降0.1个百分点。拨备覆盖率保持在180%以上，风险抵补能力充足。</p>
                <p>展望2025年，随着宏观经济稳步复苏和货币政策持续发力，银行业将继续保持稳健发展态势。预计全年信贷增速将保持在8%左右，净息差有望企稳回升。</p>
                <p>在数字化转型方面，各大银行持续加大科技投入，线上业务占比进一步提升。智能风控、数字人民币等创新应用不断深化。</p>
                <p>监管层面，金融监管部门将继续引导银行业回归本源、服务实体经济，同时加强对系统性金融风险的防范化解。</p>
            </div>
            <div class="footer">Copyright 2024 关于我们</div>
        </body></html>"""
        text = self.crawler._extract_text_bs4(mixed_html, "https://test.com")
        assert text is not None, "Article with content should be extracted"
        assert "银行业" in text, "Should contain article text"
        assert len(text) > 200, "Extracted text should be substantial"


class TestLinkDiscovery:
    """爬虫应能从列表页中发现文章链接"""

    def setup_method(self):
        self.crawler = FinancialCrawler()

    def test_detect_article_url_by_year_pattern(self):
        """含年份模式的 URL 应被识别为文章"""
        html = """<html><body>
            <a href="/zhengce/content/2025/01/15/content_6993796.htm">关于资本市场的指导意见</a>
            <a href="/">首页</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 1
        assert "content_6993796" in links[0]

    def test_detect_article_url_by_numeric_id(self):
        """含数字路径段的 URL 应被识别为文章"""
        html = """<html><body>
            <a href="https://www.gov.cn/zhengce/6993796.htm">金融监管条例</a>
            <a href="/list/">政策列表</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 1

    def test_nav_links_filtered(self):
        """导航链接不应被识别为文章"""
        html = """<html><body>
            <a href="/">首页</a>
            <a href="/about/">关于我们</a>
            <a href="/sitemap/">网站地图</a>
            <a href="/en/">English</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 0

    def test_external_links_filtered(self):
        """站外链接不应被识别"""
        html = """<html><body>
            <a href="https://www.baidu.com">百度</a>
            <a href="https://www.gov.cn/zhengce/6993796.htm">政策文件</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 1
        assert "baidu.com" not in links[0]

    def test_short_anchor_filtered(self):
        """锚文本太短的链接不应被识别"""
        html = """<html><body>
            <a href="/content/6993796.htm">点击</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 0

    def test_file_links_filtered(self):
        """图片/PDF 链接应过滤"""
        html = """<html><body>
            <a href="/file/report.pdf">报告PDF</a>
            <a href="/file/photo.jpg">图片</a>
            <a href="/content/6993796.htm">政策解读</a>
        </body></html>"""
        links = self.crawler._discover_article_links(html, "https://www.gov.cn")
        assert len(links) == 1


class TestTitleExtraction:
    """爬虫应从页面 <title> 提取真实标题"""

    def setup_method(self):
        self.crawler = FinancialCrawler()

    def test_extract_title_from_html(self):
        """能从 HTML 中提取标题"""
        html = "<html><head><title>国务院关于加强金融监管的通知 - 中国政府网</title></head><body></body></html>"
        title = self.crawler._extract_title(html)
        assert title == "国务院关于加强金融监管的通知"

    def test_extract_title_short_fallback(self):
        """标题太短时返回默认值"""
        html = "<html><head><title>首页</title></head><body></body></html>"
        title = self.crawler._extract_title(html, "默认标题")
        assert title == "默认标题"

    def test_extract_title_no_title_tag(self):
        """没有 title 标签时返回默认值"""
        html = "<html><body><p>no title</p></body></html>"
        title = self.crawler._extract_title(html, "未知文章")
        assert title == "未知文章"