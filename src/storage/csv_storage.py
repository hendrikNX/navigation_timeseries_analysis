import csv
import os
from dataclasses import astuple
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
            header = RouteData(0,0,0,0,0,0,0,None).get_field_names() # type: ignore
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