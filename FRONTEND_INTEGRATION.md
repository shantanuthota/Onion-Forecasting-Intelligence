# Frontend integration contract — v4

Base URL locally: `http://127.0.0.1:8000`

All graph endpoints support `horizon_days=7|14|30|60|90`. Forecast price outputs are in INR/kg. The SQLite observations table retains historical prices in INR/metric quintal; actual-history values in the graph API are converted at response time to INR/kg so chart lines are comparable. Forecast price quantiles are converted to INR/kg and saved to SQLite.

## Graph 1 — AP prices

`GET /api/graphs/ap-retail?horizon_days=14&price_types=retail,wholesale,mandi_modal&history_days=90`

- `price_types`: comma-separated `retail`, `wholesale`, `mandi_modal`.
- `historical`: `date`, `state`, `price_type`, `actual_price_rs_kg`.
- `forecast`: `date`, `state`, `price_type`, `predicted_price_rs_kg`, `p10_rs_kg`, `p50_rs_kg`, `p90_rs_kg`.
- `saved_to_sqlite`: run ID and number of saved quantile rows.

Target logic:
- retail uses past AP retail, wholesale and mandi modal; future wholesale and mandi modal values are first forecast as covariates.
- wholesale uses only its own past series.
- mandi modal uses only its own past series.

## Graph 2 — state comparison

`GET /api/graphs/state-comparison?states=AP,MH&price_types=retail,wholesale,mandi_modal&horizon_days=30`

- `states`: any comma-separated subset of `AP`, `KA`, `MH`, `MP`.
- `price_types`: any subset of `retail`, `wholesale`, `mandi_modal`.
- Only selected states and series are returned and saved.
- Retail uses each state's own retail/wholesale/mandi history; wholesale and mandi modal each use only their own history.

## Graph 3 — supply / consumption / shortfall

`GET /api/graphs/supply-balance?states=AP&horizon_days=30`

- `quantity_forecast`: `metric` is `supply` or `consumption`, with P10/P50/P90 in `metric_quintal/day`.
- `balance_forecast`: `shortfall_p50_metric_quintal_day` and bounds; formula is `supply - consumption`. Negative = potential shortfall; positive = potential surplus.
- Supply is created from historical arrival + production and forecast as a univariate target. Consumption is forecast as a separate univariate target. Shortfall is calculated, not independently forecast.

## Forecast persistence endpoints

- `GET /api/forecasts/latest` — latest saved forecast run.
- `GET /api/forecasts/latest?graph_code=graph1_ap_prices` — latest Graph 1 run.
- `GET /api/forecasts/runs?limit=20` — recent saved runs.

## Data ingestion

- `GET /api/ingestion/status` — SQLite history and last ingestion status.
- `POST /api/ingestion/sync-csv?filename=Onion_Model_Ready_Dataset_Chronos2_2026-10-26_Interpolated_Metric_Quintal.csv` with `X-Ingestion-Key` header — imports a combined CSV located inside `data/`. Set `INGESTION_API_KEY` in `.env` first.
