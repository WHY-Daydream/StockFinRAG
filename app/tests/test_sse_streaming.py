"""SSE 流式响应测试"""


def test_qa_service_has_ask_stream():
    from service.qa_service import QAAnswerService
    svc = QAAnswerService()
    assert hasattr(svc, "ask_stream")


def test_ask_stream_is_generator():
    from service.qa_service import QAAnswerService
    svc = QAAnswerService()
    result = svc.ask_stream("test", "sess-1")
    from collections.abc import Generator
    assert isinstance(result, Generator)


def test_stream_first_event_is_valid_sse():
    """模拟一小步，验证 SSE 格式"""
    from service.qa_service import QAAnswerService
    svc = QAAnswerService()
    gen = svc.ask_stream("test_q", "sess_1")
    first = next(gen)
    # 第一个事件可能是 :connected（注释）或 event:（缓存命中）
    assert first.startswith("event:") or first.startswith(":"), f"Unexpected SSE: {first[:50]}"


def test_stream_route_exists():
    with open("api_server.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "ask/stream" in source
    assert "event-stream" in source


def test_stream_route_returns_sse_headers():
    with open("api_server.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "text/event-stream" in source
    assert "X-Accel-Buffering" in source


def test_chat_js_has_stream_function():
    with open("static/js/chat.js", "r", encoding="utf-8") as f:
        source = f.read()
    assert "sendQuestionStream" in source or "ask/stream" in source