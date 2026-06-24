"""验证异常处理修复

Bug #4: json.loads 需要 try/except 保护
Bug #5: API 调用需要 try/except 保护
Bug #6: sys.path 需使用 os.path 解析而非硬编码 ".."
"""
import os


def get_file_source(filename):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


class TestErrorHandling:
    """Bug #4: json.loads 异常处理"""

    def test_compliance_node_has_json_error_handling(self):
        """compliance_node 中 json.loads 应在 try/except 内"""
        source = get_file_source("agent/graph.py")
        lines = source.split("\n")
        # 找到 json.loads 行
        json_loads_lines = [i for i, l in enumerate(lines) if "json.loads(" in l]
        for jl in json_loads_lines:
            # 检查上方是否有 try（搜索范围扩大到 15 行，因为 try 在 API 调用之前）
            has_try = any(
                lines[t].strip().startswith("try:")
                for t in range(max(0, jl - 15), jl)
            )
            has_get = ".get(" in lines[jl]
            assert has_try or has_get, (
                f"json.loads() 应在 try/except 内 (line {jl + 1}): {lines[jl].strip()}"
            )
            # 检查下方是否有 except
            has_except = any(
                lines[e].strip().startswith("except")
                for e in range(jl + 1, min(jl + 15, len(lines)))
            )
            assert has_try and has_except, (
                f"json.loads() 必须有对应的 except 处理 (line {jl + 1})"
            )

    def test_analysis_node_has_api_error_handling(self):
        """analysis_node 中 API 调用应在 try/except 内"""
        source = get_file_source("agent/graph.py")
        lines = source.split("\n")
        # 找到 client.chat.completions.create 行
        api_call_lines = [i for i, l in enumerate(lines) if "chat.completions.create(" in l]
        for al in api_call_lines:
            has_try = any(
                lines[t].strip().startswith("try:")
                for t in range(max(0, al - 10), al)
            )
            has_except = any(
                lines[e].strip().startswith("except")
                for e in range(al + 1, min(al + 15, len(lines)))
            )
            assert has_try and has_except, (
                f"chat.completions.create() 调用应在 try/except 内 (line {al + 1})"
            )


class TestSysPath:
    """Bug #6: sys.path 正确性"""

    def _check_syspath_files(self):
        """检查哪些文件使用 sys.path.insert"""
        files = [
            "agent/graph.py",
            "ingestion/pipeline.py",
            "retrieval/hybrid_searcher.py",
            "crawler/financial_crawler.py",
        ]
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        results = []
        for f in files:
            path = os.path.join(app_dir, f)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            has_syspath = 'sys.path.insert' in content or 'sys.path.append' in content
            if has_syspath:
                results.append((f, content))
        return results

    def test_no_hardcoded_dotdot_syspath(self):
        """不应使用硬编码的 sys.path.insert(0, '..')"""
        for fname, content in self._check_syspath_files():
            lines = content.split("\n")
            problematic = [l for l in lines if "sys.path.insert" in l and '".."' in l]
            assert not problematic, (
                f"{fname} 使用了硬编码 sys.path.insert(0, '..')，"
                f"应使用 os.path 动态解析: {problematic}"
            )

    def test_syspath_uses_abspath(self):
        """sys.path 应使用 os.path.abspath 动态解析"""
        for fname, content in self._check_syspath_files():
            lines = content.split("\n")
            syspath_lines = [l for l in lines if "sys.path.insert" in l or "sys.path.append" in l]
            for sl in syspath_lines:
                assert "os.path" in sl or "os.path.dirname" in sl, (
                    f"{fname} 中 sys.path 添加路径应使用 os.path.abspath 动态计算: {sl.strip()}"
                )
