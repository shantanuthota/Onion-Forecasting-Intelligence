"""Streamlit visual QA dashboard for the three onion forecasting graphs.

This dashboard is for model/response inspection. The production frontend team can
consume the same FastAPI endpoints; see FRONTEND_INTEGRATION.md.
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
import requests
import streamlit as st
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

st.set_page_config(page_title="AP Civil Supplies · Onion Outlook", page_icon="🧅", layout="wide")

# Align the local visual QA tool with the supplied AP Civil Supplies frontend reference.
st.markdown("""
<style>
  .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px; }
  .app-kicker { color:#657080; font-size:.79rem; letter-spacing:.07em; text-transform:uppercase; }
  .hero { border:1px solid #e4e8ef; border-radius:18px; padding:20px 24px; background:linear-gradient(115deg,#ffffff 0%,#f8fafc 100%); margin: 0.4rem 0 1.5rem; }
  .hero-title { font-size:1.7rem; font-weight:750; color:#161c28; margin:0; }
  .hero-sub { color:#687385; margin-top:4px; font-size:.94rem; }
  .section-title { font-size:1.55rem; font-weight:750; letter-spacing:-.025em; color:#171c27; margin: .5rem 0 0; }
  .section-subtitle { color:#697586; font-size:.91rem; margin:.15rem 0 .8rem; }
  .section-rule { border:0; border-top:1px solid #edf0f4; margin:1.6rem 0; }
  div[data-testid="stMetric"] { border:1px solid #e9edf2; border-radius:12px; padding:13px 15px; background:#fff; }
  div[data-testid="stMetricLabel"] { color:#647083; }
  .data-note { font-size:.82rem; color:#697586; }
  div.stButton > button[kind="primary"] { border-radius:10px; }
</style>
""", unsafe_allow_html=True)

STATE_LABELS = {
    "AP": "Andhra Pradesh",
    "KA": "Karnataka",
    "MH": "Maharashtra",
    "MP": "Madhya Pradesh",
}
HORIZONS = [7, 14, 30, 60, 90]
HORIZON_LABELS = {7: "1W", 14: "2W", 30: "1M", 60: "2M", 90: "3M"}
STATE_COLORS = {"AP": "#4469a8", "KA": "#bd6b88", "MH": "#9270b5", "MP": "#599a91"}
PRICE_COLORS = {"retail": "#4469a8", "mandi_modal": "#b28a3b", "wholesale": "#b28a3b"}

with st.sidebar:
    st.header("Connection")
    api_base = st.text_input(
        "FastAPI base URL", value=os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    ).strip().rstrip("/")
    st.markdown(f"[Open API docs]({api_base}/docs)")
    if st.button("Check API health", use_container_width=True):
        try:
            response = requests.get(f"{api_base}/health", timeout=10)
            response.raise_for_status()
            health = response.json()
            st.success(f"API running · latest data {health.get('last_observation_date', 'unknown')}")
            st.json({k: health.get(k) for k in ("model_loaded", "last_observation_date", "data_staleness_days", "ingestion")})
        except Exception as exc:
            st.error(f"Could not reach API: {exc}")
    st.divider()
    st.caption("P50 is the median forecast. P10–P90 is a nominal 80% prediction interval, not a calibrated confidence score.")


@st.cache_data(ttl=300, show_spinner=False)
def api_get(url: str, params: tuple[tuple[str, Any], ...]) -> dict:
    response = requests.get(url, params=dict(params), timeout=1800)
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text[:1000]}
    if not response.ok:
        raise RuntimeError(body.get("detail", f"API HTTP {response.status_code}"))
    return body


def fetch_graph(endpoint: str, params: dict[str, Any]) -> dict:
    return api_get(f"{api_base}{endpoint}", tuple(sorted(params.items())))


def set_freshness(payload: dict) -> None:
    last_date = payload.get("last_observation_date")
    if last_date:
        st.caption(
            f"Latest actual data: {last_date}  ·  Forecast: "
            f"{payload.get('forecast_start_date')} → {payload.get('forecast_end_date')}  ·  "
            f"Model context rows: {payload.get('model_history_rows', 'full stored history')}"
        )
    for warning in payload.get("warnings", []):
        st.warning(warning)


def section_heading(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div><div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def horizon_control(key: str, label: str = "Forecast") -> int:
    return st.radio(
        label,
        options=HORIZONS,
        index=0,
        format_func=lambda n: f"{HORIZON_LABELS[n]} · {n}d",
        horizontal=True,
        key=key,
    )


def add_forecast_band(fig: go.Figure, x, lower, upper, color: str, name: str, legendgroup: str) -> None:
    import re
    m = re.match(r"#([0-9a-fA-F]{6})", color)
    if m:
        value = m.group(1)
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        fill = f"rgba({r},{g},{b},0.14)"
    else:
        fill = "rgba(68,105,168,0.14)"
    fig.add_trace(go.Scatter(
        x=x, y=upper, mode="lines", line={"width": 0, "color": color},
        showlegend=False, hoverinfo="skip", legendgroup=legendgroup,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=lower, mode="lines", line={"width": 0, "color": color},
        fill="tonexty", fillcolor=fill, name=name, legendgroup=legendgroup,
        hovertemplate="Date: %{x}<br>Lower bound: ₹%{y:.2f}/kg<extra></extra>",
    ))


def configure_chart(fig: go.Figure, y_title: str = "Price (₹/kg)", height: int = 420) -> None:
    fig.update_layout(
        height=height, margin={"l": 12, "r": 18, "t": 18, "b": 15},
        paper_bgcolor="white", plot_bgcolor="white", hovermode="x unified",
        xaxis_title="", yaxis_title=y_title,
        font={"family": "Inter, Arial, sans-serif", "color": "#394252"},
        xaxis={"gridcolor": "#f0f2f5", "linecolor": "#e6eaf0", "zeroline": False},
        yaxis={"gridcolor": "#e7ebf1", "linecolor": "#e6eaf0", "zeroline": False},
        legend={"orientation": "h", "y": -0.22, "x": 0},
    )


# Header and summary card
st.markdown('<div class="app-kicker">AP Civil Supplies · AI price outlook · Andhra Pradesh</div>', unsafe_allow_html=True)
st.markdown('''<div class="hero">
  <div class="app-kicker">Vegetable · Onion</div>
  <div class="hero-title">Onion price outlook</div>
  <div class="hero-sub">Chronos-2 forecasting · Retail, wholesale and mandi modal prices · State comparison · Supply-demand outlook</div>
</div>''', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Graph 1 — AP price outlook. Forecast is calculated from all stored rows;
# API only returns 90 days of actuals for the chart.
# ---------------------------------------------------------------------------
section_heading("AP retail price forecast", "Andhra Pradesh onion prices · Last 3 months of actuals and the selected forecast horizon")
c1, c2 = st.columns([1.35, 1.2])
with c1:
    horizon1 = horizon_control("g1_horizon", "Forecast horizon")
with c2:
    opt1, opt2, opt3 = st.columns(3)
    with opt1:
        show_retail = st.checkbox("Retail price", value=True, key="g1_retail")
    with opt2:
        show_wholesale = st.checkbox("Wholesale price", value=False, key="g1_wholesale")
    with opt3:
        show_mandi = st.checkbox("Mandi modal price", value=False, key="g1_mandi")
run1 = st.button("Update AP forecast", type="primary", key="g1_run")
if run1:
    st.session_state["g1_started"] = True
if run1 or st.session_state.get("g1_started", False):
    selected_price_types = []
    if show_retail:
        selected_price_types.append("retail")
    if show_wholesale:
        selected_price_types.append("wholesale")
    if show_mandi:
        selected_price_types.append("mandi_modal")
    if not selected_price_types:
        st.session_state["g1_error"] = "Select retail, wholesale, and/or mandi modal price."
        st.session_state.pop("g1_payload", None)
    else:
        with st.spinner("Running Chronos-2 on the full available historical context..."):
            try:
                st.session_state["g1_payload"] = fetch_graph(
                    "/api/graphs/ap-retail",
                    {"horizon_days": horizon1, "price_types": ",".join(selected_price_types), "history_days": 90},
                )
                st.session_state["g1_error"] = None
            except Exception as exc:
                st.session_state["g1_error"] = str(exc)
if st.session_state.get("g1_error"):
    st.error(st.session_state["g1_error"])
payload1 = st.session_state.get("g1_payload")
if payload1:
    set_freshness(payload1)
    hdf = pd.DataFrame(payload1.get("historical", []))
    fdf = pd.DataFrame(payload1.get("forecast", []))
    if not hdf.empty and not fdf.empty:
        fig1 = go.Figure()
        for ptype in payload1.get("price_types", []):
            color = PRICE_COLORS.get(ptype, PRICE_COLORS["wholesale"])
            label = {"retail": "Retail price", "wholesale": "Wholesale price", "mandi_modal": "Mandi modal price"}.get(ptype, ptype)
            hist = hdf[hdf["price_type"] == ptype]
            pred = fdf[fdf["price_type"] == ptype]
            if not hist.empty:
                fig1.add_trace(go.Scatter(
                    x=hist["date"], y=hist["actual_price_rs_kg"], mode="lines",
                    name=f"{label} · actual", line={"color": color, "width": 2.3},
                    legendgroup=ptype,
                ))
            if not pred.empty:
                add_forecast_band(fig1, pred["date"], pred["p10_rs_kg"], pred["p90_rs_kg"], color, f"{label} · P10–P90", ptype)
                fig1.add_trace(go.Scatter(
                    x=pred["date"], y=pred["predicted_price_rs_kg"], mode="lines",
                    name=f"{label} · forecast P50", line={"color": color, "width": 2.7, "dash": "dash"},
                    legendgroup=ptype, hovertemplate="Date: %{x}<br>P50: ₹%{y:.2f}/kg<extra></extra>",
                ))
        # Mark the boundary between latest actual and future forecast.
        fig1.add_vline(x=payload1.get("forecast_start_date"), line_dash="dot", line_color="#8d96a5", opacity=.7)
        configure_chart(fig1, height=420)
        st.plotly_chart(fig1, use_container_width=True)

        # Compact summary values, based only on the selected series.
        metrics = []
        for ptype in payload1.get("price_types", []):
            hist = hdf[hdf["price_type"] == ptype]
            pred = fdf[fdf["price_type"] == ptype]
            if not hist.empty and not pred.empty:
                label = {"retail": "AP retail", "wholesale": "AP wholesale", "mandi_modal": "AP mandi modal"}.get(ptype, ptype)
                metrics.append((label, hist.iloc[-1]["actual_price_rs_kg"], pred.iloc[0]["predicted_price_rs_kg"], pred.iloc[0]["p10_rs_kg"], pred.iloc[0]["p90_rs_kg"]))
        if metrics:
            cols = st.columns(len(metrics))
            for col, metric in zip(cols, metrics):
                label, actual, p50, p10, p90 = metric
                col.metric(f"{label} · latest actual", f"₹{actual:.2f}/kg")
                col.caption(f"First forecast P50 ₹{p50:.2f}/kg · P10 ₹{p10:.2f} · P90 ₹{p90:.2f}")
        with st.expander("Forecast rows / API values"):
            st.dataframe(fdf, use_container_width=True, hide_index=True)
        st.download_button("Download AP price forecast CSV", fdf.to_csv(index=False), file_name=f"ap_price_forecast_{payload1['horizon_days']}d.csv", mime="text/csv", key="g1_download")
else:
    st.info("Choose any combination of retail, wholesale and mandi modal prices, select a horizon, then click Update AP forecast.")

st.markdown('<hr class="section-rule"/>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Graph 2 — selected states only, with retail and wholesale/mandi prices.
# ---------------------------------------------------------------------------
section_heading("AP vs other states", "Compare only the states you select · Retail, wholesale and mandi modal prices")
g2a, g2b = st.columns([1.5, 1.25])
with g2a:
    selected_states = st.multiselect(
        "States to compare", options=list(STATE_LABELS), default=["AP", "KA", "MH", "MP"],
        format_func=lambda code: STATE_LABELS[code], key="g2_states",
    )
with g2b:
    selected_price_types2 = st.multiselect("Price types", ["retail", "wholesale", "mandi_modal"], default=["retail", "wholesale", "mandi_modal"], format_func=lambda x: {"retail": "Retail price", "wholesale": "Wholesale price", "mandi_modal": "Mandi modal price"}[x], key="g2_types")
horizon2 = horizon_control("g2_horizon", "Comparison horizon")
run2 = st.button("Update state comparison", type="primary", key="g2_run")
if run2:
    st.session_state["g2_started"] = True
if run2 or st.session_state.get("g2_started", False):
    if not selected_states or not selected_price_types2:
        st.session_state["g2_error"] = "Select at least one state and one price type."
        st.session_state.pop("g2_payload", None)
    else:
        with st.spinner("Forecasting selected state and price series..."):
            try:
                st.session_state["g2_payload"] = fetch_graph(
                    "/api/graphs/state-comparison",
                    {"states": ",".join(selected_states), "price_types": ",".join(selected_price_types2), "horizon_days": horizon2, "history_days": 90},
                )
                st.session_state["g2_error"] = None
            except Exception as exc:
                st.session_state["g2_error"] = str(exc)
if st.session_state.get("g2_error"):
    st.error(st.session_state["g2_error"])
payload2 = st.session_state.get("g2_payload")
if payload2:
    set_freshness(payload2)
    hdf2 = pd.DataFrame(payload2.get("historical", []))
    fdf2 = pd.DataFrame(payload2.get("forecast", []))
    fig2 = go.Figure()
    for state in payload2.get("selected_states", []):
        color = STATE_COLORS.get(state, qualitative.Plotly[0])
        for ptype in payload2.get("selected_price_types", []):
            label = f"{STATE_LABELS.get(state, state)} · {dict(retail='Retail', wholesale='Wholesale', mandi_modal='Mandi modal')[ptype]}"
            hist = hdf2[(hdf2["state"] == state) & (hdf2["price_type"] == ptype)] if not hdf2.empty else pd.DataFrame()
            pred = fdf2[(fdf2["state"] == state) & (fdf2["price_type"] == ptype)] if not fdf2.empty else pd.DataFrame()
            dash = {"retail": "solid", "wholesale": "dashdot", "mandi_modal": "dot"}[ptype]
            if not hist.empty:
                fig2.add_trace(go.Scatter(x=hist["date"], y=hist["actual_price_rs_kg"], mode="lines", name=f"{label} · actual", line={"color": color, "width": 2, "dash": dash}, legendgroup=f"{state}-{ptype}"))
            if not pred.empty:
                add_forecast_band(fig2, pred["date"], pred["p10_rs_kg"], pred["p90_rs_kg"], color, f"{label} · P10–P90", f"{state}-{ptype}")
                fig2.add_trace(go.Scatter(x=pred["date"], y=pred["predicted_price_rs_kg"], mode="lines", name=f"{label} · forecast P50", line={"color": color, "width": 2.4, "dash": "dash" if ptype == "retail" else "dashdot"}, legendgroup=f"{state}-{ptype}"))
    if payload2.get("forecast_start_date"):
        fig2.add_vline(x=payload2["forecast_start_date"], line_dash="dot", line_color="#8d96a5", opacity=.7)
    configure_chart(fig2, height=470)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Only selected states and price types are included in the API response. Forecasts use all stored historical rows; the chart displays the last 90 actual days.")
    if not fdf2.empty:
        with st.expander("Comparison forecast rows"):
            st.dataframe(fdf2, use_container_width=True, hide_index=True)
        st.download_button("Download comparison forecast CSV", fdf2.to_csv(index=False), file_name="selected_state_price_forecasts.csv", mime="text/csv", key="g2_download")
else:
    st.info("Select states and price types, choose a horizon and click Update state comparison.")

st.markdown('<hr class="section-rule"/>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Graph 3 — forecast supply (arrivals + production) and consumption, then derive shortfall.
# ---------------------------------------------------------------------------
section_heading("Demand, supply and shortfall", "Chronos-2 forecasts Supply = Arrivals + Production and Consumption separately; Shortfall = Supply − Consumption")
st.warning("Supply is defined per the requested logic as arrivals + production. Confirm the quantities share compatible time periods and that this does not double-count the same supply flow.")
g3a, g3b = st.columns([1.35, 1.65])
with g3a:
    qty_states = st.multiselect("States for quantity outlook", options=list(STATE_LABELS), default=["AP"], format_func=lambda code: STATE_LABELS[code], key="g3_states")
with g3b:
    st.caption("Only Supply and Consumption are forecast targets. Arrivals and Production are combined into Supply before forecasting.")
horizon3 = horizon_control("g3_horizon", "Forecast horizon")
run3 = st.button("Update supply / demand outlook", type="primary", key="g3_run")
if run3:
    st.session_state["g3_started"] = True
if run3 or st.session_state.get("g3_started", False):
    if not qty_states:
        st.session_state["g3_error"] = "Select at least one state."
        st.session_state.pop("g3_payload", None)
    else:
        with st.spinner("Forecasting Supply and Consumption with Chronos-2..."):
            try:
                st.session_state["g3_payload"] = fetch_graph(
                    "/api/graphs/supply-balance",
                    {"states": ",".join(qty_states), "horizon_days": horizon3, "history_days": 90},
                )
                st.session_state["g3_error"] = None
            except Exception as exc:
                st.session_state["g3_error"] = str(exc)
if st.session_state.get("g3_error"):
    st.error(st.session_state["g3_error"])
payload3 = st.session_state.get("g3_payload")
if payload3:
    set_freshness(payload3)
    qhist = pd.DataFrame(payload3.get("historical", []))
    qpred = pd.DataFrame(payload3.get("quantity_forecast", []))
    bpred = pd.DataFrame(payload3.get("balance_forecast", []))
    if not qhist.empty and not qpred.empty:
        fig3 = go.Figure()
        for state in payload3.get("selected_states", []):
            color = STATE_COLORS.get(state, "#4469a8")
            hist_state = qhist[qhist["state"] == state]
            pred_state = qpred[qpred["state"] == state]
            for metric, label, dash in [("supply", "Supply", "solid"), ("consumption", "Consumption", "dot")]:
                h = hist_state[hist_state["metric"] == metric]
                f = pred_state[pred_state["metric"] == metric]
                if not h.empty:
                    fig3.add_trace(go.Scatter(x=h["date"], y=h["actual_quantity_mq_day"], mode="lines",
                        name=f"{state} {label} · actual", line={"color": color, "width": 2 if metric == "supply" else 1.8, "dash": dash}, legendgroup=f"{state}-{metric}"))
                if not f.empty:
                    fig3.add_trace(go.Scatter(x=f["date"], y=f["predicted_quantity_mq_day"], mode="lines",
                        name=f"{state} {label} · forecast P50", line={"color": color, "width": 2.5, "dash": "dash" if metric == "supply" else "dashdot"}, legendgroup=f"{state}-{metric}"))
        if payload3.get("forecast_start_date"):
            fig3.add_vline(x=payload3["forecast_start_date"], line_dash="dot", line_color="#8d96a5", opacity=.75)
        configure_chart(fig3, y_title="Metric quintals per day", height=470)
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Shortfall = Supply − Consumption. Negative values mean potential shortfall; positive values mean potential surplus. Values are provisional until the quantity definitions and periods are confirmed.")
    if not bpred.empty:
        latest = bpred[bpred["date"] == bpred["date"].max()]
        cards = st.columns(max(1, len(latest)))
        for col, (_, row) in zip(cards, latest.iterrows()):
            val = float(row["shortfall_p50_metric_quintal_day"])
            col.metric("Indicative shortfall / surplus · " + row["state"], f"{val:,.1f} mq/day", delta="Potential shortfall" if val < 0 else "Potential surplus", delta_color="inverse" if val < 0 else "normal")
        with st.expander("Supply, consumption and shortfall forecast rows"):
            st.dataframe(qpred, use_container_width=True, hide_index=True)
            st.dataframe(bpred, use_container_width=True, hide_index=True)
            for warning in payload3.get("warnings", []):
                st.write(f"- {warning}")
    if not qpred.empty:
        st.download_button("Download supply / consumption forecast CSV", qpred.to_csv(index=False), file_name="supply_consumption_forecasts.csv", mime="text/csv", key="g3_download")
else:
    st.info("Select states, choose a horizon and click Update supply / demand outlook.")
st.markdown('<hr class="section-rule"/>', unsafe_allow_html=True)
st.caption("Visual QA dashboard. The production frontend should call the same FastAPI endpoints. Weather / El Niño / cyclone scenarios are intentionally not included yet.")
