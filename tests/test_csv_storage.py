import pytest
import os
import csv
from datetime import datetime
import pytz
from pathlib import Path

from src.storage.csv_storage import CsvStorage
from src.data_models import RouteData

@pytest.fixture
def sample_route_data_1() -> RouteData:
    """Provides a sample RouteData object."""
    return RouteData(
        origin_lat=48.0,
        origin_lon=9.0,
        dest_lat=48.1,
        dest_lon=9.1,
        distance_m=10000,
        duration_s=600,
        duration_in_traffic_s=650,
        start_time=datetime(2023, 10, 27, 10, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    )

@pytest.fixture
def sample_route_data_2() -> RouteData:
    """Provides another sample RouteData object."""
    return RouteData(
        origin_lat=48.2,
        origin_lon=9.2,
        dest_lat=48.3,
        dest_lon=9.3,
        distance_m=12000,
        duration_s=700,
        duration_in_traffic_s=750,
        start_time=datetime(2023, 10, 27, 10, 15, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    )

@pytest.fixture
def csv_file_path(tmp_path: Path) -> str:
    """Provides a path to a temporary CSV file."""
    return str(tmp_path / "test_routes.csv")

def test_csv_storage_initialization_creates_file_with_header(csv_file_path: str, sample_route_data_1: RouteData):
    """Tests that a new CSV file is created with the correct header if it doesn't exist."""
    assert not os.path.exists(csv_file_path)

    _ = CsvStorage(file_path=csv_file_path)

    assert os.path.exists(csv_file_path)
    with open(csv_file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == sample_route_data_1.get_field_names()
        # Check if there are any more rows (should be only header)
        with pytest.raises(StopIteration):
            next(reader)

def test_csv_storage_initialization_empty_file_adds_header(csv_file_path: str, sample_route_data_1: RouteData):
    """Tests that if an empty CSV file exists, a header is added."""
    # Create an empty file
    open(csv_file_path, 'w').close()
    assert os.path.exists(csv_file_path)
    assert os.path.getsize(csv_file_path) == 0

    _ = CsvStorage(file_path=csv_file_path)

    with open(csv_file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == sample_route_data_1.get_field_names()

def test_csv_storage_save_single_route_data(csv_file_path: str, sample_route_data_1: RouteData):
    """Tests saving a single RouteData object to the CSV."""
    storage = CsvStorage(file_path=csv_file_path)
    storage.save(sample_route_data_1)

    with open(csv_file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader) # Skip header
        data_row = next(reader)

        assert data_row[0] == str(sample_route_data_1.origin_lat)
        assert data_row[1] == str(sample_route_data_1.origin_lon)
        assert data_row[4] == str(sample_route_data_1.distance_m)
        assert data_row[5] == str(sample_route_data_1.duration_s)
        assert data_row[6] == str(sample_route_data_1.duration_in_traffic_s)
        assert data_row[7] == sample_route_data_1.start_time.isoformat()

def test_csv_storage_save_multiple_route_data(csv_file_path: str, sample_route_data_1: RouteData, sample_route_data_2: RouteData):
    """Tests saving multiple RouteData objects, ensuring they are appended."""
    storage = CsvStorage(file_path=csv_file_path)
    storage.save(sample_route_data_1)
    storage.save(sample_route_data_2)

    with open(csv_file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        _ = next(reader) # Skip header
        row1 = next(reader)
        row2 = next(reader)

        assert row1[7] == sample_route_data_1.start_time.isoformat()
        assert row2[7] == sample_route_data_2.start_time.isoformat()
        assert row2[4] == str(sample_route_data_2.distance_m)

        # Ensure no more rows
        with pytest.raises(StopIteration):
            next(reader)