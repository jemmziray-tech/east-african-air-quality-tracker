import streamlit as st
import sqlite3
import pandas as pd
import time
import pydeck as pdk

st.set_page_config(page_title="East Africa AQI", layout="wide")

DB_FILE = "air_quality.db"


# --- READ FROM DATABASE ---
def get_latest_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        # SQL Query: Get the absolute latest record for each city
        query = """
            SELECT city, lat, lon, pm2_5, pm10, MAX(timestamp) as last_updated
            FROM pollution_log
            GROUP BY city
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except sqlite3.OperationalError:
        return pd.DataFrame()  # Return empty if DB doesn't exist yet


# --- UI RENDERING ---
st.title("🌍 East Africa Air Quality Sentinel")
st.markdown(
    "Live PM2.5 & PM10 monitoring. Data is decoupled and ingested via SQLite background harvester."
)

df = get_latest_data()

if not df.empty:
    st.success(f"Database Connected. Last updated: {df['last_updated'].max()}")

    # 1. Metrics Layout
    cols = st.columns(len(df))
    for i, row in df.iterrows():
        with cols[i]:
            st.metric(
                label=row["city"],
                value=f"{row['pm2_5']} µg/m³",
                delta="PM 2.5",
                delta_color="inverse",
            )

    # 2. Geospatial Map
    # Color logic: Red if PM2.5 > 25 (WHO guideline), else Green
    df["color"] = df["pm2_5"].apply(
        lambda x: [255, 0, 0, 200] if x > 25 else [0, 255, 128, 200]
    )

    view_state = pdk.ViewState(latitude=-2.0, longitude=35.0, zoom=4.5, pitch=30)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_color="color",
        get_radius=30000,
        pickable=True,
    )

    st.pydeck_chart(
        pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            initial_view_state=view_state,
            layers=[layer],
            tooltip={"text": "{city}\nPM 2.5: {pm2_5} µg/m³\nPM 10: {pm10} µg/m³"},
        )
    )

    # 3. Raw Database View
    st.markdown("### 🗄️ Raw Database Output (Latest Records)")
    st.dataframe(
        df[["city", "pm2_5", "pm10", "last_updated"]], use_container_width=True
    )

else:
    st.warning(
        "⚠️ Database is empty. Ensure `harvester.py` is running in the background."
    )

# Auto-refresh UI every 10 seconds
time.sleep(10)
st.rerun()
