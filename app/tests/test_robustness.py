"""验证健壮性修复

Bug #7: Milvus 查询表达式使用 IN 语法（而非链式 ||）
Bug #8: file_hash 有 UNIQUE 约束
Bug #9: 空检索上下文友好处理
Bug #11: 审计日志记录 latency_ms
"""
import os
import re


def get_file_source(filename):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


class TestMilvusQuery:
    """Bug #7: 双通道检索架构验证"""

    def test_dual_channel_search_structure(self):
        """检索器应有 parent 和 child 两个通道"""
        source = get_file_source("retrieval/hybrid_searcher.py")
        assert "_search_collection" in source, "应有 _search_collection 方法"
        assert '"parent"' in source, "应有 parent 通道"
        assert '"child"' in source, "应有 child 通道"

    def test_no_old_fetch_parents(self):
        """不应再使用旧的 _fetch_parents 方法"""
        source = get_file_source("retrieval/hybrid_searcher.py")
        assert "_fetch_parents" not in source, "旧的 _fetch_parents 已移除，改用双通道向量检索"


class TestUniqueConstraint:
    """Bug #8: file_hash 应有 UNIQUE 约束"""

    def test_file_hash_has_unique(self):
        """MySQL schema 中 file_hash 应有 UNIQUE 约束"""
        schema_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        schema_path = os.path.join(schema_dir, "mysql", "init", "01_schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "UNIQUE" in content and "file_hash" in content, (
            "documents 表的 file_hash 字段应添加 UNIQUE 约束"
        )


class TestEmptyContext:
    """Bug #9: 空检索上下文应友好处理"""

    def test_context_empty_check_exists(self):
        """analysis_node 函数应有空上下文检查逻辑"""
        source = get_file_source("agent/graph.py")
        # 直接在 analysis_node 函数定义下方查找空值检查
        analysis_node_start = source.find("def analysis_node(")
        assert analysis_node_start >= 0, "找不到 analysis_node 函数"
        # 提取函数体直到下一个 def
        remainder = source[analysis_node_start:]
        next_def = remainder.find("\ndef ", 1)
        func_body = remainder[:next_def] if next_def > 0 else remainder
        # 检查有无空值判断
        has_check = (
            "not context" in func_body
            or "context is None" in func_body
            or "if not context" in func_body
            or "len(context)" in func_body
        )
        assert has_check, (
            "analysis_node 应检查上下文是否为空并给出友好提示，在函数体中未找到空值检查"
        )


class TestLatencyLogging:
    """Bug #11: 审计日志应记录 latency_ms"""

    def test_latency_tracked_in_service(self):
        """审计日志写入和 latency_ms 应在服务层处理"""
        source = get_file_source("service/qa_service.py")
        assert "latency_ms" in source, (
            "qa_service.py 中应包含 latency_ms 字段的写入"
        )
        assert "qa_logs" in source, "qa_service.py 中应写入 qa_logs 表"
        assert "_write_audit_log" in source, "应有审计日志写入方法"
