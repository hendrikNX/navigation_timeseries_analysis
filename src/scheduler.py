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
                 frequency_per_hour: int,
                 start_time_route_to_dest: int,
                 end_time_route_to_dest: int,
                 start_time_route_to_origin: int,
                 end_time_route_to_origin: int,
                 weekdays: list[int]):
        self.route_fetcher = route_fetcher
        self.data_storage = data_storage
        self.origin_coords = origin_coords
        self.dest_coords = dest_coords
        self.weekdays = weekdays

        if not 0 <= start_time_route_to_dest <= 24:
            raise ValueError("Invalid start_time_route_to_dest. Must be between 0 and 24.")
        if not 0 <= end_time_route_to_dest <= 24:
            raise ValueError("Invalid end_time_route_to_dest. Must be between 0 and 24.")
        if not 0 <= start_time_route_to_origin <= 24:
            raise ValueError("Invalid start_time_route_to_origin. Must be between 0 and 24.")
        if not 0 <= end_time_route_to_origin <= 24:
            raise ValueError("Invalid end_time_route_to_origin. Must be between 0 and 24.")

        if not start_time_route_to_dest < end_time_route_to_dest:
            raise ValueError("start_time_route_to_dest must be less than end_time_route_to_dest.")
        if not start_time_route_to_origin < end_time_route_to_origin:
            raise ValueError("start_time_route_to_origin must be less than end_time_route_to_origin.")

        self.hour_range_to_dest = (start_time_route_to_dest, end_time_route_to_dest)
        self.hour_range_to_origin = (start_time_route_to_origin, end_time_route_to_origin)

        if frequency_per_hour <= 0:
            raise ValueError("Frequency per hour must be a positive integer.")
        self.frequency_per_hour = frequency_per_hour
        # Calculate interval in seconds. 3600 seconds in an hour.
        self.interval_seconds = 3600 // frequency_per_hour # Use integer division

    def run(self):
        print(f"Scheduler started. Fetching data {self.frequency_per_hour} times per hour for routes between {self.origin_coords} & {self.dest_coords} on days {self.weekdays}.")
        
        # Calculate the target minutes within the hour
        scheduled_minutes = [(i * 60) // self.frequency_per_hour for i in range(self.frequency_per_hour)]
        print(f"Scheduled minutes within each hour: {scheduled_minutes}")

        while True:
            now = datetime.now(tz=pytz.timezone("Europe/Berlin"))

            next_fetch_time = self.get_next_fetch_time(now)

            time_until_next_run = next_fetch_time - now
            sleep_seconds = time_until_next_run.total_seconds()

            print(f"[{now.isoformat()}] Waiting until {next_fetch_time.strftime('%Y-%m-%d %H:%M:%S')} ({sleep_seconds:.2f} seconds)...")
            time.sleep(sleep_seconds)

            current_time = datetime.now(tz=pytz.timezone("Europe/Berlin"))
            current_time_str = current_time.isoformat()
            print(f"[{current_time_str}] Fetching route data...")
            try:
                route_data = None
                if current_time.hour in range(*self.hour_range_to_dest):
                    route_data = self.route_fetcher.get_current_route_data(
                        origin_cords=self.origin_coords,
                        dest_cords=self.dest_coords
                    )
                elif current_time.hour in range(*self.hour_range_to_origin):
                    route_data = self.route_fetcher.get_current_route_data(
                        origin_cords=self.dest_coords,
                        dest_cords=self.origin_coords  
                    )
                if route_data:
                    self.data_storage.save(route_data)
                    print(f"[{current_time_str}] Data processed and saved.")
                else:
                    print(f"[{current_time_str}] No data fetched or an error occurred during fetch.")
            except Exception as e:
                print(f"[{current_time_str}] An error occurred in the scheduler loop: {e}")

    def get_next_fetch_time(self, now: datetime):
        next_fetch_time = None
        reference_time = now.replace(minute=0, second=0, microsecond=0)

        while not next_fetch_time:
            if reference_time > now:
                if reference_time.weekday() in self.weekdays:
                    if self.hour_range_to_dest[0] <= reference_time.hour < self.hour_range_to_dest[1]:
                        next_fetch_time = reference_time
                    elif self.hour_range_to_origin[0] <= reference_time.hour < self.hour_range_to_origin[1]:
                        next_fetch_time = reference_time
            reference_time += timedelta(seconds=self.interval_seconds)

        return next_fetch_time