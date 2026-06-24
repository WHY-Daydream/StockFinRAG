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
    assert first.startswith("event:")
    assert "data:" in first