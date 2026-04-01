"""
Food Sharing Map Dashboard

Interactive dashboard displaying food sharing initiatives worldwide.
Data sourced from ShareCity200 CULTIVATE REST API.

Supports two modes:
  1. Snowflake mode: reads from gold layer tables (production)
  2. API mode: fetches directly from REST API (demo / no Snowflake)
"""

import json

from datetime import datetime

import numpy as np
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

# CULTIVATE brand palette (from brandbook v1.1)
BROCCOGREEN = "#05A54B"
CARROTORANGE = "#EB502D"
CUCUMBER = "#8CC896"
BANANA = "#FCD9A3"
RADISH = "#C8146E"
SOIL = "#3C140F"
CULTIVATE_PALETTE = [
    BROCCOGREEN, CARROTORANGE, CUCUMBER, BANANA, RADISH, SOIL,
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def load_data_from_api() -> pd.DataFrame:
    """Fetch data directly from the REST API (demo mode)."""
    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    payload = response.json()

    # API returns {"success": ..., "data": [...]}
    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = payload

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
        df = pd.read_sql(query, conn)
        df.columns = [c.lower() for c in df.columns]
        return df
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def load_snowflake_data() -> dict:
    """Load all gold tables from Snowflake."""
    activity_dist = load_data_from_snowflake(
        "SELECT * FROM FOOD_SHARING_MAP.GOLD.FCT_ACTIVITY_DISTRIBUTION"
    )
    geo_dist = load_data_from_snowflake(
        "SELECT * FROM FOOD_SHARING_MAP.GOLD.FCT_GEO_DISTRIBUTION"
    )
    country_summary = load_data_from_snowflake(
        "SELECT * FROM FOOD_SHARING_MAP.GOLD.FCT_COUNTRY_SUMMARY"
    )
    sharing_methods = load_data_from_snowflake(
        "SELECT * FROM FOOD_SHARING_MAP.SILVER.INT_INITIATIVES_SHARING_METHODS"
    )
    sharing_dist = (
        sharing_methods.groupby("sharing_method")
        .agg(initiative_count=("initiative_id", "nunique"))
        .reset_index()
        .sort_values("initiative_count", ascending=False)
    )
    return {
        "activity_dist": activity_dist,
        "geo_dist": geo_dist,
        "country_summary": country_summary,
        "sharing_dist": sharing_dist,
    }


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

    activity_dist = data["activity_dist"].sort_values(
        "initiative_count", ascending=False,
    )

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
            color_discrete_sequence=CULTIVATE_PALETTE,
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
            color_discrete_sequence=CULTIVATE_PALETTE,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)


def render_geo_tile(data: dict):
    """Tile 2: Geographic distribution."""
    st.subheader("🗺️ Geographic Distribution")

    country_summary = data["country_summary"]
    geo_dist = data["geo_dist"]

    col_country, col_city = st.columns(2)

    with col_country:
        st.markdown("**By Country**")
        top_n_country = st.slider(
            "Show top N countries", 5, 50, 15, key="top_country",
        )
        top_countries = country_summary.sort_values(
            "total_initiatives", ascending=False,
        ).head(top_n_country)

        fig = px.bar(
            top_countries,
            x="country",
            y="total_initiatives",
            color="total_initiatives",
            text="total_initiatives",
            labels={
                "country": "Country",
                "total_initiatives": "Initiatives",
            },
            color_continuous_scale=[
                [0, CUCUMBER], [0.5, BROCCOGREEN], [1, SOIL],
            ],
        )
        fig.update_layout(
            xaxis_tickangle=-45, height=500, showlegend=False,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with col_city:
        st.markdown("**By City**")
        top_n_city = st.slider(
            "Show top N cities", 5, 50, 20, key="top_city",
        )
        top_cities = geo_dist.sort_values(
            "initiative_count", ascending=False,
        ).head(top_n_city)

        fig = px.bar(
            top_cities,
            x="city",
            y="initiative_count",
            color="initiative_count",
            text="initiative_count",
            labels={
                "city": "City",
                "initiative_count": "Initiatives",
            },
            color_continuous_scale=[
                [0, BANANA], [0.5, CARROTORANGE], [1, RADISH],
            ],
        )
        fig.update_layout(
            xaxis_tickangle=-45, height=500, showlegend=False,
        )
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
        color_discrete_sequence=CULTIVATE_PALETTE,
    )
    fig.update_layout(showlegend=False, height=400)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def render_city_drilldown(data: dict):
    """City-level drill-down."""
    st.subheader("🔍 City Drill-Down")

    cities = sorted(data["raw"]["city"].dropna().unique())
    selected = st.selectbox("Select a city", cities)

    if selected:
        city_data = data["activities"][
            data["activities"]["city"] == selected
        ]

        col1, col2 = st.columns(2)

        with col1:
            initiative_list = (
                city_data.groupby("id")
                .agg(
                    name=("name", "first"),
                    activities=("activity_type", lambda x: ", ".join(x.dropna())),
                )
                .reset_index()
            )
            st.markdown(f"**{len(initiative_list)} initiatives in {selected}**")
            st.dataframe(
                initiative_list[["name", "activities"]].rename(
                    columns={"name": "Initiative", "activities": "Activities"},
                ),
                use_container_width=True,
                hide_index=True,
            )

        with col2:
            act_counts = (
                city_data.groupby("activity_type")
                .agg(count=("id", "nunique"))
                .reset_index()
                .sort_values("count", ascending=False)
            )
            fig = px.pie(
                act_counts,
                values="count",
                names="activity_type",
                color_discrete_sequence=CULTIVATE_PALETTE,
            )
            fig.update_layout(
                title=f"Activities in {selected}", height=400,
            )
            st.plotly_chart(fig, use_container_width=True)


def render_data_quality(data: dict):
    """Data quality checks — flag incorrect or unexpected values."""
    st.subheader("🔎 Data Quality Check")

    today = datetime.now().strftime("%Y-%m-%d")
    st.info(
        f"**Note for the Sharing Solutions admin:** "
        f"This data is fetched directly from the "
        f"[Food Sharing Map](https://www.sharingsolutions.eu/food-sharing-map/) "
        f"on **{today}**. "
        f"Please review the flagged issues below and adjust in the platform."
    )

    raw = data["raw"]

    VALID_ACTIVITIES = {"Distribution", "Growing", "Cooking & Eating"}
    VALID_SHARING = {"Gifting", "Selling", "Collecting", "Bartering"}

    # Check activities
    activity_issues = []
    for _, row in raw.iterrows():
        activities = row.get("foodSharingActivities", [])
        if not isinstance(activities, list):
            continue
        for a in activities:
            if a not in VALID_ACTIVITIES:
                activity_issues.append({
                    "Initiative ID": row.get("id", "N/A"),
                    "Initiative Name": row.get("name", "N/A"),
                    "Country": row.get("country", "N/A"),
                    "Field": "foodSharingActivities",
                    "Invalid Value": repr(a),
                })

    # Check sharing methods
    sharing_issues = []
    for _, row in raw.iterrows():
        methods = row.get("howItIsShared", [])
        if not isinstance(methods, list):
            continue
        for m in methods:
            if m not in VALID_SHARING:
                sharing_issues.append({
                    "Initiative ID": row.get("id", "N/A"),
                    "Initiative Name": row.get("name", "N/A"),
                    "Country": row.get("country", "N/A"),
                    "Field": "howItIsShared",
                    "Invalid Value": repr(m),
                })

    all_issues = activity_issues + sharing_issues

    st.markdown("### Tag Issues")
    if all_issues:
        st.warning(f"Found {len(all_issues)} tag issues")
        st.dataframe(
            pd.DataFrame(all_issues),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No tag issues found")

    # Geographic outlier check
    st.markdown("### Geographic Outliers")
    st.markdown(
        "Initiatives whose coordinates are far from the median "
        "of their city (possible data entry errors)."
    )

    geo_df = raw.copy()
    geo_df["lat"] = pd.to_numeric(geo_df["lat"], errors="coerce")
    geo_df["lng"] = pd.to_numeric(geo_df["lng"], errors="coerce")
    geo_df = geo_df.dropna(subset=["lat", "lng", "city"])

    # Filter out (0,0) or invalid ranges
    invalid_coords = geo_df[
        (geo_df["lat"] == 0) & (geo_df["lng"] == 0)
        | (geo_df["lat"].abs() > 90)
        | (geo_df["lng"].abs() > 180)
    ]

    # Calculate distance from city median
    city_medians = geo_df.groupby("city").agg(
        median_lat=("lat", "median"),
        median_lng=("lng", "median"),
        city_count=("id", "count"),
    ).reset_index()

    geo_merged = geo_df.merge(city_medians, on="city")
    # Only check cities with 2+ initiatives (need comparison)
    geo_merged = geo_merged[geo_merged["city_count"] >= 2]

    # Haversine-like distance in km (simplified)
    geo_merged["dist_km"] = np.sqrt(
        ((geo_merged["lat"] - geo_merged["median_lat"]) * 111) ** 2
        + (
            (geo_merged["lng"] - geo_merged["median_lng"])
            * 111
            * np.cos(np.radians(geo_merged["median_lat"]))
        ) ** 2
    )

    threshold_km = st.slider(
        "Distance threshold (km)", 10, 500, 100, key="geo_threshold",
    )
    outliers = geo_merged[geo_merged["dist_km"] > threshold_km]

    if len(outliers) > 0 or len(invalid_coords) > 0:
        geo_issues = []

        for _, row in invalid_coords.iterrows():
            geo_issues.append({
                "Initiative ID": row.get("id", "N/A"),
                "Initiative Name": row.get("name", "N/A"),
                "City": row.get("city", "N/A"),
                "Country": row.get("country", "N/A"),
                "Lat": row["lat"],
                "Lng": row["lng"],
                "Issue": "Invalid coordinates (0,0 or out of range)",
            })

        for _, row in outliers.iterrows():
            geo_issues.append({
                "Initiative ID": row.get("id", "N/A"),
                "Initiative Name": row.get("name", "N/A"),
                "City": row["city"],
                "Country": row.get("country", "N/A"),
                "Lat": round(row["lat"], 4),
                "Lng": round(row["lng"], 4),
                "Issue": f"{row['dist_km']:.0f} km from city median",
            })

        st.warning(f"Found {len(geo_issues)} geographic issues")
        st.dataframe(
            pd.DataFrame(geo_issues),
            use_container_width=True,
            hide_index=True,
        )

        # Map showing outliers in red
        if len(outliers) > 0:
            fig_map = px.scatter_mapbox(
                outliers,
                lat="lat",
                lon="lng",
                hover_name="name",
                hover_data=["city", "country", "dist_km"],
                color_discrete_sequence=[CARROTORANGE],
                zoom=2,
                height=400,
            )
            fig_map.update_layout(
                mapbox_style="carto-positron",
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                showlegend=False,
            )
            st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.success("No geographic outliers found")

    # Potential duplicates check
    st.markdown("### Potential Duplicates")
    st.markdown(
        "Initiatives within the same city with similar names or URLs. "
        "These may be duplicate entries."
    )

    from difflib import SequenceMatcher

    dup_df = raw.dropna(subset=["city"]).copy()
    duplicates = []

    for city, group in dup_df.groupby("city"):
        if len(group) < 2:
            continue
        rows = group.to_dict("records")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                STOP_WORDS = {
                    "community", "gardens", "garden",
                    "cooperativa", "sostenible",
                    "fundación", "fundació", "hort",
                    "jardins", "la", "le", "les",
                    "marseille", "milano", "caritas",
                    "food", "association", "charita",
                    "banco", "asociación", "associaci",
                }

                def clean_name(name):
                    words = name.lower().split()
                    return " ".join(
                        w for w in words if w not in STOP_WORDS
                    )

                name_a = clean_name(str(rows[i].get("name", "")))
                name_b = clean_name(str(rows[j].get("name", "")))
                import re

                def clean_url(url):
                    """Remove protocol, www, and TLD for comparison."""
                    url = re.sub(r"https?://", "", url)
                    url = re.sub(r"^www\.", "", url)
                    url = re.sub(r"\.[a-z]{2,3}/?$", "", url)
                    return url.strip("/").lower()

                url_a = clean_url(str(rows[i].get("url", "")))
                url_b = clean_url(str(rows[j].get("url", "")))

                name_sim = SequenceMatcher(None, name_a, name_b).ratio()
                url_sim = SequenceMatcher(
                    None, url_a, url_b,
                ).ratio() if url_a and url_b else 0

                if name_sim > 0.7 or (url_sim > 0.8 and url_a != ""):
                    reason = []
                    if name_sim > 0.7:
                        reason.append(f"name {name_sim:.0%} similar")
                    if url_sim > 0.8:
                        reason.append(f"URL {url_sim:.0%} similar")
                    reason_str = ", ".join(reason)
                    duplicates.append({
                        "City": city,
                        "ID": rows[i].get("id", "N/A"),
                        "Name": rows[i].get("name", "N/A"),
                        "URL": rows[i].get("url", ""),
                        "Reason": reason_str,
                    })
                    duplicates.append({
                        "City": city,
                        "ID": rows[j].get("id", "N/A"),
                        "Name": rows[j].get("name", "N/A"),
                        "URL": rows[j].get("url", ""),
                        "Reason": reason_str,
                    })

    if duplicates:
        pairs = len(duplicates) // 2
        st.warning(f"Found {pairs} potential duplicate pairs")
        dup_frame = pd.DataFrame(duplicates)
        # Assign pair number (every 2 rows = 1 pair)
        dup_frame["_pair"] = [i // 2 for i in range(len(dup_frame))]
        # Get max percentage per pair for sorting
        dup_frame["_sort"] = dup_frame["Reason"].str.extractall(
            r"(\d+)%"
        ).astype(int).groupby(level=0).max()[0]
        dup_frame["_sort"] = dup_frame["_sort"].fillna(0)
        pair_sort = dup_frame.groupby("_pair")["_sort"].max()
        dup_frame["_pair_sort"] = dup_frame["_pair"].map(pair_sort)
        dup_frame = dup_frame.sort_values(
            ["_pair_sort", "_pair"], ascending=[False, True],
        ).drop(columns=["_pair", "_sort", "_pair_sort"])
        st.dataframe(
            dup_frame,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No potential duplicates found")


def render_manual_trigger():
    """Manual pipeline trigger — calls API Gateway to start EC2 + Airflow."""
    st.subheader("⚙️ Pipeline Control")
    st.markdown(
        "Start the pipeline by calling the API Gateway endpoint. "
        "This invokes Lambda → starts EC2 → boots Airflow → "
        "runs the DAG automatically."
    )

    trigger_url = st.secrets.get("aws", {}).get("trigger_api_url", "")

    if not trigger_url:
        st.warning(
            "Trigger API URL not configured. "
            "Add `[aws]` section with `trigger_api_url` to "
            "`dashboard/.streamlit/secrets.toml`."
        )
        return

    if st.button("🔄 Start Pipeline", type="primary"):
        with st.spinner("Starting EC2 instance..."):
            try:
                response = requests.post(trigger_url, json={}, timeout=15)

                if response.status_code == 200:
                    body = response.json()
                    st.success(
                        f"EC2 instance starting! "
                        f"Airflow DAG will run automatically in ~2 minutes. "
                        f"{body.get('body', '')}"
                    )
                else:
                    st.error(
                        f"Trigger failed: {response.status_code} — "
                        f"{response.text}"
                    )
            except requests.exceptions.ConnectionError:
                st.warning("Could not connect to the trigger API.")
            except Exception as e:
                st.error(f"Failed to trigger pipeline: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    render_header()

    # Try Snowflake first, fallback to API
    use_snowflake = False
    try:
        if "snowflake" in st.secrets:
            with st.spinner("Loading data from Snowflake..."):
                snowflake_data = load_snowflake_data()
            use_snowflake = True
    except Exception:
        pass

    # Always load API data for data quality + fallback
    with st.spinner("Loading data from API..."):
        raw_df = load_data_from_api()
        api_data = prepare_api_data(raw_df)

    if use_snowflake:
        # Use Snowflake GOLD data for dashboard charts
        data = {
            "activity_dist": snowflake_data["activity_dist"],
            "geo_dist": snowflake_data["geo_dist"],
            "country_summary": snowflake_data["country_summary"],
            "sharing_dist": snowflake_data["sharing_dist"],
            "raw": api_data["raw"],
            "activities": api_data["activities"],
        }
    else:
        data = api_data

    render_kpis(data)

    tab_dashboard, tab_quality = st.tabs(["Dashboard", "Data Quality"])

    with tab_dashboard:
        st.divider()
        render_activity_tile(data)
        st.divider()
        render_geo_tile(data)
        st.divider()
        render_sharing_methods(data)
        st.divider()
        render_city_drilldown(data)
        st.divider()
        render_manual_trigger()

    with tab_quality:
        render_data_quality(api_data)

    # Footer
    st.divider()
    st.caption(
        "Data source: [ShareCity200 CULTIVATE API]"
        "(https://www.sharingsolutions.eu/wp-json/cultivate/v1/data) | "
        "Built with Streamlit"
    )


if __name__ == "__main__":
    main()
