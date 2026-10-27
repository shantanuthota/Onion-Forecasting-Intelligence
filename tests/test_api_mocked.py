"""API contract tests using a fake predictor; no model weights/network needed."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from fastapi.testclient import TestClient
import history_store
import main


class FakeChronosPipeline:
    calls = []
    def predict_df(self, df, future_df, id_column, timestamp_column, target,
                   prediction_length, quantile_levels, freq):
        self.calls.append({"columns": list(df.columns), "future_columns": list(future_df.columns), "target": target})
        recent = float(pd.to_numeric(df[target], errors="coerce").dropna().iloc[-1])
        rows = []
        for i, ts in enumerate(future_df[timestamp_column]):
            median = max(0.0, recent * (1 + (i + 1) * 0.0005))
            rows.append({id_column: future_df[id_column].iloc[i], timestamp_column: ts,
                         "target_name": target, "predictions": median,
                         "0.1": median * .95, "0.5": median, "0.9": median * 1.05})
        return pd.DataFrame(rows)


def client_with_fake(monkeypatch, tmp_path):
    monkeypatch.setattr(history_store, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(main, "get_pipeline", lambda: FakeChronosPipeline())
    main._PREDICTION_CACHE.clear()
    FakeChronosPipeline.calls = []
    return TestClient(main.app)


def test_graph1_retail_uses_only_requested_context_and_converts_forecast(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/ap-retail?horizon_days=7&price_types=retail")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["forecast"]) == 7
    assert body["forecast"][0]["date"] == "2026-10-27"
    assert body["unit"] == "INR/kg"
    assert body["price_types"] == ["retail"]
    assert body["model_history_rows"] == 1760
    # Retail target context contains only date/id, AP retail, AP wholesale and AP mandi modal.
    retail_calls = [c for c in FakeChronosPipeline.calls if c["target"] == "AP_retail_rs_per_metric_quintal"]
    assert len(retail_calls) == 1
    assert set(retail_calls[0]["columns"]) == {"item_id", "timestamp", "AP_retail_rs_per_metric_quintal", "AP_wholesale_rs_per_metric_quintal", "AP_mandi_modal_rs_per_metric_quintal"}
    # Forecast median is converted from ₹/metric quintal to ₹/kg.
    assert body["forecast"][0]["predicted_price_rs_kg"] < 100
    assert body["saved_to_sqlite"]["saved_values"] == 7
    latest = client.get("/api/forecasts/latest?graph_code=graph1_ap_prices").json()["forecast"]
    assert latest is not None and latest["forecast_values"][0]["unit"] == "INR/kg"


def test_graph1_all_three_price_series(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/ap-retail?horizon_days=90&price_types=retail,wholesale,mandi_modal")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["forecast"]) == 270
    assert set(body["price_types"]) == {"retail", "wholesale", "mandi_modal"}
    assert body["saved_to_sqlite"]["saved_values"] == 270


def test_graph2_only_selected_states_and_series(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/state-comparison?states=KA,MP&price_types=retail,wholesale,mandi_modal&horizon_days=14")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["selected_states"] == ["KA", "MP"]
    assert {r["state"] for r in body["forecast"]} == {"KA", "MP"}
    assert {r["price_type"] for r in body["forecast"]} == {"retail", "wholesale", "mandi_modal"}
    assert len(body["forecast"]) == 14 * 2 * 3
    assert body["saved_to_sqlite"]["saved_values"] == 84


def test_graph3_supply_consumption_and_shortfall(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/supply-balance?states=AP&horizon_days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["quantity_forecast"]) == 14
    assert {r["metric"] for r in body["quantity_forecast"]} == {"supply", "consumption"}
    assert len(body["balance_forecast"]) == 7
    assert body["balance_formula"] == "supply - consumption"
    assert body["saved_to_sqlite"]["saved_values"] == 21
    supply_calls = [c for c in FakeChronosPipeline.calls if c["target"] == "AP_supply_metric_quintal_per_day"]
    assert len(supply_calls) == 1
    assert set(supply_calls[0]["columns"]) == {"item_id", "timestamp", "AP_supply_metric_quintal_per_day"}


def test_forecast_saved_runs_endpoint(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/ap-retail?horizon_days=7&price_types=wholesale")
    assert response.status_code == 200
    runs = client.get("/api/forecasts/runs").json()["runs"]
    assert len(runs) >= 1
    assert runs[0]["graph_code"] == "graph1_ap_prices"


def test_invalid_horizon_rejected(monkeypatch, tmp_path):
    client = client_with_fake(monkeypatch, tmp_path)
    response = client.get("/api/graphs/ap-retail?horizon_days=10")
    assert response.status_code == 422
