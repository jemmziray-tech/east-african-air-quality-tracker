import requests
import sqlite3
import time
from datetime import datetime

# --- 1. CONFIGURATION ---
DB_FILE = "air_quality.db"

# Coordinates for our East African monitoring nodes
CITIES = {
    "Dar es Salaam": {"lat": -6.7924, "lon": 39.2083},
    "Nairobi": {"lat": -1.2921, "lon": 36.8219},
    "Kampala": {"lat": 0.3476, "lon": 32.5825},
    "Kigali": {"lat": -1.9441, "lon": 30.0619},
}


# --- 2. DATABASE SETUP (LOAD) ---
def setup_database():
    """Creates the permanent storage vault if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()


# --- 3. EXTRACT & TRANSFORM ---
def fetch_and_clean_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records_added = 0

    for city, coords in CITIES.items():
        # EXTRACT: Hit the API
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={coords['lat']}&longitude={coords['lon']}&current=pm10,pm2_5"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current_data = data.get("current", {})

                # TRANSFORM: Extract exact variables, handle missing data
                pm2_5 = current_data.get("pm2_5")
                pm10 = current_data.get("pm10")

                # Data Validation: Only log if sensors actually returned numbers
                if pm2_5 is not None and pm10 is not None:
                    # LOAD: Insert into database
                    cursor.execute(
                        """
                        INSERT INTO pollution_log (timestamp, city, lat, lon, pm2_5, pm10)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (current_time, city, coords["lat"], coords["lon"], pm2_5, pm10),
                    )
                    records_added += 1

        except Exception as e:
            print(f"[{current_time}] 🚨 Error fetching {city}: {e}")

    conn.commit()
    conn.close()
    print(
        f"[{current_time}] ETL Cycle Complete. {records_added} new records secured in SQLite."
    )


# --- 4. ORCHESTRATION ---
if __name__ == "__main__":
    print("🚀 Starting East Africa Air Quality Harvester...")
    setup_database()

    # Run the pipeline every 60 seconds forever
    while True:
        fetch_and_clean_data()
        time.sleep(60)
