from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from genai_trends.config import load_project_context, load_tracked_items
from genai_trends.data import build_export_frame, build_topic_summary, generate_dataset


st.set_page_config(
    page_title="genAI Trends Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)


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
) -> pd.DataFrame:
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
default_start = today - timedelta(days=30)

st.title("genAI Trends Dashboard")
st.caption(
    "Config-driven scaffold for topic trends across Bluesky, GDELT, and Google Trends. "
    "The current build uses deterministic sample data so the dashboard shell can be implemented "
    "before live collectors are connected."
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
    date_range = st.date_input(
        "Period",
        value=(default_start, today),
        min_value=today - timedelta(days=365),
        max_value=today,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        period_start, period_end = date_range
    else:
        period_start, period_end = default_start, today

data = get_dataset(
    period_start=period_start,
    period_end=period_end,
    granularity=selected_granularity,
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
    st.line_chart(topic_summary_chart, use_container_width=True)

with details_col:
    st.subheader(f"{selected_topic} latest ranking")
    st.dataframe(
        latest_topic_snapshot[["tracked_item", "composite_score", "available_sources"]],
        use_container_width=True,
        hide_index=True,
    )

st.subheader(f"{selected_topic} tracked items over time")
tracked_item_chart = filtered.pivot_table(
    index="period_end",
    columns="tracked_item",
    values="composite_score",
    aggfunc="mean",
).sort_index()
st.line_chart(tracked_item_chart, use_container_width=True)

source_cols = st.columns(3)
for index, source_key in enumerate(context["data_sources"]["priority_order"]):
    source_name = selected_sources[source_key]
    source_frame = filtered[["period_end", "tracked_item", f"{source_name}_frequency"]].rename(
        columns={f"{source_name}_frequency": "source_frequency"}
    )
    with source_cols[index]:
        st.markdown(f"**{source_name.replace('_', ' ').title()}**")
        st.dataframe(
            source_frame.sort_values(["period_end", "tracked_item"], ascending=[False, True]),
            use_container_width=True,
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
    )
    st.dataframe(export_frame, use_container_width=True, hide_index=True)

with dictionary_col:
    with (Path(__file__).resolve().parent / "data-dictionary.md").open("rb") as handle:
        st.download_button(
            label="Download data dictionary",
            data=handle.read(),
            file_name="data-dictionary.md",
            mime="text/markdown",
        )
    st.markdown("**About this data**")
    st.markdown(
        "- Source grouping follows the configured priority order.\n"
        "- Composite score uses configurable source weights.\n"
        "- If one source is missing, the app keeps remaining data and warns.\n"
        "- The export includes the currently selected topic and period only."
    )

with st.expander("Tracked item seed list"):
    st.json(tracked_items)
