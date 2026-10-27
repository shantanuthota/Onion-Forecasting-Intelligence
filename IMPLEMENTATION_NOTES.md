# Graph-specific forecasting and SQLite persistence

## Canonical observation data

The default input is `data/Onion_Model_Ready_Dataset_Chronos2_2026-10-26_Interpolated_Metric_Quintal.csv` (1,760 daily rows, 2022-01-01 through 2026-10-26).

SQLite observations keep prices in INR per metric quintal and quantities in metric quintals. The latest cleaned dataset is imported automatically into SQLite at first start and re-imported when its configured CSV changes. Forecast price values alone are persisted in the forecast table in INR/kg. Historical API values are converted only in the response layer to keep chart lines in comparable INR/kg units; observation values in SQLite remain unchanged.

## Explicit target/context rules

### Graph 1 — Andhra Pradesh

- AP retail target: `AP_retail_rs_per_metric_quintal`; historical context is timestamp + AP retail + AP wholesale + AP mandi modal. Because future wholesale and mandi values are not known, Chronos-2 first forecasts each of those two series univariately and passes those forecast medians as future covariates to the AP retail target forecast.
- AP wholesale target: timestamp + AP wholesale only.
- AP mandi modal target: timestamp + AP mandi modal only.
- The UI/API can request any subset using `price_types=retail,wholesale,mandi_modal`.

### Graph 2 — selected states

Same logic as Graph 1, applied independently for each selected state. Only selected states/price types are returned and persisted for that graph run.

### Graph 3 — supply / consumption / shortfall

- Historical supply is derived as `arrival + production` for each state.
- Supply target context: timestamp + derived supply only.
- Consumption target context: timestamp + consumption only.
- `shortfall = supply - consumption`; negative values mean potential shortfall, positive values mean potential surplus.
- Shortfall is derived from the supply and consumption forecasts and stored alongside them. It is not a separate Chronos target.

## Forecast persistence

Every successful graph endpoint call creates a row in `forecast_runs` and saves its forecast quantiles in `forecast_values`. Each saved value has graph run, state, target, forecast date, P10/P50/P90 and unit. Price forecast values are stored in INR/kg; quantity and shortfall values are stored in metric quintals/day. Inspect them with:

- `GET /api/forecasts/latest?graph_code=graph1_ap_prices`
- `GET /api/forecasts/runs`

## Important modelling caveats

- The Chronos-2 inference path is implemented using the selected context columns. Real Chronos-2 inference still needs to be run in the user's local environment with the model dependencies and weights installed.
- The retail model needs future covariate values; this implementation forecasts future wholesale and mandi modal prices first instead of leaking unknown actual future values.
- Supply = arrivals + production and shortfall = supply − consumption follow the requested business logic. Confirm compatible units/time periods and whether arrivals overlap production before treating the result as a true state-level surplus/shortfall.
- Production and consumption may be repeated periodic estimates rather than genuine daily observations; daily forecasts should be evaluated before operational use.
- P10/P50/P90 are quantiles, not a scalar confidence score.
