from __future__ import annotations

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from genai_trends.config import load_project_context, load_tracked_items
from genai_trends.data import generate_dataset, prefetch_snapshot_version
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
</style>
"""

st.set_page_config(
    page_title="Claude vs ChatGPT Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)

LOGGER = get_logger("genai_trends")
GROUP_COLORS = {
    "Claude + Anthropic": "#83C9FF",
    "ChatGPT + OpenAI": "#FF8C42",
}


@st.cache_data(show_spinner=False)
def get_context() -> dict:
    return load_project_context()


@st.cache_data(show_spinner=False)
def get_tracked_items() -> dict:
    return load_tracked_items()


@st.cache_data(show_spinner=False)
def get_dataset(period_start: date, period_end: date, snapshot_version: str) -> tuple[pd.DataFrame, dict]:
    return generate_dataset(
        context=get_context(),
        tracked_items=get_tracked_items(),
        period_start=period_start,
        period_end=period_end,
        granularity="weekly",
    )


def format_metric_value(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.0f}"


def numeric_metric(value: float | int | None) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def movement_copy(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values("period_end")
    if len(ordered) < 2:
        return "Fresh in the current window."

    latest = numeric_metric(ordered.iloc[-1]["news_mentions_frequency"])
    previous = numeric_metric(ordered.iloc[-2]["news_mentions_frequency"])
    delta = latest - previous
    if delta > 0:
        return f"Up {delta:.0f} weekly mentions vs the previous bucket."
    if delta < 0:
        return f"Down {abs(delta):.0f} weekly mentions vs the previous bucket."
    return "Holding steady across the latest buckets."


def tracked_topic_chip_markup(topic_names: list[str]) -> str:
    return "".join(f'<span class="chip mono">{topic_name}</span>' for topic_name in topic_names)


def week_label(week_start: date) -> str:
    iso_year, iso_week, _ = week_start.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def available_calendar_weeks(start_year: int, start_week: int, end_date: date) -> list[date]:
    week_starts: list[date] = []
    current = date.fromisocalendar(start_year, start_week, 1)
    end_week_start = end_date - timedelta(days=end_date.weekday())
    while current <= end_week_start:
        week_starts.append(current)
        current += timedelta(days=7)
    return week_starts


def build_comparison_summary(frame: pd.DataFrame, comparison_groups: list[dict[str, object]]) -> pd.DataFrame:
    group_lookup: dict[str, str] = {}
    for group in comparison_groups:
        label = str(group["label"])
        for topic in group["topics"]:
            group_lookup[str(topic)] = label

    working = frame.copy()
    working["comparison_group"] = working["topic"].map(group_lookup)
    working = working.dropna(subset=["comparison_group"])

    summary = (
        working.groupby(["period_end", "comparison_group"], as_index=False)["news_mentions_frequency"]
        .sum()
        .sort_values("period_end")
    )
    return summary


def render_group_card(group_frame: pd.DataFrame, label: str) -> None:
    latest_row = group_frame.sort_values("period_end").tail(1).iloc[0]
    with st.container(border=True):
        st.markdown('<div class="panel-hook"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="item-title">{label}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="item-subtitle">Weekly merged view. {movement_copy(group_frame)}</div>',
            unsafe_allow_html=True,
        )

        metric_columns = st.columns(2)
        metric_columns[0].metric("Weekly mentions", format_metric_value(latest_row["news_mentions_frequency"]))
        metric_columns[1].metric("Week bucket", latest_row["period_end"])

        history_chart = group_frame.sort_values("period_end")[["period_end", "news_mentions_frequency"]].copy()
        history_chart["period_end"] = pd.to_datetime(history_chart["period_end"])
        history_chart["group_label"] = label
        st.altair_chart(
            alt.Chart(history_chart)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("period_end:T", title=None),
                y=alt.Y("news_mentions_frequency:Q", title=None),
                color=alt.Color(
                    "group_label:N",
                    scale=alt.Scale(
                        domain=list(GROUP_COLORS.keys()),
                        range=list(GROUP_COLORS.values()),
                    ),
                    legend=None,
                ),
            ),
            height=240,
            use_container_width=True,
        )


st.markdown(APP_STYLES, unsafe_allow_html=True)

context = get_context()
comparison_groups = context["comparison_groups"]
tracked_items = get_tracked_items()

today = date.today()

with st.sidebar:
    st.header("Controls")
    calendar_weeks = available_calendar_weeks(
        start_year=int(context["time"]["calendar_start_year"]),
        start_week=int(context["time"]["calendar_start_week"]),
        end_date=today,
    )
    default_selected_weeks = min(int(context["time"]["default_selected_weeks"]), len(calendar_weeks))
    default_value = (calendar_weeks[-default_selected_weeks], calendar_weeks[-1])
    selected_week_range = st.select_slider(
        "Calendar weeks",
        options=calendar_weeks,
        value=default_value,
        format_func=week_label,
    )
    st.caption("The comparison runs in calendar-week buckets starting at 2022-W40. The default selection is the last 12 weeks.")
    period_start = selected_week_range[0]
    period_end = min(today, selected_week_range[1] + timedelta(days=6))

snapshot_version = prefetch_snapshot_version(context, "weekly")
data, load_status = get_dataset(
    period_start=period_start,
    period_end=period_end,
    snapshot_version=snapshot_version,
)

comparison_summary = build_comparison_summary(data, comparison_groups)
group_order = [str(group["label"]) for group in comparison_groups]

LOGGER.info(
    "dashboard_rendered",
    extra={
        "event": "dashboard_rendered",
        "granularity": "weekly",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "window_weeks": len(pd.date_range(period_start, selected_week_range[1], freq="W-MON")),
        "rows": int(data.shape[0]),
    },
)

if int(load_status.get("cache_rows_used", 0)) > 0 and bool(load_status.get("live_fetch_used")):
    st.info(
        "Using prefetched Guardian history for the older weeks in this window and a live Guardian refresh for the newest weekly bucket."
    )
elif int(load_status.get("cache_rows_used", 0)) > 0:
    st.info("Using prefetched Guardian history for the selected window.")

partial_data_rows = data[data["partial_data_warning"]]
if not partial_data_rows.empty:
    st.warning(
        "Some Guardian data is unavailable for part of the current result set. "
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

latest_group_snapshot = (
    comparison_summary.sort_values("period_end")
    .groupby("comparison_group", as_index=False)
    .tail(1)
)
latest_group_snapshot["comparison_group"] = pd.Categorical(
    latest_group_snapshot["comparison_group"],
    categories=group_order,
    ordered=True,
)
latest_group_snapshot = latest_group_snapshot.sort_values("comparison_group")

latest_values = {
    str(row["comparison_group"]): numeric_metric(row["news_mentions_frequency"])
    for _, row in latest_group_snapshot.iterrows()
}
selected_week_count = len(pd.date_range(period_start, selected_week_range[1], freq="W-MON"))

tracked_terms = [
    item
    for topic_name in context["topics"]["initial"]
    for item in tracked_items["topics"][topic_name]["items"]
]

st.markdown(
    f"""
    <div class="hero-panel">
        <span class="eyebrow">guardian trend explorer</span>
        <div class="hero-title">Claude versus ChatGPT</div>
        <div class="hero-copy">
            Weekly Guardian comparison for two merged groups: Claude with Anthropic, and ChatGPT with OpenAI.
            Use the period slider to widen or narrow the weekly comparison window.
        </div>
        <div class="chip-row">{tracked_topic_chip_markup(tracked_terms)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Tracked terms", f"{len(tracked_terms)}")
metric_columns[1].metric(group_order[0], format_metric_value(latest_values.get(group_order[0])))
metric_columns[2].metric(group_order[1], format_metric_value(latest_values.get(group_order[1])))
metric_columns[3].metric("Window", f"{selected_week_count} weeks")

st.subheader("Weekly comparison")
st.markdown(
    '<div class="section-note">Each line shows the merged weekly mention count for one side of the comparison.</div>',
    unsafe_allow_html=True,
)

comparison_chart = comparison_summary.pivot_table(
    index="period_end",
    columns="comparison_group",
    values="news_mentions_frequency",
    aggfunc="sum",
).sort_index()

if comparison_chart.empty:
    st.info("No weekly Guardian history is available for the current window yet.")
else:
    comparison_chart = comparison_chart.reset_index().melt(
        id_vars="period_end",
        var_name="comparison_group",
        value_name="news_mentions_frequency",
    )
    st.altair_chart(
        alt.Chart(comparison_chart)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("period_end:T", title=None),
            y=alt.Y("news_mentions_frequency:Q", title=None),
            color=alt.Color(
                "comparison_group:N",
                scale=alt.Scale(
                    domain=list(GROUP_COLORS.keys()),
                    range=list(GROUP_COLORS.values()),
                ),
                legend=alt.Legend(title=None),
            ),
        ),
        height=360,
        use_container_width=True,
    )

st.subheader("Weekly group readout")
st.markdown(
    '<div class="section-note">Each card shows the latest merged weekly total and recent direction for one side.</div>',
    unsafe_allow_html=True,
)

group_columns = st.columns(2)
for index, group_name in enumerate(group_order):
    group_frame = comparison_summary[comparison_summary["comparison_group"] == group_name].copy()
    with group_columns[index]:
        if group_frame.empty:
            st.info(f"No data is available yet for {group_name}.")
        else:
            render_group_card(group_frame, group_name)


