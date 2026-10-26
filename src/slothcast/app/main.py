"""Slothcast dashboard.  Run:  streamlit run src/slothcast/app/main.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # make `slothcast` importable without install

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from slothcast import config  # noqa: E402
from slothcast.demo_data import write_demo  # noqa: E402
from slothcast.ingest.checkin import append_checkin, set_outcome  # noqa: E402
from slothcast.models.tabpfn_model import tabpfn_status  # noqa: E402
from slothcast.pipeline import forecast_tomorrow, load_dataset, run_eval  # noqa: E402

st.set_page_config(page_title="Slothcast", page_icon="🦥", layout="centered")

# ---------------- sidebar: where the data lives ----------------
st.sidebar.header("Data")
path_text = st.sidebar.text_input("Check-in file", str(config.CHECKINS_PATH))
use_demo = st.sidebar.checkbox("Use synthetic demo data", value=not Path(path_text).exists())
if use_demo:
    data_path = Path(config.SAMPLE_CHECKINS_PATH)
    if not data_path.exists():
        write_demo(data_path)
else:
    data_path = Path(path_text)
st.sidebar.header("Models")
model_choice = st.sidebar.selectbox("Forecast model", ["auto", "tabpfn", "logistic", "random_forest"])
use_llm = st.sidebar.checkbox("Plan with local Gemma (Ollama)", value=True)
ok, why = tabpfn_status()
st.sidebar.caption(f"TabPFN: {why}" if ok else f"TabPFN not available. {why}")

ds = load_dataset(data_path, config.COMMITS_PATH)
suff = ds.sufficiency

st.title("Slothcast")
st.write("Deadline risk for tomorrow's planned work. The model forecasts; you decide what to do with it.")
if suff.n_synthetic:
    st.warning("This is synthetic demo data. Nothing here describes a real person.")

tab_forecast, tab_log, tab_history, tab_eval = st.tabs(["Tomorrow", "Check in", "History", "Evaluation"])

# ---------------- tomorrow ----------------
with tab_forecast:
    with st.form("plan_form"):
        task = st.text_input("Planned task", "DSA block")
        c1, c2, c3 = st.columns(3)
        minutes = c1.number_input("Planned minutes", 10, 600, 120, 10)
        dtd = c2.number_input("Days to deadline", 0, 60, 3)
        energy = c3.slider("Energy (1 low, 5 high)", 1, 5, 3)
        go = st.form_submit_button("Get forecast")
    if go:
        with st.spinner("Forecasting"):
            st.session_state["forecast"] = forecast_tomorrow(
                task, minutes, dtd, energy, checkins_path=data_path, commits_path=config.COMMITS_PATH,
                use_llm=use_llm, model=model_choice,
            )
    fc = st.session_state.get("forecast")
    if fc is None:
        st.info(f"{suff.message} Fill in the plan above to see a forecast.")
    else:
        if fc.risk is None:
            st.info(f"{fc.label}. {fc.sufficiency.message}")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Deadline risk", fc.label)
            m2.metric("Slip probability", f"{round(fc.risk * 100)}%")
            m3.metric("Model", fc.model_used or "none")
            if fc.sufficiency.level == "preliminary":
                st.caption(fc.sufficiency.message)
        if fc.model_note and fc.risk is not None:
            st.caption(fc.model_note)
        st.subheader("Plan")
        st.markdown(f"**Start with ({fc.plan.first_step_minutes} min):** {fc.plan.first_step}")
        st.markdown(f"**If it slips ({fc.plan.fallback_minutes} min):** {fc.plan.fallback}")
        st.write(fc.plan.note)
        st.caption(f"Plan written by: {fc.plan.source}" + (f". {fc.plan.guardrail_note}" if fc.plan.guardrail_note else ""))

# ---------------- check in ----------------
with tab_log:
    if use_demo:
        st.info("Turn off synthetic demo data in the sidebar to log real days.")
    else:
        st.subheader("Log a plan")
        with st.form("log_form"):
            d = st.date_input("Date", pd.Timestamp.today())
            t = st.text_input("Task", "DSA block", key="log_task")
            a, b, c = st.columns(3)
            mins = a.number_input("Planned minutes", 10, 600, 120, 10, key="log_min")
            dl = b.number_input("Days to deadline", 0, 60, 3, key="log_dl")
            en = c.slider("Energy", 1, 5, 3, key="log_en")
            if st.form_submit_button("Save plan"):
                append_checkin(data_path, date=d, planned_task=t, planned_minutes=mins, days_to_deadline=dl, energy=en)
                st.success(f"Saved plan for {d}.")
        st.subheader("Record an outcome")
        with st.form("outcome_form"):
            d2 = st.date_input("Date", pd.Timestamp.today(), key="out_date")
            done = st.radio("Did the planned work happen?", ["Yes", "No"], horizontal=True)
            if st.form_submit_button("Save outcome"):
                try:
                    set_outcome(data_path, d2, 1 if done == "Yes" else 0)
                    st.success(f"Saved outcome for {d2}.")
                except KeyError as exc:
                    st.error(str(exc).strip("'"))

# ---------------- history ----------------
with tab_history:
    if ds.labeled.empty:
        st.info("No labelled days yet.")
    else:
        st.caption(suff.message)
        rate = ds.labeled.set_index("date")["y_slip"].rolling(7, min_periods=3).mean().rename("7-day slip rate")
        st.line_chart(rate)
        st.dataframe(ds.labeled.tail(30).sort_values("date", ascending=False), use_container_width=True, hide_index=True)

# ---------------- evaluation ----------------
with tab_eval:
    results_md = Path(config.RESULTS_DIR) / "results.md"
    if st.button("Run evaluation"):
        with st.spinner("Running chronological evaluation"):
            res = run_eval(data_path, config.COMMITS_PATH, use_tabpfn=model_choice in ("auto", "tabpfn"))
        if "error" in res:
            st.error(res["error"])
    if results_md.exists():
        st.markdown(results_md.read_text().split("![calibration]")[0])
        for img in ("calibration.png", "learning_curve.png"):
            p = Path(config.RESULTS_DIR) / img
            if p.exists():
                st.image(str(p))
    else:
        st.info("No results yet. Run the evaluation to compare models on your own history.")
