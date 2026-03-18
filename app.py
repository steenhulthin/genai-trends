from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from genai_trends.config import load_project_context, load_tracked_items
from genai_trends.data import build_topic_summary, generate_dataset
from genai_trends.logging_utils import get_logger


APP_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;500;700&display=swap');

:root {
    --bg-top: #f6fff4;
    --bg-bottom: #edf4ff;
    --panel: rgba(255, 255, 255, 0.88);
    --panel-strong: rgba(255, 255, 255, 0.96);
    --text: #143042;
    --muted: #4d6677;
    --accent: #0f9d7a;
    --accent-2: #ff9f1c;
    --accent-3: #5b7cfa;
    --border: rgba(20, 48, 66, 0.12);
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(255, 159, 28, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(91, 124, 250, 0.18), transparent 30%),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
    color: var(--text);
}

h1, h2, h3 {
    font-family: "Space Grotesk", "Segoe UI", sans-serif;
    color: var(--text);
    letter-spacing: -0.02em;
}

p, li, [data-testid="stMarkdownContainer"] {
    font-family: "Space Grotesk", "Segoe UI", sans-serif;
}

code, .mono {
    font-family: "JetBrains Mono", "Consolas", monospace;
}

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:has(.panel-hook) {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 22px;
    box-shadow: 0 20px 45px rgba(44, 62, 80, 0.08);
}

.hero-panel {
    padding: 1.35rem 1.4rem 1rem 1.4rem;
    background: linear-gradient(140deg, rgba(15, 157, 122, 0.12), rgba(91, 124, 250, 0.12));
    border: 1px solid var(--border);
    border-radius: 24px;
    margin-bottom: 0.5rem;
}

.eyebrow {
    display: inline-block;
    padding: 0.25rem 0.55rem;
    border-radius: 999px;
    background: rgba(20, 48, 66, 0.07);
    color: var(--muted);
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.hero-title {
    margin: 0.75rem 0 0.35rem 0;
    font-size: 2.35rem;
    line-height: 1.05;
}

.hero-copy {
    color: var(--muted);
    font-size: 1rem;
    margin-bottom: 1rem;
}

.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.8rem 0 0.2rem 0;
}

.chip {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(20, 48, 66, 0.12);
    color: var(--text);
    font-size: 0.92rem;
}

.section-note {
    color: var(--muted);
    margin-bottom: 0.65rem;
}

.item-title {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 0.15rem;
}

.item-subtitle {
    color: var(--muted);
    font-size: 0.92rem;
    margin-bottom: 0.7rem;
}

.note-panel {
    padding: 1rem 1.1rem;
    background: var(--panel-strong);
    border: 1px solid var(--border);
    border-radius: 20px;
}
</style>
"""

st.set_page_config(
    page_title="Claude vs ChatGPT Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)

LOGGER = get_logger("genai_trends")


@st.cache_data(show_spinner=False)
def get_context() -> dict:
    return load_project_context()


@st.cache_data(show_spinner=False)
def get_tracked_items() -> dict:
    return load_tracked_items()


@st.cache_data(show_spinner=False)
def get_dataset(period_start: date, period_end: date) -> tuple[pd.DataFrame, dict]:
    return generate_dataset(
        context=get_context(),
        tracked_items=get_tracked_items(),
        period_start=period_start,
        period_end=period_end,
        granularity="daily",
    )


def topic_key_for_name(topic_name: str) -> str:
    return topic_name.replace(" ", "_")


def format_metric_value(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.0f}"


def numeric_metric(value: float | int | None) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def movement_copy(topic_frame: pd.DataFrame) -> str:
    ordered = topic_frame.sort_values("period_end")
    if len(ordered) < 2:
        return "Fresh in the current window."

    latest = numeric_metric(ordered.iloc[-1]["news_mentions_frequency"])
    previous = numeric_metric(ordered.iloc[-2]["news_mentions_frequency"])
    delta = latest - previous
    if delta > 0:
        return f"Up {delta:.0f} Guardian mentions vs the previous bucket."
    if delta < 0:
        return f"Down {abs(delta):.0f} Guardian mentions vs the previous bucket."
    return "Holding steady across the latest buckets."


def tracked_topic_chip_markup(topic_names: list[str]) -> str:
    return "".join(f'<span class="chip mono">{topic_name}</span>' for topic_name in topic_names)


def render_topic_detail_card(topic_frame: pd.DataFrame, latest_row: pd.Series) -> None:
    with st.container(border=True):
        st.markdown('<div class="panel-hook"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="item-title">{latest_row["topic"]}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="item-subtitle">Guardian-only topic view. {movement_copy(topic_frame)}</div>',
            unsafe_allow_html=True,
        )

        metric_columns = st.columns(3)
        metric_columns[0].metric("Guardian mentions", format_metric_value(latest_row["news_mentions_frequency"]))
        metric_columns[1].metric("Latest bucket", latest_row["period_end"])
        metric_columns[2].metric("Partial data", "Yes" if bool(latest_row["partial_data_warning"]) else "No")

        history_chart = topic_frame.sort_values("period_end")[["period_end", "news_mentions_frequency"]].copy()
        history_chart["period_end"] = pd.to_datetime(history_chart["period_end"])
        history_chart = history_chart.set_index("period_end")
        st.line_chart(history_chart, height=220, width="stretch")


st.markdown(APP_STYLES, unsafe_allow_html=True)

context = get_context()
tracked_items = get_tracked_items()

today = date.today()

with st.sidebar:
    st.header("Controls")
    topic_options = context["topics"]["initial"]
    selected_topic = st.selectbox("Topic", topic_options, index=0)
    window_days = st.slider(
        "Time window (days)",
        min_value=30,
        max_value=int(context["time"].get("max_fetch_window_days", 365)),
        value=int(context["time"]["fetch_window_days"]),
        step=1,
    )
    st.caption("Use the slider to compare the latest window. The default is roughly half a year.")
    default_start = today - timedelta(days=window_days - 1)
    period_start = default_start
    period_end = today
    st.date_input(
        "Current fetch window",
        value=(period_start, period_end),
        disabled=True,
    )

data, load_status = get_dataset(
    period_start=period_start,
    period_end=period_end,
)

LOGGER.info(
    "dashboard_rendered",
    extra={
        "event": "dashboard_rendered",
        "topic": selected_topic,
        "granularity": "daily",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "rows": int(data.shape[0]),
    },
)

filtered = data[data["topic"] == selected_topic].copy()
topic_summary = build_topic_summary(data)
topic_items = tracked_items["topics"][topic_key_for_name(selected_topic)]["items"]

partial_data_rows = filtered[filtered["partial_data_warning"]]
if not partial_data_rows.empty:
    st.warning(
        "Some Guardian data is unavailable for part of the selected result set. "
        "The dashboard is keeping the remaining history visible."
    )

if int(load_status["throttled_calls"]) > 0:
    LOGGER.error(
        "dashboard_throttled_warning",
        extra={"event": "dashboard_throttled_warning", "throttled_calls": int(load_status["throttled_calls"])},
    )
    st.error(
        f"Detected {int(load_status['throttled_calls'])} throttled Guardian API calls in the current load. "
        "Detailed fetch diagnostics have been written to the log files."
    )
elif int(load_status["error_calls"]) > 0:
    LOGGER.warning(
        "dashboard_partial_warning",
        extra={
            "event": "dashboard_partial_warning",
            "error_calls": int(load_status["error_calls"]),
            "partial_rows": int(load_status["partial_rows"]),
        },
    )

latest_topic_snapshot = (
    topic_summary.sort_values("period_end")
    .groupby("topic", as_index=False)
    .tail(1)
    .sort_values("news_mentions_frequency", ascending=False)
)

selected_latest_row = filtered.sort_values("period_end").tail(1)
selected_latest_mentions = numeric_metric(
    selected_latest_row.iloc[0]["news_mentions_frequency"] if not selected_latest_row.empty else 0.0
)
top_topic_name = latest_topic_snapshot.iloc[0]["topic"] if not latest_topic_snapshot.empty else "n/a"
top_topic_score = (
    float(latest_topic_snapshot.iloc[0]["news_mentions_frequency"]) if not latest_topic_snapshot.empty else 0.0
)

st.markdown(
    f"""
    <div class="hero-panel">
        <span class="eyebrow">guardian trend explorer</span>
        <div class="hero-title">Claude versus ChatGPT</div>
        <div class="hero-copy">
            Compare how Claude and ChatGPT are showing up in Guardian coverage while keeping Anthropic and OpenAI
            in the same frame. Use the topic selector and time-window slider to change the lens without changing
            the daily resolution.
        </div>
        <div class="chip-row">{tracked_topic_chip_markup(topic_options)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Predefined topics", f"{len(topic_options)}")
metric_columns[1].metric("Guardian mentions", format_metric_value(selected_latest_mentions))
metric_columns[2].metric(
    "Window leader",
    top_topic_name,
    f"{top_topic_score:.0f}" if top_topic_name != "n/a" else None,
)
metric_columns[3].metric("Resolution", "Daily")

overview_col, ranking_col = st.columns((1.3, 1))

with overview_col:
    st.subheader("Guardian comparison")
    st.markdown(
        '<div class="section-note">Each line shows Guardian mention counts for one predefined topic across the active window.</div>',
        unsafe_allow_html=True,
    )
    topic_summary_chart = topic_summary.pivot_table(
        index="period_end",
        columns="topic",
        values="news_mentions_frequency",
        aggfunc="sum",
    ).sort_index()
    if topic_summary_chart.empty:
        st.info("No topic-level Guardian history is available for the current selection yet.")
    else:
        st.line_chart(topic_summary_chart, height=320, width="stretch")

with ranking_col:
    st.subheader("Current ranking")
    st.markdown(
        '<div class="section-note">A quick read on which of the four predefined terms is strongest in the latest bucket.</div>',
        unsafe_allow_html=True,
    )
    if latest_topic_snapshot.empty:
        st.info("No current topic ranking is available for the current selection yet.")
    else:
        latest_scores_chart = latest_topic_snapshot[["topic", "news_mentions_frequency"]].set_index("topic")
        st.bar_chart(latest_scores_chart, height=320, width="stretch")

st.subheader("Selected topic")
st.markdown(
    '<div class="section-note">The selected term keeps a simple, single-source detail view: latest Guardian count, current bucket, and recent history.</div>',
    unsafe_allow_html=True,
)

if selected_latest_row.empty:
    st.info("No Guardian detail is available for the current selection yet.")
else:
    render_topic_detail_card(filtered, selected_latest_row.iloc[0])

with st.expander("Tracked terms"):
    for topic_name in context["topics"]["initial"]:
        items = tracked_items["topics"][topic_key_for_name(topic_name)]["items"]
        st.markdown(f"**{topic_name}**")
        st.markdown(", ".join(f"`{item}`" for item in items))
