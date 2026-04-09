# Food Sharing Map Dashboard

> **Simplified branch** -- no infrastructure required. Reads directly from the CULTIVATE REST API.
> For the full pipeline version (Airflow, Snowflake, dbt, Terraform), see the [`main`](https://github.com/HCHODUBLIN/foodsharingmap_dashboard/tree/main) branch.

Interactive Streamlit dashboard exploring 500+ food sharing initiatives worldwide, using data from the [ShareCity200 CULTIVATE API](https://www.sharingsolutions.eu).

## Live Dashboard

https://foodsharingmapdashboard.streamlit.app/

## Setup

```bash
pip install -r requirements.txt
cd dashboard
streamlit run app.py
```

## Dashboard Tiles

- **KPIs** -- total initiatives, countries, cities, and activity types at a glance
- **Food Sharing Activities by Type** -- bar and pie charts of activity distribution
- **Geographic Distribution** -- top countries and cities by initiative count, plus an interactive map
- **How Food Is Shared** -- distribution of sharing methods (gifting, selling, collecting, bartering)
- **City Drill-Down** -- select a city to see its initiatives and activity breakdown
- **Data Quality** -- tag validation, geographic outlier detection, duplicate detection, and dead link checking
