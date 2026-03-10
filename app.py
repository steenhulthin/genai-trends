from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from genai_trends.config import load_project_context, load_tracked_items
from genai_trends.data import SOURCE_FIELD_MAP, build_export_frame, build_topic_summary, generate_dataset
from genai_trends.logging_utils import get_logger


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


context = get_context()
tracked_items = get_tracked_items()

today = date.today()
default_start = today - timedelta(days=6)

st.title("genAI Trends Dashboard")
st.caption(
    "Config-driven dashboard for topic trends across Reddit, Guardian Open Platform, and Google Trends. "
    "The current implementation uses Reddit app-only OAuth, the Guardian content API, and SerpApi "
    "for Google Trends."
)

with st.sidebar:
    st.header("Filters")
    topic_options = context["topics"]["initial"]
    selected_topic = st.selectbox("Topic", topic_options, index=0)
    granularity_options = context["time"]["granularity"]["allowed"]
    default_granularity = context["time"]["granularity"]["default"]
    selected_granularity = st.selectbox(
        "Granularity",
        granularity_options,
        index=granularity_options.index(default_granularity),
    )
    st.caption("Current fetch scope is fixed to the latest 7 days while the live collectors are being stabilized.")
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

partial_data_rows = filtered[filtered["partial_data_warning"]]
if not partial_data_rows.empty:
    st.warning(
        "Some source data is unavailable for part of the selected result set. "
        "The dashboard is keeping the remaining data visible."
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

metric_columns = st.columns(3)
latest_topic_snapshot = (
    filtered.sort_values("period_end")
    .groupby("tracked_item", as_index=False)
    .tail(1)
    .sort_values("composite_score", ascending=False)
)

metric_columns[0].metric("Tracked items", f"{filtered['tracked_item'].nunique()}")
metric_columns[1].metric("Rows in export", f"{len(export_frame):,}")
if latest_topic_snapshot.empty:
    metric_columns[2].metric("Top tracked item", "n/a")
else:
    metric_columns[2].metric(
        "Top tracked item",
        latest_topic_snapshot.iloc[0]["tracked_item"],
        f"{latest_topic_snapshot.iloc[0]['composite_score']:.1f}",
    )

overview_col, details_col = st.columns((1.2, 1))

with overview_col:
    st.subheader("Topic overview")
    topic_summary_chart = topic_summary.pivot_table(
        index="period_end",
        columns="topic",
        values="composite_score",
        aggfunc="mean",
    ).sort_index()
    st.line_chart(topic_summary_chart, width="stretch")

with details_col:
    st.subheader(f"{selected_topic} latest ranking")
    st.dataframe(
        latest_topic_snapshot[["tracked_item", "composite_score", "available_sources"]],
        width="stretch",
        hide_index=True,
    )

st.subheader(f"{selected_topic} tracked items over time")
tracked_item_chart = filtered.pivot_table(
    index="period_end",
    columns="tracked_item",
    values="composite_score",
    aggfunc="mean",
).sort_index()
st.line_chart(tracked_item_chart, width="stretch")

source_cols = st.columns(3)
for index, source_key in enumerate(context["data_sources"]["priority_order"]):
    source_name = selected_sources[source_key]
    source_field = SOURCE_FIELD_MAP[source_key]
    source_frame = filtered[["period_end", "tracked_item", f"{source_field}_frequency"]].rename(
        columns={f"{source_field}_frequency": "source_frequency"}
    )
    with source_cols[index]:
        st.markdown(f"**{source_name.replace('_', ' ').title()}**")
        st.dataframe(
            source_frame.sort_values(["period_end", "tracked_item"], ascending=[False, True]),
            width="stretch",
            hide_index=True,
        )

st.subheader("Exports")
export_col, dictionary_col = st.columns(2)

with export_col:
    st.download_button(
        label="Download filtered CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name=f"genai-trends-{selected_topic.replace(' ', '-')}.csv",
        mime="text/csv",
        width="stretch",
    )
    st.dataframe(export_frame, width="stretch", hide_index=True)

with dictionary_col:
    with (Path(__file__).resolve().parent / "data-dictionary.md").open("rb") as handle:
        st.download_button(
            label="Download data dictionary",
            data=handle.read(),
            file_name="data-dictionary.md",
            mime="text/markdown",
            width="stretch",
        )
    st.markdown("**About this data**")
    st.markdown(
        "- Source grouping follows the configured priority order.\n"
        "- Composite score uses configurable source weights.\n"
        "- If one source is missing, the app keeps remaining data and warns.\n"
        "- The export includes the currently selected topic and period only.\n"
        "- Live providers currently require external API credentials for fully populated results.\n"
        "- Detailed runtime instrumentation is written to the log files."
    )

with st.expander("Tracked item seed list"):
    st.json(tracked_items)
