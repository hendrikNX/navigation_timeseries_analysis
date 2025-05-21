import sqlite3
import os
from datetime import datetime, timedelta

from .base import DataStorage, DeleteParams
try:
    from ..data_models import RouteData
except ImportError:
    from data_models import RouteData # For standalone testing if needed
from typing_extensions import Unpack
from typing import TypedDict, Union, List, Tuple

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

    def load(self, limit: int) -> list[RouteData]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM route_times ORDER BY start_time DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        route_data_list: list[RouteData] = []
        for row in rows:
            row_dict = dict(row) # Convert sqlite3.Row to a standard dictionary
            try:
                start_time_dt = datetime.fromisoformat(row_dict['start_time'])
                route_data_obj = RouteData(
                    origin_lat=row_dict['origin_lat'],
                    origin_lon=row_dict['origin_lon'],
                    dest_lat=row_dict['dest_lat'],
                    dest_lon=row_dict['dest_lon'],
                    distance_m=row_dict['distance_m'],
                    duration_s=row_dict['duration_s'],
                    duration_in_traffic_s=row_dict['duration_in_traffic_s'],
                    start_time=start_time_dt
                    # Note: 'id' from the database is not part of RouteData model
                )
                route_data_list.append(route_data_obj)
            except (ValueError, KeyError, TypeError) as e:
                print(f"Skipping row due to parsing or instantiation error: {row_dict}, error: {e}")
                continue
        return route_data_list
    
    def delete(self, **kwargs: Unpack[DeleteParams]):
        if not kwargs or len(kwargs) > 1:
            raise ValueError("Deletion requires exactly one condition.")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query_conditions = []
        params = []

        if 'time' in kwargs:
            time_param = kwargs['time']
            if isinstance(time_param, list):
                times_list = [self._time_round_minutes(t) for t in time_param]
                print(f"Processing deletion based on timestamp(s): {[t.strftime('%Y-%m-%d %H:%M') for t in times_list]}")
                for t_rounded in times_list:
                    query_conditions.append("(start_time >= ? AND start_time < ?)")
                    params.extend([t_rounded.isoformat(), (t_rounded + timedelta(minutes=1)).isoformat()])
            else:
                t_rounded = self._time_round_minutes(time_param)
                print(f"Processing deletion based on timestamp: {t_rounded.strftime('%Y-%m-%d %H:%M')}")
                query_conditions.append("(start_time >= ? AND start_time < ?)")
                params.extend([t_rounded.isoformat(), (t_rounded + timedelta(minutes=1)).isoformat()])
        
        elif 'time_range' in kwargs:
            time_range_param = kwargs['time_range']
            if not (isinstance(time_range_param, tuple) and len(time_range_param) == 2 and
                    isinstance(time_range_param[0], datetime) and isinstance(time_range_param[1], datetime)):
                raise ValueError("time_range must be a tuple of two datetime objects.")
            if time_range_param[0] >= time_range_param[1]:
                raise ValueError("Start of time_range must be before end of time_range.")

            start_time_rounded = self._time_round_minutes(time_range_param[0])
            end_time_rounded = self._time_round_minutes(time_range_param[1])
            print(f"Processing deletion based on timestamp range: {start_time_rounded.isoformat()} to {end_time_rounded.isoformat()}")
            query_conditions.append("(start_time >= ? AND start_time < ?)")
            params.extend([start_time_rounded.isoformat(), end_time_rounded.isoformat()])

        elif 'id' in kwargs:
            id_param = kwargs['id']
            if isinstance(id_param, list):
                if not id_param: # Handle empty list case
                    print("Processing deletion based on id list: No IDs provided, no rows will be deleted.")
                    # Effectively a no-op, or raise error if empty list is invalid
                    query_conditions.append("1=0") # Condition that is always false
                else:
                    print(f"Processing deletion based on id list: {id_param}")
                    placeholders = ', '.join(['?'] * len(id_param))
                    query_conditions.append(f"id IN ({placeholders})")
                    params.extend(id_param)
            else:
                print(f"Processing deletion based on id: {id_param}")
                query_conditions.append("id = ?")
                params.append(id_param)

        sql = f"DELETE FROM route_times WHERE {' OR '.join(query_conditions)}"
        cursor.execute(sql, params)
        conn.commit()
        conn.close()
        print(f"Deleted {cursor.rowcount} rows from SQLite DB based on criteria: {kwargs} using query: {sql} with params: {params}")