from src import config
from src.route_fetcher import RouteFetcher
from src.storage.csv_storage import CsvStorage
from src.scheduler import JobScheduler
from src.storage.base import DataStorage # For type hinting

def main_app():
    print("Starting Navigation Timeseries Analysis application...")

    # Initialize components
    route_fetcher = RouteFetcher() # API key is handled via config/env by RouteFetcher

    # Select storage backend based on configuration (Strategy Pattern)
    if config.STORAGE_TYPE == "csv":
        storage_backend = CsvStorage(file_path=config.CSV_FILE_PATH)
        print(f"Using CSV storage: {config.CSV_FILE_PATH}")
    else:
        raise ValueError(f"Unsupported storage type: {config.STORAGE_TYPE}. Choose 'csv' or 'sqlite'.")

    # Initialize and run the scheduler
    scheduler = JobScheduler(
        route_fetcher=route_fetcher,
        data_storage=storage_backend,
        origin_coords=config.ORIGIN_COORDS,
        dest_coords=config.DEST_COORDS,
        frequency_per_hour=config.FETCH_FREQUENCY_PER_HOUR
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
