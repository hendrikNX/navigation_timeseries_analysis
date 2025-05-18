import csv
import os
from dataclasses import astuple
from datetime import datetime, timezone

from .base import DataStorage
try:
    from ..data_models import RouteData # For application context
except ImportError:
    from data_models import RouteData # For standalone testing if needed

class CsvStorage(DataStorage):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._initialize_csv()

    def _initialize_csv(self):
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            # Create dummy RouteData instance to get headers in correct order
            header = RouteData(0,0,0,0,0,0,0,datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)).get_field_names() # type: ignore
            with open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)

    def save(self, route_data: RouteData) -> None:
        # Convert datetime to ISO format string for consistent CSV storage
        data_tuple = list(astuple(route_data))
        data_tuple[-1] = route_data.start_time.isoformat() # Assuming start_time is the last field

        with open(self.file_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(data_tuple)
        print(f"Data saved to CSV: {self.file_path}")

    def load(self, limit: int) -> list[dict]:
        records = []
        if not os.path.exists(self.file_path):
            return []

        with open(self.file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric types from string
                try:
                    row['origin_lat'] = float(row['origin_lat'])
                    row['origin_lon'] = float(row['origin_lon'])
                    row['dest_lat'] = float(row['dest_lat'])
                    row['dest_lon'] = float(row['dest_lon'])
                    row['distance_m'] = int(row['distance_m'])
                    row['duration_s'] = int(row['duration_s'])
                    row['duration_in_traffic_s'] = int(row['duration_in_traffic_s'])
                    # 'start_time' is already an ISO string, which is fine for JSON output
                except (ValueError, KeyError) as e:
                    print(f"Skipping row due to parsing error: {row}, error: {e}")
                    continue
                records.append(row)
        
        # Sort by start_time descending (most recent first)
        records.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return records[:limit]