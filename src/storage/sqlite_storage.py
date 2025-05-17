import sqlite3
import os
from datetime import datetime

from .base import DataStorage
try:
    from ..data_models import RouteData
except ImportError:
    from data_models import RouteData # For standalone testing if needed

class SQLiteStorage(DataStorage):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """
        Initializes the database and creates the 'route_times' table if it doesn't exist.
        Ensures the directory for the database file exists.
        """
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created directory for SQLite database: {db_dir}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # The table schema matches the fields in RouteData
        # start_time will be stored as TEXT in ISO 8601 format
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS route_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin_lat REAL NOT NULL,
                origin_lon REAL NOT NULL,
                dest_lat REAL NOT NULL,
                dest_lon REAL NOT NULL,
                distance_m INTEGER NOT NULL,
                duration_s INTEGER NOT NULL,
                duration_in_traffic_s INTEGER NOT NULL,
                start_time TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def save(self, route_data: RouteData) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Ensure start_time is in ISO format string
        start_time_iso = route_data.start_time.isoformat()

        data_to_insert = (
            route_data.origin_lat,
            route_data.origin_lon,
            route_data.dest_lat,
            route_data.dest_lon,
            route_data.distance_m,
            route_data.duration_s,
            route_data.duration_in_traffic_s,
            start_time_iso
        )

        cursor.execute('''
            INSERT INTO route_times (
                origin_lat, origin_lon, dest_lat, dest_lon,
                distance_m, duration_s, duration_in_traffic_s, start_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)

        conn.commit()
        conn.close()
        print(f"Data saved to SQLite DB: {self.db_path}, Row ID: {cursor.lastrowid}")