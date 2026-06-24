import sys
import os
import json

import pytest
from flask import Flask
from pydantic import ValidationError

# Ensure app/ is on the path
test_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(test_dir)
sys.path.insert(0, app_dir)

from schemas.request import AskRequest, IngestRequest, SeedRequest, CrawlRequest
from schemas.response import AskResponse, HealthResponse, IngestResponse, SeedResponse, ErrorResponse
from schemas import validate_or_error


@pytest.fixture
def app():
    """Minimal Flask app for tests that need an app context."""
    return Flask(__name__)


# ---------- AskRequest ----------

class TestAskRequest:
    def test_ask_request_valid(self):
        m = AskRequest(question="净利润是多少")
        assert m.question == "净利润是多少"
        assert m.session_id == ""
        assert m.history is None

    def test_ask_request_missing_question(self):
        with pytest.raises(ValidationError):
            AskRequest()

    def test_ask_request_empty_question(self):
        with pytest.raises(ValidationError):
            AskRequest(question="")

    def test_ask_request_session_default(self):
        m = AskRequest(question="你好", session_id="sess_001")
        assert m.session_id == "sess_001"
        assert m.question == "你好"


# ---------- IngestRequest ----------

class TestIngestRequest:
    def test_ingest_request_default(self):
        m = IngestRequest()
        assert m.limit == 10

    def test_ingest_request_custom(self):
        m = IngestRequest(limit=25)
        assert m.limit == 25

    def test_ingest_request_limit_too_low(self):
        with pytest.raises(ValidationError):
            IngestRequest(limit=0)

    def test_ingest_request_limit_too_high(self):
        with pytest.raises(ValidationError):
            IngestRequest(limit=101)


# ---------- SeedRequest ----------

class TestSeedRequest:
    def test_seed_request_default(self):
        m = SeedRequest()
        assert m.limit == 50


# ---------- CrawlRequest ----------

class TestCrawlRequest:
    def test_crawl_request_default(self):
        m = CrawlRequest()
        assert m.config is None


# ---------- Response models ----------

class TestResponseModels:
    def test_health_response_default(self):
        m = HealthResponse()
        assert m.status == "ok"
        assert m.service == "StockFinRAG"


# ---------- validate_or_error ----------

class TestValidateHelper:
    def test_validate_helper_valid(self):
        model, err = validate_or_error(AskRequest, {"question": "净利润趋势"})
        assert err is None
        assert model is not None
        assert model.question == "净利润趋势"

    def test_validate_helper_invalid(self, app):
        with app.app_context():
            model, err = validate_or_error(AskRequest, {"question": ""})
            assert model is None
            assert err is not None
            response, status_code = err
            assert status_code == 422
            data = response.get_json()
            assert data["error"] == "validation_error"
            assert "field" in data["detail"][0]
            assert "msg" in data["detail"][0]
