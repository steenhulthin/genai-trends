from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from genai_trends.config import load_project_context, load_tracked_items
from genai_trends.data import SOURCE_FIELD_MAP, build_export_frame, build_topic_summary, generate_dataset
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

.chip--source {
    background: rgba(91, 124, 250, 0.1);
}

.chip--warning {
    background: rgba(255, 159, 28, 0.18);
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

.signal-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
    margin: 0.55rem 0 0.3rem 0;
}

.signal-card {
    background: rgba(20, 48, 66, 0.045);
    border: 1px solid rgba(20, 48, 66, 0.08);
    border-radius: 16px;
    padding: 0.65rem 0.75rem;
}

.signal-label {
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
}

.signal-value {
    font-size: 1.15rem;
    font-weight: 700;
    margin-top: 0.18rem;
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
    page_title="genAI Trends Dashboard",
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
def get_dataset(
    period_start: date,
    period_end: date,
    granularity: str,
) -> tuple[pd.DataFrame, dict]:
    return generate_dataset(
        context=get_context(),
        tracked_items=get_tracked_items(),
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
    )


def topic_key_for_name(topic_name: str) -> str:
    return topic_name.replace(" ", "_")


def format_source_name(source_name: str) -> str:
    return source_name.replace("_", " ").title()


def hashtag_slug(term: str) -> str:
    return "".join(character.lower() for character in term if character.isalnum())


def format_metric_value(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.1f}"


def movement_copy(item_frame: pd.DataFrame) -> str:
    ordered = item_frame.sort_values("period_end")
    if len(ordered) < 2:
        return "Fresh in the current window."

    latest = float(ordered.iloc[-1]["composite_score"])
    previous = float(ordered.iloc[-2]["composite_score"])
    delta = round(latest - previous, 1)
    if delta > 0:
        return f"Up {delta:.1f} vs the previous bucket."
    if delta < 0:
        return f"Down {abs(delta):.1f} vs the previous bucket."
    return "Holding steady across the latest buckets."


def source_signal_markup(row: pd.Series, selected_sources: dict[str, str]) -> str:
    cards: list[str] = []
    for source_key in ("social_media", "news_mentions", "google_trends"):
        field_name = SOURCE_FIELD_MAP[source_key]
        cards.append(
            f"""
            <div class="signal-card">
                <div class="signal-label">{format_source_name(selected_sources[source_key])}</div>
                <div class="signal-value">{format_metric_value(row.get(f"{field_name}_frequency"))}</div>
            </div>
            """
        )
    return f'<div class="signal-grid">{"".join(cards)}</div>'


def tracked_item_chip_markup(topic_items: list[str]) -> str:
    return "".join(f'<span class="chip mono">{item}</span>' for item in topic_items)


def available_source_chip_markup(value: str) -> str:
    labels = [label.strip() for label in value.split(",") if label.strip()]
    if not labels:
        return '<span class="chip chip--warning">Waiting for source data</span>'
    return "".join(f'<span class="chip chip--source">{format_source_name(label)}</span>' for label in labels)


def source_summary_markup(source_name: str, total_value: float, leader: str, leader_value: float) -> str:
    return f"""
    <div class="panel-hook"></div>
    <div class="item-title">{format_source_name(source_name)}</div>
    <div class="item-subtitle">Current signal across the selected topic.</div>
    <div class="signal-grid">
        <div class="signal-card">
            <div class="signal-label">Topic Total</div>
            <div class="signal-value">{total_value:.1f}</div>
        </div>
        <div class="signal-card">
            <div class="signal-label">Leading Item</div>
            <div class="signal-value mono">{leader}</div>
        </div>
        <div class="signal-card">
            <div class="signal-label">Leader Signal</div>
            <div class="signal-value">{leader_value:.1f}</div>
        </div>
    </div>
    """


def render_item_card(
    item_name: str,
    item_frame: pd.DataFrame,
    latest_row: pd.Series,
    selected_sources: dict[str, str],
) -> None:
    with st.container(border=True):
        st.markdown('<div class="panel-hook"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="item-title">{item_name}</div>', unsafe_allow_html=True)
        st.markdown(
            (
                f'<div class="item-subtitle mono">#{hashtag_slug(item_name)}'
                f" | {movement_copy(item_frame)}</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(available_source_chip_markup(str(latest_row.get("available_sources", ""))), unsafe_allow_html=True)

        metric_columns = st.columns(3)
        metric_columns[0].metric("Composite", f"{float(latest_row['composite_score']):.1f}")
        metric_columns[1].metric("Latest bucket", latest_row["period_end"])
        metric_columns[2].metric("Partial data", "Yes" if bool(latest_row["partial_data_warning"]) else "No")

        st.markdown(source_signal_markup(latest_row, selected_sources), unsafe_allow_html=True)

        history_chart = item_frame.sort_values("period_end")[["period_end", "composite_score"]].copy()
        history_chart["period_end"] = pd.to_datetime(history_chart["period_end"])
        history_chart = history_chart.set_index("period_end")
        st.line_chart(history_chart, height=190, width="stretch")


st.markdown(APP_STYLES, unsafe_allow_html=True)

context = get_context()
tracked_items = get_tracked_items()

today = date.today()
default_start = today - timedelta(days=6)

with st.sidebar:
    st.header("Controls")
    topic_options = context["topics"]["initial"]
    selected_topic = st.selectbox("Topic", topic_options, index=0)
    granularity_options = context["time"]["granularity"]["allowed"]
    default_granularity = context["time"]["granularity"]["default"]
    selected_granularity = st.selectbox(
        "Granularity",
        granularity_options,
        index=granularity_options.index(default_granularity),
    )
    st.caption("The live fetch window is fixed to the latest 7 days while the collectors are being stabilized.")
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
    granularity=selected_granularity,
)

LOGGER.info(
    "dashboard_rendered",
    extra={
        "event": "dashboard_rendered",
        "topic": selected_topic,
        "granularity": selected_granularity,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "rows": int(data.shape[0]),
    },
)

filtered = data[data["topic"] == selected_topic].copy()
topic_summary = build_topic_summary(data)
export_frame = build_export_frame(filtered)
selected_sources = context["data_sources"]["selected"]
topic_items = tracked_items["topics"][topic_key_for_name(selected_topic)]["items"]

partial_data_rows = filtered[filtered["partial_data_warning"]]
if not partial_data_rows.empty:
    st.warning(
        "Some source data is unavailable for part of the selected result set. "
        "The dashboard is keeping the remaining signals visible."
    )

if int(load_status["throttled_calls"]) > 0:
    LOGGER.error(
        "dashboard_throttled_warning",
        extra={"event": "dashboard_throttled_warning", "throttled_calls": int(load_status["throttled_calls"])},
    )
    st.error(
        f"Detected {int(load_status['throttled_calls'])} throttled API calls in the current load. "
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
    filtered.sort_values("period_end")
    .groupby("tracked_item", as_index=False)
    .tail(1)
    .sort_values("composite_score", ascending=False)
)

topic_total = float(latest_topic_snapshot["composite_score"].sum()) if not latest_topic_snapshot.empty else 0.0
top_item_name = latest_topic_snapshot.iloc[0]["tracked_item"] if not latest_topic_snapshot.empty else "n/a"
top_item_score = float(latest_topic_snapshot.iloc[0]["composite_score"]) if not latest_topic_snapshot.empty else 0.0

st.markdown(
    f"""
    <div class="hero-panel">
        <span class="eyebrow">genai trend explorer</span>
        <div class="hero-title">{selected_topic.title()}</div>
        <div class="hero-copy">
            Follow how this topic is moving across {format_source_name(selected_sources["social_media"])},
            {format_source_name(selected_sources["news_mentions"])}, and {format_source_name(selected_sources["google_trends"])}.
            The tracked-item hierarchy stays visible so the topic never feels like a black box.
        </div>
        <div class="chip-row">{tracked_item_chip_markup(topic_items)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Tracked items", f"{filtered['tracked_item'].nunique()}")
metric_columns[1].metric("Topic pulse", f"{topic_total:.1f}")
metric_columns[2].metric("Strongest item", top_item_name, f"{top_item_score:.1f}" if top_item_name != "n/a" else None)
metric_columns[3].metric("Export rows", f"{len(export_frame):,}")

overview_col, ranking_col = st.columns((1.3, 1))

with overview_col:
    st.subheader("Topic pulse")
    st.markdown(
        '<div class="section-note">Each line shows how the topic-level composite score changes over the active window.</div>',
        unsafe_allow_html=True,
    )
    topic_summary_chart = topic_summary.pivot_table(
        index="period_end",
        columns="topic",
        values="composite_score",
        aggfunc="mean",
    ).sort_index()
    if topic_summary_chart.empty:
        st.info("No topic-level history is available for the current selection yet.")
    else:
        st.line_chart(topic_summary_chart, height=320, width="stretch")

with ranking_col:
    st.subheader("Current item stack")
    st.markdown(
        '<div class="section-note">A quick read on which tracked items are doing the most work inside the selected topic.</div>',
        unsafe_allow_html=True,
    )
    if latest_topic_snapshot.empty:
        st.info("No tracked-item ranking is available for the current selection yet.")
    else:
        latest_scores_chart = latest_topic_snapshot[["tracked_item", "composite_score"]].set_index("tracked_item")
        st.bar_chart(latest_scores_chart, height=320, width="stretch")

st.subheader("Source readout")
st.markdown(
    '<div class="section-note">The same topic, broken out by source so you can see where the energy is coming from.</div>',
    unsafe_allow_html=True,
)

source_columns = st.columns(3)
for index, source_key in enumerate(context["data_sources"]["priority_order"]):
    source_field = SOURCE_FIELD_MAP[source_key]
    source_name = selected_sources[source_key]
    latest_source_frame = latest_topic_snapshot[["tracked_item", f"{source_field}_frequency"]].copy()
    latest_source_frame[f"{source_field}_frequency"] = latest_source_frame[f"{source_field}_frequency"].fillna(0.0)

    if latest_source_frame.empty:
        source_total = 0.0
        leader_name = "n/a"
        leader_value = 0.0
    else:
        leader_row = latest_source_frame.sort_values(f"{source_field}_frequency", ascending=False).iloc[0]
        source_total = float(latest_source_frame[f"{source_field}_frequency"].sum())
        leader_name = str(leader_row["tracked_item"])
        leader_value = float(leader_row[f"{source_field}_frequency"])

    with source_columns[index]:
        with st.container(border=True):
            st.markdown(
                source_summary_markup(source_name, source_total, leader_name, leader_value),
                unsafe_allow_html=True,
            )

st.subheader(f"{selected_topic.title()} hierarchy")
st.markdown(
    '<div class="section-note">Topic first, then tracked items, then signal detail. Each card keeps the hierarchy visible without falling back to raw tables.</div>',
    unsafe_allow_html=True,
)

item_columns = st.columns(2)
if latest_topic_snapshot.empty:
    st.info("No tracked-item detail cards are available for the current selection yet.")
else:
    for index, item_name in enumerate(latest_topic_snapshot["tracked_item"].tolist()):
        item_frame = filtered[filtered["tracked_item"] == item_name].copy()
        latest_row = latest_topic_snapshot[latest_topic_snapshot["tracked_item"] == item_name].iloc[0]
        with item_columns[index % 2]:
            render_item_card(item_name, item_frame, latest_row, selected_sources)

st.subheader("Exports")
export_col, dictionary_col = st.columns(2)

with export_col:
    with st.container(border=True):
        st.markdown('<div class="panel-hook"></div>', unsafe_allow_html=True)
        st.markdown("### Filtered CSV")
        st.markdown(
            '<div class="section-note">Download the current topic slice for spreadsheets, notebooks, or your own scripts.</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="Download filtered CSV",
            data=export_frame.to_csv(index=False).encode("utf-8"),
            file_name=f"genai-trends-{selected_topic.replace(' ', '-')}.csv",
            mime="text/csv",
            width="stretch",
        )
        st.caption(f"Includes {len(export_frame):,} rows for the current topic and window.")

with dictionary_col:
    with st.container(border=True):
        st.markdown('<div class="panel-hook"></div>', unsafe_allow_html=True)
        st.markdown("### Data dictionary")
        st.markdown(
            '<div class="section-note">Keep the schema documentation close to the export so the dataset stays understandable outside the app.</div>',
            unsafe_allow_html=True,
        )
        with (Path(__file__).resolve().parent / "data-dictionary.md").open("rb") as handle:
            st.download_button(
                label="Download data dictionary",
                data=handle.read(),
                file_name="data-dictionary.md",
                mime="text/markdown",
                width="stretch",
            )
        st.markdown(
            """
            <div class="note-panel">
                <strong>Current assumptions</strong><br/>
                Mastodon signals come from normalized hashtags, Guardian provides the news layer,
                and the legacy <span class="mono">google_trends_frequency</span> field name remains in the export
                even though the current tertiary provider is Hacker News.
            </div>
            """,
            unsafe_allow_html=True,
        )

with st.expander("Topic map"):
    for topic_name in context["topics"]["initial"]:
        items = tracked_items["topics"][topic_key_for_name(topic_name)]["items"]
        st.markdown(f"**{topic_name.title()}**")
        st.markdown(", ".join(f"`{item}`" for item in items))
