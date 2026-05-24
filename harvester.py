import requests
import sqlite3
import time
import logging
import concurrent.futures
from datetime import datetime

# --- 1. CONFIGURATION ---
DB_FILE = "air_quality.db"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Coordinates for 26 Tanzanian Regions
TANZANIA_REGIONS = {
    "Arusha": {"lat": -3.3667, "lon": 36.6833},
    "Coast (Pwani)": {"lat": -6.7667, "lon": 38.9833},
    "Dar es Salaam": {"lat": -6.7924, "lon": 39.2083},
    "Dodoma": {"lat": -6.1731, "lon": 35.7383},
    "Geita": {"lat": -2.8667, "lon": 32.2333},
    "Iringa": {"lat": -7.7667, "lon": 35.7000},
    "Kagera": {"lat": -1.3333, "lon": 31.8167},
    "Katavi": {"lat": -6.3333, "lon": 31.0667},
    "Kigoma": {"lat": -4.8769, "lon": 29.6265},
    "Kilimanjaro": {"lat": -3.3500, "lon": 37.3333},
    "Lindi": {"lat": -9.9969, "lon": 39.7144},
    "Manyara": {"lat": -4.2167, "lon": 35.7500},
    "Mara": {"lat": -1.5000, "lon": 33.8000},
    "Mbeya": {"lat": -8.9000, "lon": 33.4500},
    "Morogoro": {"lat": -6.8228, "lon": 37.6612},
    "Mtwara": {"lat": -10.2667, "lon": 40.1833},
    "Mwanza": {"lat": -2.5167, "lon": 32.9000},
    "Njombe": {"lat": -9.3333, "lon": 34.7667},
    "Rukwa": {"lat": -7.9667, "lon": 31.6167},
    "Ruvuma": {"lat": -10.6833, "lon": 35.6500},
    "Shinyanga": {"lat": -3.6619, "lon": 33.4231},
    "Simiyu": {"lat": -2.8000, "lon": 33.9833},
    "Singida": {"lat": -4.8167, "lon": 34.7500},
    "Songwe": {"lat": -9.1167, "lon": 32.9333},
    "Tabora": {"lat": -5.0167, "lon": 32.8000},
    "Tanga": {"lat": -5.0667, "lon": 39.1000},
}


# --- 2. DATABASE SETUP ---
def setup_database():
    """Creates the DB and Tables. Uses timeout=20 to prevent locking errors."""
    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pollution_log (
            timestamp TEXT,
            city TEXT,
            lat REAL,
            lon REAL,
            pm2_5 REAL,
            pm10 REAL
        )
    """)
    # Adding an index makes querying 26 regions extremely fast as data grows
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_city_time ON pollution_log(city, timestamp)"
    )
    conn.commit()
    conn.close()


# --- 3. CONCURRENT EXTRACTION ---
def fetch_single_region(region_data):
    """Hits the API for a single region."""
    city, coords = region_data
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={coords['lat']}&longitude={coords['lon']}&current=pm10,pm2_5"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            pm2_5 = current.get("pm2_5")
            pm10 = current.get("pm10")

            if pm2_5 is not None and pm10 is not None:
                return (city, coords["lat"], coords["lon"], pm2_5, pm10)
    except Exception as e:
        logging.error(f"Failed to fetch {city}: {e}")
    return None


def run_etl_pipeline():
    """Orchestrates the multithreaded fetching and bulk insertion."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid_records = []

    # Harvesters hitting the API simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_region, TANZANIA_REGIONS.items())

        for result in results:
            if result:
                valid_records.append((current_time,) + result)

    # Bulk insert to SQLite with timeout lock protection
    if valid_records:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO pollution_log (timestamp, city, lat, lon, pm2_5, pm10)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            valid_records,
        )
        conn.commit()
        conn.close()
        logging.info(f"ETL Cycle Complete. {len(valid_records)} regions secured in DB.")


# --- 4. LOCAL TESTING EXECUTION ---
if __name__ == "__main__":
    logging.info("🚀 Starting Local Tanzania Regional Air Quality Harvester...")
    setup_database()
    while True:
        run_etl_pipeline()
        time.sleep(60)
