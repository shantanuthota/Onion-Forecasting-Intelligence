# Onion Forecasting Intelligence — API Documentation

This document covers all API endpoints, parameters, request headers, service logic, and response schemas implemented across the codebase (`main.py`, `history_store.py`, and `upag_client.py`).

---

## Quick Reference & Base URL

- **Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **Model Engine**: Amazon Chronos-2 (`amazon/chronos-2`) probabilistic zero-shot time-series model
- **Database**: SQLite (`data/onion_forecasting_v4.sqlite3`)
- **Key Units**:
  - Observation prices in SQLite: ₹ / metric quintal
  - Forecast prices in API & persistence: ₹ / kg (converted automatically: divide by 100)
  - Historical prices returned in graphs: ₹ / kg (converted for direct comparison with forecasts)
  - Quantities (Arrival, Production, Consumption, Supply): Metric quintals / day

---

## 1. Core Forecasting Graph APIs

These endpoints execute Chronos-2 predictions on historical market data and automatically persist forecast runs and quantile values to SQLite.

### 1.1 Graph 1: Andhra Pradesh (AP) Price Forecast
*Endpoint for predicting retail, wholesale, and mandi modal onion prices for Andhra Pradesh.*

- **Method**: `GET`
- **Path**: `/api/graphs/ap-retail`
- **Description**: Returns historical observations and future forecasts for Andhra Pradesh. Retail price forecasts use multivariate covariates (wholesale and mandi modal prices as covariates forecast beforehand). Wholesale and mandi modal prices are forecast as univariate series.

#### Query Parameters:
| Parameter | Type | Required | Default | Allowed Values / Constraints | Description |
|---|---|---|---|---|---|
| `horizon_days` | integer | No | `14` | `7`, `14`, `30`, `60`, `90` | Forecast window length in days. |
| `price_types` | string | No | `retail` | Comma-separated: `retail`, `wholesale`, `mandi_modal` | Price series to include. Case-insensitive. |
| `history_days` | integer | No | `90` | `1` to `1825` (days) | Visible historical days to return for graph display (model always uses full history). |

#### Target & Covariate Logic:
- **`retail`**: Context uses Date + AP Retail + AP Wholesale + AP Mandi Modal. Future wholesale and mandi modal values are independently forecast first, then supplied as known future covariates.
- **`wholesale`**: Context uses Date + AP Wholesale only.
- **`mandi_modal`**: Context uses Date + AP Mandi Modal only.

#### Example Request:
```http
GET /api/graphs/ap-retail?horizon_days=14&price_types=retail,wholesale,mandi_modal&history_days=90
```

#### Sample Output:
```json
{
  "graph": "ap_price_forecast",
  "title": "Andhra Pradesh Onion Price Forecast",
  "state": "AP",
  "state_name": "Andhra Pradesh",
  "price_types": ["retail", "wholesale", "mandi_modal"],
  "unit": "INR/kg",
  "horizon_days": 14,
  "model_history_rows": 1760,
  "visible_history_days": 90,
  "context_logic": {
    "retail": ["timestamp", "AP_retail_rs_per_metric_quintal", "AP_wholesale_rs_per_metric_quintal", "AP_mandi_modal_rs_per_metric_quintal"],
    "wholesale": ["timestamp", "AP_wholesale_rs_per_metric_quintal"],
    "mandi_modal": ["timestamp", "AP_mandi_modal_rs_per_metric_quintal"]
  },
  "historical": [
    {
      "date": "2026-07-18",
      "state": "AP",
      "price_type": "retail",
      "price_type_label": "Retail price",
      "actual_price_rs_kg": 32.50
    },
    ...
  ],
  "forecast": [
    {
      "date": "2026-10-16",
      "state": "AP",
      "state_name": "Andhra Pradesh",
      "price_type": "retail",
      "price_type_label": "Retail price",
      "predicted_price_rs_kg": 34.20,
      "p10_rs_kg": 30.10,
      "p50_rs_kg": 34.20,
      "p90_rs_kg": 38.80,
      "prediction_interval_width_rs_kg": 8.70,
      "interval_width_pct_of_median": 25.44
    },
    ...
  ],
  "metadata": {
    "model": "amazon/chronos-2",
    "frequency": "daily",
    "observation_price_unit": "INR/metric quintal",
    "forecast_price_unit": "INR/kg",
    "quantiles": {"lower": 0.1, "median": 0.5, "upper": 0.9},
    "prediction_interval": {
      "nominal_coverage": 0.8,
      "description": "P10–P90 is a nominal central 80% prediction interval, not a guarantee."
    }
  },
  "saved_to_sqlite": {
    "run_id": 1,
    "generated_at": "2026-10-27T18:00:00Z",
    "saved_values": 42,
    "graph_code": "graph1_ap_prices"
  },
  "last_observation_date": "2026-10-15",
  "data_staleness_days": 12,
  "forecast_start_date": "2026-10-16",
  "forecast_end_date": "2026-10-29",
  "warnings": [
    "Latest observation is 2026-10-15 (12 day(s) behind the server date)."
  ]
}
```

---

### 1.2 Graph 2: Multi-State Price Comparison
*Endpoint for comparing onion prices across key producing and consuming states.*

- **Method**: `GET`
- **Path**: `/api/graphs/state-comparison`
- **Description**: Compares onion prices across any combination of supported states (`AP`, `KA`, `MH`, `MP`) and price types.

#### Query Parameters:
| Parameter | Type | Required | Default | Allowed Values / Constraints | Description |
|---|---|---|---|---|---|
| `states` | string | No | `AP,KA,MH,MP` | Comma-separated: `AP`, `KA`, `MH`, `MP` | States to forecast and compare. |
| `price_types` | string | No | `retail,wholesale,mandi_modal` | Comma-separated: `retail`, `wholesale`, `mandi_modal` | Price types to include. |
| `horizon_days` | integer | No | `14` | `7`, `14`, `30`, `60`, `90` | Forecast window length in days. |
| `history_days` | integer | No | `90` | `30` to `730` (days) | Visible historical observations to return. |

#### Example Request:
```http
GET /api/graphs/state-comparison?states=AP,MH&price_types=retail,wholesale&horizon_days=30&history_days=90
```

#### Sample Output:
```json
{
  "graph": "state_price_comparison",
  "title": "Selected States — Onion Price Forecasts",
  "selected_states": ["AP", "MH"],
  "selected_state_names": ["Andhra Pradesh", "Maharashtra"],
  "selected_price_types": ["retail", "wholesale"],
  "horizon_days": 30,
  "unit": "INR/kg",
  "historical": [
    {
      "date": "2026-07-18",
      "state": "MH",
      "price_type": "wholesale",
      "price_type_label": "Wholesale price",
      "actual_price_rs_kg": 24.10
    },
    ...
  ],
  "forecast": [
    {
      "date": "2026-10-16",
      "state": "MH",
      "state_name": "Maharashtra",
      "price_type": "wholesale",
      "price_type_label": "Wholesale price",
      "predicted_price_rs_kg": 26.50,
      "p10_rs_kg": 23.20,
      "p50_rs_kg": 26.50,
      "p90_rs_kg": 30.10,
      "prediction_interval_width_rs_kg": 6.90,
      "interval_width_pct_of_median": 26.04
    },
    ...
  ],
  "metadata": { "...": "..." },
  "saved_to_sqlite": {
    "run_id": 2,
    "generated_at": "2026-10-27T18:05:00Z",
    "saved_values": 120,
    "graph_code": "graph2_state_comparison"
  },
  "last_observation_date": "2026-10-15",
  "data_staleness_days": 12,
  "forecast_start_date": "2026-10-16",
  "forecast_end_date": "2026-11-14",
  "warnings": [ "..." ]
}
```

---

### 1.3 Graph 3: Supply, Consumption & Balance (Shortfall) Forecast
*Endpoint for predicting quantity flows and estimated surplus / deficit.*

- **Method**: `GET`
- **Path**: `/api/graphs/supply-balance`
- **Description**: Forecasts onion supply (`arrival + production`) and `consumption` as independent univariate targets in metric quintals/day. Calculates shortfall as `supply - consumption` with conservative component bounds.

#### Query Parameters:
| Parameter | Type | Required | Default | Allowed Values / Constraints | Description |
|---|---|---|---|---|---|
| `states` | string | No | `AP` | Comma-separated: `AP`, `KA`, `MH`, `MP` | States to calculate balance for. |
| `horizon_days` | integer | No | `14` | `7`, `14`, `30`, `60`, `90` | Forecast window length in days. |
| `history_days` | integer | No | `90` | `30` to `730` (days) | Visible historical observations to return. |

#### Formula & Logic:
- **Supply**: Historical `arrival + production` (in metric quintals/day), forecast as a univariate series.
- **Consumption**: Historical daily consumption, forecast as a univariate series.
- **Shortfall Formula**: `Shortfall = Supply - Consumption`
  - $P_{50} = \text{Supply } P_{50} - \text{Consumption } P_{50}$
  - $P_{10} = \text{Supply } P_{10} - \text{Consumption } P_{90}$ (conservative lower bound)
  - $P_{90} = \text{Supply } P_{90} - \text{Consumption } P_{10}$ (conservative upper bound)
  - **Classification**: `potential_surplus` (if $P_{50} > 0$), `potential_shortfall` (if $P_{50} < 0$), or `near_balance` (if $P_{50} = 0$).

#### Example Request:
```http
GET /api/graphs/supply-balance?states=AP&horizon_days=14&history_days=90
```

#### Sample Output:
```json
{
  "graph": "supply_demand_shortfall",
  "title": "Onion Supply, Consumption and Shortfall Forecast",
  "selected_states": ["AP"],
  "selected_state_names": ["Andhra Pradesh"],
  "horizon_days": 14,
  "quantity_unit": "metric_quintal/day",
  "historical": [
    {
      "date": "2026-07-18",
      "state": "AP",
      "state_name": "Andhra Pradesh",
      "metric": "supply",
      "actual_quantity_mq_day": 4520.0,
      "unit": "metric_quintal/day"
    }
  ],
  "quantity_forecast": [
    {
      "date": "2026-10-16",
      "state": "AP",
      "state_name": "Andhra Pradesh",
      "metric": "supply",
      "predicted_quantity_mq_day": 4350.25,
      "p10_mq_day": 3900.0,
      "p50_mq_day": 4350.25,
      "p90_mq_day": 4800.5,
      "unit": "metric_quintal/day"
    },
    {
      "date": "2026-10-16",
      "state": "AP",
      "state_name": "Andhra Pradesh",
      "metric": "consumption",
      "predicted_quantity_mq_day": 4600.0,
      "p10_mq_day": 4400.0,
      "p50_mq_day": 4600.0,
      "p90_mq_day": 4850.0,
      "unit": "metric_quintal/day"
    }
  ],
  "balance_forecast": [
    {
      "date": "2026-10-16",
      "state": "AP",
      "state_name": "Andhra Pradesh",
      "shortfall_p10_metric_quintal_day": -950.0,
      "shortfall_p50_metric_quintal_day": -249.75,
      "shortfall_p90_metric_quintal_day": 400.5,
      "classification": "potential_shortfall"
    }
  ],
  "balance_formula": "supply - consumption",
  "warnings": [
    "Supply is calculated as arrivals + production as requested; confirm that arrivals and production are compatible flows and do not double-count the same supply.",
    "The source production/consumption series repeat across many daily rows; verify their real reporting frequency before interpreting daily forecasts.",
    "Shortfall is supply minus consumption: negative values indicate demand exceeds supply; positive values indicate surplus.",
    "Shortfall P10/P90 combine component quantiles conservatively and are not a calibrated joint prediction interval."
  ],
  "saved_to_sqlite": {
    "run_id": 3,
    "generated_at": "2026-10-27T18:10:00Z",
    "saved_values": 42,
    "graph_code": "graph3_supply_balance"
  },
  "last_observation_date": "2026-10-15",
  "data_staleness_days": 12,
  "forecast_start_date": "2026-10-16",
  "forecast_end_date": "2026-10-29"
}
```

---

## 2. Forecast Persistence & Run History APIs

Every forecast generated by the graph endpoints is automatically stored in SQLite. These endpoints allow querying stored runs.

### 2.1 Get Latest Saved Forecast
- **Method**: `GET`
- **Path**: `/api/forecasts/latest`
- **Description**: Returns the latest forecast run and its detailed predicted quantile values.

#### Query Parameters:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `graph_code` | string | No | `null` | Optional filter: `graph1_ap_prices`, `graph2_state_comparison`, or `graph3_supply_balance`. If omitted, returns the latest run across all graphs. |

#### Sample Output:
```json
{
  "forecast": {
    "run_id": 12,
    "graph_code": "graph1_ap_prices",
    "generated_at": "2026-10-27T17:45:10Z",
    "model_id": "amazon/chronos-2",
    "horizon_days": 14,
    "last_observation_date": "2026-10-15",
    "context_hash": "a1b2c3d4e5f6789012345678",
    "metadata": {
      "stored_forecast_price_unit": "INR/kg",
      "observation_price_unit": "INR/metric quintal",
      "quantiles": [0.1, 0.5, 0.9]
    },
    "forecast_values": [
      {
        "state_code": "AP",
        "target_key": "retail",
        "forecast_date": "2026-10-16",
        "p10": 30.12,
        "p50": 34.50,
        "p90": 39.20,
        "unit": "INR/kg"
      }
    ]
  }
}
```

---

### 2.2 List Recent Forecast Runs
- **Method**: `GET`
- **Path**: `/api/forecasts/runs`
- **Description**: Returns a summary list of past forecast runs (without expanding individual value rows).

#### Query Parameters:
| Parameter | Type | Required | Default | Allowed Values | Description |
|---|---|---|---|---|---|
| `limit` | integer | No | `20` | `1` to `100` | Number of recent runs to return. |

#### Sample Output:
```json
{
  "runs": [
    {
      "run_id": 12,
      "graph_code": "graph1_ap_prices",
      "generated_at": "2026-10-27T17:45:10Z",
      "model_id": "amazon/chronos-2",
      "horizon_days": 14,
      "last_observation_date": "2026-10-15",
      "context_hash": "a1b2c3d4e5f6789012345678"
    },
    {
      "run_id": 11,
      "graph_code": "graph3_supply_balance",
      "generated_at": "2026-10-27T17:30:22Z",
      "model_id": "amazon/chronos-2",
      "horizon_days": 30,
      "last_observation_date": "2026-10-15",
      "context_hash": "b2c3d4e5f6a1789012345678"
    }
  ]
}
```

---

## 3. Data Health, Staleness & Ingestion APIs

These endpoints provide observability into the underlying SQLite database, observation freshness, and dataset synchronization.

### 3.1 Service Root
- **Method**: `GET`
- **Path**: `/`
- **Description**: Entrypoint providing API service information, links to Swagger UI docs, and sample graph endpoints.

#### Sample Output:
```json
{
  "service": "Onion Forecasting MVP API v3",
  "docs": "/docs",
  "graphs": {
    "graph_1_ap_prices": "/api/graphs/ap-retail?horizon_days=14&price_types=retail,wholesale,mandi_modal",
    "graph_2_state_comparison": "/api/graphs/state-comparison?states=AP,MH&price_types=retail,wholesale,mandi_modal&horizon_days=14",
    "graph_3_supply_balance": "/api/graphs/supply-balance?states=AP&horizon_days=14"
  },
  "ops": {
    "health": "/health",
    "ingestion_status": "/api/ingestion/status",
    "saved_forecasts": "/api/forecasts/latest"
  }
}
```

---

### 3.2 Health Check
- **Method**: `GET`
- **Path**: `/health`
- **Description**: Verifies API operational status, SQLite connection, whether Chronos-2 pipeline is loaded in memory, and dataset staleness relative to system clock.

#### Sample Output:
```json
{
  "status": "ok",
  "model_loaded": true,
  "model_id": "amazon/chronos-2",
  "history_db": "c:\\Users\\user\\Desktop\\Onion-Forecasting-Intelligence\\data\\onion_forecasting_v4.sqlite3",
  "ingestion": {
    "database_path": "c:\\Users\\user\\Desktop\\Onion-Forecasting-Intelligence\\data\\onion_forecasting_v4.sqlite3",
    "observation_rows": 1760,
    "first_observation_date": "2022-01-01",
    "last_observation_date": "2026-10-15",
    "forecast_run_count": 12,
    "last_ingestion": {
      "id": 1,
      "checked_at": "2026-10-27T10:00:00Z",
      "source": "initial_csv_seed",
      "status": "success",
      "rows_seen": 1760,
      "inserted": 1760,
      "updated": 0,
      "unchanged": 0,
      "latest_observation_date": "2026-10-15",
      "message": null
    }
  },
  "last_observation_date": "2026-10-15",
  "data_staleness_days": 12,
  "forecast_start_date": "2026-10-16",
  "warnings": [
    "Latest observation is 2026-10-15 (12 day(s) behind the server date)."
  ]
}
```

---

### 3.3 Data Status
- **Method**: `GET`
- **Path**: `/api/data/status`
- **Description**: Lightweight overview of observation freshness, staleness warning, and last sync summary.

---

### 3.4 Ingestion Status
- **Method**: `GET`
- **Path**: `/api/ingestion/status`
- **Description**: Returns database statistics including total observation rows, date span, total forecast runs, and the latest ingestion audit log.

---

### 3.5 Sync / Import Model-Ready CSV
- **Method**: `POST`
- **Path**: `/api/ingestion/sync-csv`
- **Description**: Performs a timestamp-based upsert of a combined model-ready CSV located inside the `data/` directory into the SQLite database. Invalidates the prediction cache. Protected by an API key header.

#### Headers:
| Header | Type | Required | Description |
|---|---|---|---|
| `X-Ingestion-Key` | string | **Yes** | Secret token matching `INGESTION_API_KEY` defined in `.env`. |

#### Query Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `filename` | string | **Yes** | Name of the CSV file inside `data/` (e.g. `Onion_Model_Ready_Dataset_Chronos2.csv`). Cannot contain directory traversal paths. |

#### Sample Request:
```http
POST /api/ingestion/sync-csv?filename=Onion_Model_Ready_Dataset_Chronos2_2026-10-26_Interpolated_Metric_Quintal.csv
X-Ingestion-Key: your-secret-key-here
```

#### Sample Output:
```json
{
  "status": "success",
  "source": "csv_import:Onion_Model_Ready_Dataset_Chronos2_2026-10-26_Interpolated_Metric_Quintal.csv",
  "rows_seen": 1760,
  "inserted": 0,
  "updated": 15,
  "unchanged": 1745,
  "latest_observation_date": "2026-10-15",
  "history": {
    "database_path": "c:\\...\\data\\onion_forecasting_v4.sqlite3",
    "observation_rows": 1760,
    "first_observation_date": "2022-01-01",
    "last_observation_date": "2026-10-15",
    "forecast_run_count": 12
  }
}
```

---

## 4. External Data Integration Service: UPAg Client (`upag_client.py`)

This service integrates with the government **UPAg (Unified Portal for Agricultural Statistics)** Open API at `https://data.upag.gov.in`. It securely manages authentication and raw source extraction without altering schema.

### Endpoints Consumed:
| Method | UPAg Path | Service Function | Description |
|---|---|---|---|
| `POST` | `/v1/upag/api-data-share/login` | `UPAgClient.login()` | Authenticates using credentials in `.env` (`UPAG_USERNAME`, `UPAG_PASSWORD`, `UPAG_CLIENT_ID`, `UPAG_CLIENT_SECRET`) via OAuth2 password grant to acquire a Bearer token. |
| `GET` | `/v1/upag/api-data-share/sources/user-allowed-sources` | `UPAgClient.allowed_sources()` | Returns the list of datasets/sources authorized for the account. |
| `POST` | `/v1/upag/api-data-share/sources/{source_name}` | `UPAgClient.fetch_source(source_name, payload)` | Queries a specific allowed source with a user-supplied JSON filter object. |

### Allowed Sources Supported:
`agmarknet`, `dafw_state`, `dafw_district`, `doca`, `enam`, `horticulture`, `fci_procurement`, `fci_stock`, `mncfc`, `ieg`, `dcs`, `dgcis`, `farmers_survey`, `nsso`, `cwwg`, `pmfby_ay`, `trs`, `state_reported`, `sopa`, `wpi`, `ncdex`, `pink_sheet`.

### CLI Service Usage:
```powershell
# 1. List sources allowed for your account:
python upag_client.py --list-sources

# 2. Fetch raw source data using a JSON payload file:
python upag_client.py --source agmarknet --payload-file payload.json --output data/raw_agmarknet.json
```

---

## 5. Summary of Error Codes & HTTP Statuses

| Status Code | Reason | Cause |
|---|---|---|
| `200 OK` | Success | Request succeeded and forecast/data returned. |
| `400 Bad Request` | Invalid filename | `sync-csv` filename contains path separators or does not end with `.csv`. |
| `401 Unauthorized` | Invalid API Key | `X-Ingestion-Key` header is missing or does not match `.env`. |
| `404 Not Found` | File not found | CSV file specified in `sync-csv` was not found in `data/`. |
| `422 Unprocessable Entity` | Parameter validation error | Invalid `horizon_days` (must be 7, 14, 30, 60, 90), unsupported state code, or invalid price type. |
| `500 Internal Server Error` | Execution error | Missing required column in SQLite, or Chronos-2 pipeline failure. |
| `503 Service Unavailable` | Service or Model not ready | Model dependencies missing, or `INGESTION_API_KEY` left as placeholder default. |
