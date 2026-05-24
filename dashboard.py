import streamlit as st
import sqlite3
import pandas as pd
import pydeck as pdk
import os

# --- 1. CLOUD ORCHESTRATION ---
# Tunaleta harvester hapa ili dashboard ijisimamie yenyewe kwenye cloud
from harvester import setup_database, run_etl_pipeline

# Usanifu wa Ukurasa Mkuu
st.set_page_config(
    page_title="Tanzania AQI Intelligence", page_icon="🇹🇿", layout="wide"
)
DB_FILE = "air_quality.db"

# Kama tupo kwenye cloud na database haipo, itengeneze mara moja
if not os.path.exists(DB_FILE):
    setup_database()


# --- 2. DATA RETRIEVAL ---
def get_latest_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT city, lat, lon, pm2_5, pm10, MAX(timestamp) as last_updated
            FROM pollution_log
            GROUP BY city
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    # Tumerekebisha exception ili kuzuia programu isicrash kama table haipo
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return pd.DataFrame()


# --- HEADER ---
st.title("🇹🇿 Tanzania Regional Air Quality Intelligence")
st.markdown(
    "Live monitoring network covering all 26 administrative regions. Data automatically refreshed via localized ETL pipeline."
)


# --- MAIN DASHBOARD FRAGMENT ---
# Fragment hii inajirudia kila baada ya dakika 5 (5m).
# Hii inachukua nafasi ya 'while True' loop ya kwenye harvester yako ya zamani.
@st.fragment(run_every="5m")
def render_dashboard():

    # 1. Trigger the harvester pipeline directly from the UI thread
    with st.spinner("📡 Harvesting live satellite data across Tanzania..."):
        run_etl_pipeline()

    # 2. Read the newly fetched data
    df = get_latest_data()

    if df.empty:
        st.warning(
            "⚠️ Mfumo unakusanya data (System initializing). Tafadhali subiri..."
        )
        return

    # 3. KPIs (Key Performance Indicators)
    national_avg = df["pm2_5"].mean()
    worst_region = df.loc[df["pm2_5"].idxmax()]
    best_region = df.loc[df["pm2_5"].idxmin()]
    last_update = df["last_updated"].max()

    st.success(f"🟢 System Online | Last Sync: {last_update}")

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("National Average (PM 2.5)", f"{national_avg:.1f} µg/m³")
    kpi2.metric(
        "Most Polluted Region",
        worst_region["city"],
        f"{worst_region['pm2_5']} µg/m³",
        delta_color="inverse",
    )
    kpi3.metric(
        "Cleanest Region",
        best_region["city"],
        f"{best_region['pm2_5']} µg/m³",
        delta_color="normal",
    )

    st.divider()

    # 4. Geospatial Map & Ranking Table Layout
    col_map, col_table = st.columns([1.5, 1])

    with col_map:
        st.markdown("### 🗺️ Sensor Map")
        df["color"] = df["pm2_5"].apply(
            lambda x: [255, 75, 75, 200] if x > 25 else [75, 255, 120, 200]
        )

        view_state = pdk.ViewState(
            latitude=-6.3690, longitude=34.8888, zoom=5.2, pitch=35
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_color="color",
            get_radius=20000,
            pickable=True,
        )

        st.pydeck_chart(
            pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                initial_view_state=view_state,
                layers=[layer],
                tooltip={"text": "{city}\nPM 2.5: {pm2_5} µg/m³"},
            )
        )

    with col_table:
        st.markdown("### 📊 Air Quality Leaderboard")
        st.caption("Sorted by PM 2.5 concentration")

        df_sorted = df.sort_values(by="pm2_5", ascending=False).reset_index(drop=True)

        st.dataframe(
            df_sorted[["city", "pm2_5", "pm10"]],
            column_config={
                "city": st.column_config.TextColumn("Region"),
                "pm2_5": st.column_config.ProgressColumn(
                    "PM 2.5 Level",
                    help="WHO guideline is < 25 µg/m³",
                    format="%f",
                    min_value=0,
                    max_value=70,
                ),
                "pm10": "PM 10",
            },
            hide_index=True,
            use_container_width=True,
            height=450,
        )


# Washa dashboard
render_dashboard()
