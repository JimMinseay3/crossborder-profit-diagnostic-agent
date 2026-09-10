import os
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test.db")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_profit_math_and_anomalies():
    response = client.post("/api/runs", json={"example": "profit_ledger.csv"})
    assert response.status_code == 200
    result = response.json()["result"]
    expected = result["totals"]["revenue"] - result["totals"]["refunds"] - result["totals"]["cogs"] - result["totals"]["amazon_fees"] - result["totals"]["ad_spend"] - result["totals"]["shipping"]
    assert abs(result["totals"]["net_profit"] - expected) < 0.01
    assert result["currency"] == "USD"
    assert result["anomalies"]


def test_rejects_incomplete_csv():
    response = client.post("/api/runs", json={"file_name": "x.csv", "file_content": "sku,revenue\nA,1"})
    assert response.status_code == 422

