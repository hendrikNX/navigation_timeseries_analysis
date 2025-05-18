from src import config
from src.route_fetcher import RouteFetcher
from src.storage.csv_storage import CsvStorage
from src.storage.sqlite_storage import SQLiteStorage
from src.scheduler import JobScheduler

def main_app():
    print("Starting Navigation Timeseries Analysis application...")

    # Initialize components
    route_fetcher = RouteFetcher() # API key is handled via config/env by RouteFetcher

    # Initialize and run the scheduler
    scheduler = JobScheduler(
        route_fetcher=route_fetcher,
        api_base_url=config.API_BASE_URL, # Use API_BASE_URL from config
        origin_coords=config.ORIGIN_COORDS,
        dest_coords=config.DEST_COORDS,
        frequency_per_hour=config.FETCH_FREQUENCY_PER_HOUR,
        start_time_route_to_dest=config.START_TIME_ROUTE_TO_DEST,
        end_time_route_to_dest=config.END_TIME_ROUTE_TO_DEST,
        start_time_route_to_origin=config.START_TIME_ROUTE_TO_ORIGIN,
        end_time_route_to_origin=config.END_TIME_ROUTE_TO_ORIGIN,
        weekdays=config.WEEKDAYS
    )

    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\nApplication shutting down gracefully...")
    except Exception as e:
        print(f"An critical unexpected error occurred: {e}")
    finally:
        print("Application stopped.")

if __name__ == "__main__":
    main_app()
