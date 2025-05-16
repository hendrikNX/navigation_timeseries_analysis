import time
from datetime import datetime
import pytz
from typing import Tuple

try:
    from .route_fetcher import RouteFetcher
    from .storage.base import DataStorage
except ImportError: # Fallback for potential direct execution or different project structures
    from route_fetcher import RouteFetcher
    from storage.base import DataStorage

class JobScheduler:
    def __init__(self,
                 route_fetcher: RouteFetcher,
                 data_storage: DataStorage,
                 origin_coords: Tuple[float, float],
                 dest_coords: Tuple[float, float],
                 interval_seconds: int):
        self.route_fetcher = route_fetcher
        self.data_storage = data_storage
        self.origin_coords = origin_coords
        self.dest_coords = dest_coords
        self.interval_seconds = interval_seconds

    def run(self):
        print(f"Scheduler started. Fetching data every {self.interval_seconds} seconds for route {self.origin_coords} -> {self.dest_coords}.")
        while True:
            current_time_str = datetime.now(tz=pytz.timezone("Europe/Berlin")).isoformat()
            print(f"[{current_time_str}] Fetching route data...")
            try:
                route_data = self.route_fetcher.get_current_route_data(
                    origin_cords=self.origin_coords,
                    dest_cords=self.dest_coords
                )
                if route_data:
                    self.data_storage.save(route_data)
                    print(f"[{current_time_str}] Data processed and saved.")
                else:
                    print(f"[{current_time_str}] No data fetched or an error occurred during fetch.")
            except Exception as e:
                print(f"[{current_time_str}] An error occurred in the scheduler loop: {e}")
            print(f"Waiting for {self.interval_seconds} seconds until next fetch...")
            time.sleep(self.interval_seconds)