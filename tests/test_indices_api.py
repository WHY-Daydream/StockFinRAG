import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from api_server import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


class TestIndicesAPI:
    def test_indices_endpoint_returns_json(self, client):
        """GET /api/indices 应返回 JSON"""
        resp = client.get('/api/indices')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "indices" in data

    def test_indices_endpoint_structure(self, client):
        """返回的指数数据应有 code/name/close 字段"""
        resp = client.get('/api/indices')
        data = json.loads(resp.data)
        for idx in data["indices"]:
            assert "code" in idx
            assert "name" in idx
            assert "close" in idx