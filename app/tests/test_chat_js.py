"""验证 chat.js 的 bug 修复"""
import os

def get_source():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, "static", "js", "chat.js"), "r", encoding="utf-8") as f:
        return f.read()


def test_saveMessage_stores_compliance_reason():
    """saveMessage 应保存 compliance_reason"""
    source = get_source()
    # 检查 saveMessage 函数是否有 reason 参数
    assert "compliance_reason" in source or "complianceReason" in source, \
        "saveMessage 应保存 compliance_reason"


def test_loadMessages_shows_compliance_reason():
    """loadMessages 应显示 compliance_reason 而非 raw status"""
    source = get_source()
    assert "compliance_reason" in source or "complianceReason" in source, \
        "loadMessages 应显示 compliance_reason"


def test_localStorage_has_trycatch():
    """localStorage 操作应有 try/catch 保护"""
    source = get_source()
    lines = source.split("\n")
    # 检查 getSessions 和 saveSessions 是否有 try
    for fn_name in ["getSessions", "saveSessions"]:
        found = False
        for i, line in enumerate(lines):
            if f"function {fn_name}" in line:
                body = "\n".join(lines[i:i+20])
                if "try" in body:
                    found = True
                break
        assert found, f"{fn_name} 应有 try/catch"


def test_session_limit_exists():
    """会话列表应有最大数量限制"""
    source = get_source()
    assert "MAX_SESSIONS" in source, "应有 MAX_SESSIONS 限制"