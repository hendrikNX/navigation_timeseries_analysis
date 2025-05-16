import time
from datetime import datetime, timedelta
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
                 frequency_per_hour: int):
        self.route_fetcher = route_fetcher
        self.data_storage = data_storage
        self.origin_coords = origin_coords
        self.dest_coords = dest_coords
        if frequency_per_hour <= 0:
            raise ValueError("Frequency per hour must be a positive integer.")
        self.frequency_per_hour = frequency_per_hour
        # Calculate interval in seconds. 3600 seconds in an hour.
        self.interval_seconds = 3600 // frequency_per_hour # Use integer division

    def run(self):
        print(f"Scheduler started. Fetching data {self.frequency_per_hour} times per hour for route {self.origin_coords} -> {self.dest_coords}.")
        
        # Calculate the target minutes within the hour
        scheduled_minutes = sorted([(i * 60) // self.frequency_per_hour for i in range(self.frequency_per_hour)])
        print(f"Scheduled minutes within the hour: {scheduled_minutes}")

        while True:
            now = datetime.now(tz=pytz.timezone("Europe/Berlin"))

            # Determine the next scheduled time
            next_scheduled_time = None
            # Start checking from the current hour, at the beginning of the hour
            current_hour_dt = now.replace(minute=0, second=0, microsecond=0)

            # Find the first scheduled minute that is in the future relative to 'now'
            for target_minute in scheduled_minutes:
                scheduled_dt = current_hour_dt.replace(minute=target_minute)
                if scheduled_dt > now:
                    next_scheduled_time = scheduled_dt
                    break # Found the next scheduled time in the current hour

            # If no scheduled time found in the current hour (i.e., 'now' is past the last scheduled minute),
            # the next scheduled time is the first minute (0) of the next hour.
            if next_scheduled_time is None:
                next_scheduled_time = (current_hour_dt + timedelta(hours=1)).replace(minute=0)

            # Calculate time until the next run
            time_until_next_run = next_scheduled_time - now
            sleep_seconds = time_until_next_run.total_seconds()

            # If sleep_seconds is positive, wait. Otherwise, fetch immediately (we are past the scheduled time).
            if sleep_seconds > 0:
                print(f"[{now.isoformat()}] Waiting until {next_scheduled_time.isoformat()} ({sleep_seconds:.2f} seconds)...")
                time.sleep(sleep_seconds)

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