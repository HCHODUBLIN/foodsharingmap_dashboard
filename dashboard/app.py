"""
Food Sharing Map Dashboard

Interactive dashboard displaying food sharing initiatives worldwide.
Data sourced from ShareCity200 CULTIVATE REST API.

Supports two modes:
  1. Snowflake mode: reads from gold layer tables (production)
  2. API mode: fetches directly from REST API (demo / no Snowflake)
"""

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Food Sharing Map Dashboard",
    page_icon="🌍",
    layout="wide",
)

API_URL = "https://www.sharingsolutions.eu/wp-json/cultivate/v1/data"
AIRFLOW_API_BASE = "http://localhost:8080/api/v1"  # Configurable


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def load_data_from_api() -> pd.DataFrame:
    """Fetch data directly from the REST API (demo mode)."""
    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame(data)


def load_data_from_snowflake(query: str) -> pd.DataFrame:
    """Load data from Snowflake gold layer."""
    import snowflake.connector

    conn = snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema="GOLD",
    )
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def get_data() -> pd.DataFrame:
    """Load data from Snowflake if configured, otherwise from API."""
    try:
        if "snowflake" in st.secrets:
            df = load_data_from_snowflake(
                "SELECT * FROM FOOD_SHARING_MAP.GOLD.FCT_GEO_DISTRIBUTION"
            )
            return df
    except Exception:
        pass

    # Fallback: fetch from API directly
    return load_data_from_api()


def prepare_api_data(df: pd.DataFrame) -> dict:
    """Process raw API data into analysis-ready DataFrames."""
    # Parse coordinates
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")

    # Explode foodSharingActivities
    activities_df = df.explode("foodSharingActivities").rename(
        columns={"foodSharingActivities": "activity_type"}
    )

    # Explode howItIsShared
    sharing_df = df.explode("howItIsShared").rename(
        columns={"howItIsShared": "sharing_method"}
    )

    # Activity distribution
    activity_dist = (
        activities_df.groupby("activity_type")
        .agg(initiative_count=("id", "nunique"))
        .reset_index()
        .sort_values("initiative_count", ascending=False)
    )
    total = activity_dist["initiative_count"].sum()
    activity_dist["pct_of_total"] = (
        activity_dist["initiative_count"] / total * 100
    ).round(2)

    # Geographic distribution
    geo_dist = (
        activities_df.groupby(["country", "city"])
        .agg(
            initiative_count=("id", "nunique"),
            avg_latitude=("lat", "mean"),
            avg_longitude=("lng", "mean"),
        )
        .reset_index()
        .sort_values("initiative_count", ascending=False)
    )

    # Country summary
    country_summary = (
        activities_df.groupby("country")
        .agg(
            total_initiatives=("id", "nunique"),
            city_count=("city", "nunique"),
            centroid_lat=("lat", "mean"),
            centroid_lng=("lng", "mean"),
        )
        .reset_index()
        .sort_values("total_initiatives", ascending=False)
    )

    # Sharing method distribution
    sharing_dist = (
        sharing_df.groupby("sharing_method")
        .agg(initiative_count=("id", "nunique"))
        .reset_index()
        .sort_values("initiative_count", ascending=False)
    )

    return {
        "raw": df,
        "activities": activities_df,
        "activity_dist": activity_dist,
        "geo_dist": geo_dist,
        "country_summary": country_summary,
        "sharing_dist": sharing_dist,
    }


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------


def render_header():
    st.title("🌍 Food Sharing Map Dashboard")
    st.markdown(
        """
        Exploring **food sharing initiatives** worldwide — data from the
        [ShareCity200 CULTIVATE API](https://www.sharingsolutions.eu).
        """
    )


def render_kpis(data: dict):
    """Top-level KPI metrics."""
    raw = data["raw"]
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Initiatives", f"{raw['id'].nunique():,}")
    col2.metric("Countries", f"{raw['country'].nunique():,}")
    col3.metric("Cities", f"{raw['city'].nunique():,}")
    col4.metric(
        "Activity Types", f"{data['activity_dist'].shape[0]:,}"
    )


def render_activity_tile(data: dict):
    """Tile 1: Food sharing activity type distribution."""
    st.subheader("📊 Food Sharing Activities by Type")

    activity_dist = data["activity_dist"]

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = px.bar(
            activity_dist,
            x="activity_type",
            y="initiative_count",
            color="activity_type",
            text="initiative_count",
            labels={
                "activity_type": "Activity Type",
                "initiative_count": "Number of Initiatives",
            },
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            showlegend=False,
            xaxis_tickangle=-45,
            height=450,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig_pie = px.pie(
            activity_dist,
            values="initiative_count",
            names="activity_type",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)


def render_geo_tile(data: dict):
    """Tile 2: Geographic distribution."""
    st.subheader("🗺️ Initiatives by Country & City")

    country_summary = data["country_summary"]

    # Top countries bar chart
    top_n = st.slider("Show top N countries", 5, 30, 15)
    top_countries = country_summary.head(top_n)

    fig = px.bar(
        top_countries,
        x="country",
        y="total_initiatives",
        color="total_initiatives",
        text="total_initiatives",
        labels={
            "country": "Country",
            "total_initiatives": "Number of Initiatives",
        },
        color_continuous_scale="Greens",
    )
    fig.update_layout(xaxis_tickangle=-45, height=450, showlegend=False)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Interactive map
    st.subheader("🌐 Initiative Locations")
    map_data = data["raw"].dropna(subset=["lat", "lng"])

    fig_map = px.scatter_mapbox(
        map_data,
        lat="lat",
        lon="lng",
        hover_name="name",
        hover_data=["country", "city"],
        color="country",
        zoom=2,
        height=600,
    )
    fig_map.update_layout(
        mapbox_style="carto-positron",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        showlegend=False,
    )
    st.plotly_chart(fig_map, use_container_width=True)


def render_sharing_methods(data: dict):
    """Bonus tile: How food is shared."""
    st.subheader("🤝 How Food Is Shared")

    sharing_dist = data["sharing_dist"]

    fig = px.bar(
        sharing_dist,
        x="sharing_method",
        y="initiative_count",
        color="sharing_method",
        text="initiative_count",
        labels={
            "sharing_method": "Sharing Method",
            "initiative_count": "Number of Initiatives",
        },
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_layout(showlegend=False, height=400)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def render_country_drilldown(data: dict):
    """Country-level drill-down."""
    st.subheader("🔍 Country Drill-Down")

    countries = sorted(data["raw"]["country"].dropna().unique())
    selected = st.selectbox("Select a country", countries)

    if selected:
        country_data = data["activities"][
            data["activities"]["country"] == selected
        ]

        col1, col2 = st.columns(2)

        with col1:
            city_counts = (
                country_data.groupby("city")
                .agg(count=("id", "nunique"))
                .reset_index()
                .sort_values("count", ascending=False)
            )
            fig = px.bar(
                city_counts,
                x="city",
                y="count",
                text="count",
                labels={"city": "City", "count": "Initiatives"},
                color_discrete_sequence=["#2ecc71"],
            )
            fig.update_layout(
                title=f"Cities in {selected}", height=400
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            act_counts = (
                country_data.groupby("activity_type")
                .agg(count=("id", "nunique"))
                .reset_index()
            )
            fig = px.pie(
                act_counts,
                values="count",
                names="activity_type",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(
                title=f"Activities in {selected}", height=400
            )
            st.plotly_chart(fig, use_container_width=True)


def render_manual_trigger():
    """Manual pipeline trigger button (calls Airflow REST API)."""
    st.subheader("⚙️ Pipeline Control")
    st.markdown(
        "Trigger a manual data refresh by calling the Airflow REST API."
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        airflow_url = st.text_input(
            "Airflow API URL",
            value=AIRFLOW_API_BASE,
        )

    with col2:
        st.markdown("")  # spacing
        st.markdown("")

    if st.button("🔄 Trigger Pipeline Run", type="primary"):
        try:
            dag_id = "food_sharing_map_pipeline"
            url = f"{airflow_url}/dags/{dag_id}/dagRuns"
            response = requests.post(
                url,
                json={"conf": {}},
                auth=("airflow", "airflow"),  # default dev credentials
                timeout=10,
            )
            if response.status_code in (200, 201):
                st.success(
                    f"Pipeline triggered successfully! "
                    f"Run ID: {response.json().get('dag_run_id', 'N/A')}"
                )
            else:
                st.error(
                    f"Failed to trigger pipeline: {response.status_code} — "
                    f"{response.text}"
                )
        except requests.exceptions.ConnectionError:
            st.warning(
                "Could not connect to Airflow API. "
                "Ensure Airflow is running and the URL is correct."
            )
        except Exception as e:
            st.error(f"Error triggering pipeline: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    render_header()

    with st.spinner("Loading data..."):
        raw_df = load_data_from_api()
        data = prepare_api_data(raw_df)

    render_kpis(data)

    st.divider()

    # Tile 1: Activity distribution
    render_activity_tile(data)

    st.divider()

    # Tile 2: Geographic distribution
    render_geo_tile(data)

    st.divider()

    # Bonus: Sharing methods
    render_sharing_methods(data)

    st.divider()

    # Drill-down
    render_country_drilldown(data)

    st.divider()

    # Manual trigger
    render_manual_trigger()

    # Footer
    st.divider()
    st.caption(
        "Data source: [ShareCity200 CULTIVATE API]"
        "(https://www.sharingsolutions.eu/wp-json/cultivate/v1/data) | "
        "Built with Streamlit"
    )


if __name__ == "__main__":
    main()
