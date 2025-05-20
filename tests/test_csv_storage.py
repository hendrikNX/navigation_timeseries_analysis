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

@pytest.fixture
def base_sample_route_data() -> RouteData:
    """Provides a base RouteData object for modification in tests, similar to SQLite tests."""
    return RouteData(
        origin_lat=52.5200,
        origin_lon=13.4050,
        dest_lat=48.8566,
        dest_lon=2.3522,
        distance_m=1050000,
        duration_s=36000,
        duration_in_traffic_s=37800,
        start_time=datetime(2023, 10, 26, 12, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    )

@pytest.fixture
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

# Helper functions for CSV tests
def _read_all_csv_rows(file_path: str) -> list[dict]:
    """Reads all data rows from CSV as list of dicts, excluding header."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return []
    rows = []
    try:
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Perform type conversions similar to CsvStorage.load()
                try:
                    row['origin_lat'] = float(row['origin_lat'])
                    row['origin_lon'] = float(row['origin_lon'])
                    row['dest_lat'] = float(row['dest_lat'])
                    row['dest_lon'] = float(row['dest_lon'])
                    row['distance_m'] = int(row['distance_m'])
                    row['duration_s'] = int(row['duration_s'])
                    row['duration_in_traffic_s'] = int(row['duration_in_traffic_s'])
                    # start_time remains an ISO string
                except (ValueError, KeyError) as e:
                    print(f"Skipping row in test helper due to parsing error: {row}, error: {e}")
                    continue # Or handle as per test needs
                rows.append(row)
    except FileNotFoundError:
        return []
    return rows

def _get_csv_row_count(file_path: str) -> int:
    """Counts data rows in CSV, excluding header."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 0
    try:
        with open(file_path, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None: return 0 # Empty file or only header with no newline
            count = sum(1 for row in reader if any(field.strip() for field in row)) # Count non-empty rows
        return count
    except FileNotFoundError:
        return 0

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

def test_csv_load_data_empty_csv(csv_file_path: str):
    storage = CsvStorage(file_path=csv_file_path) # Initializes with header
    loaded_data = storage.load(limit=10)
    assert len(loaded_data) == 0, "Should return an empty list from an empty (header-only) CSV."

def test_csv_load_data_with_limit(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    time_now = datetime(2023, 10, 26, 12, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    
    # Create copies for modification
    from copy import deepcopy
    from datetime import timedelta

    data1_dict = base_sample_route_data.__dict__.copy()
    data1_dict["start_time"] = time_now
    data1_dict["distance_m"] = 100
    data1 = RouteData(**data1_dict)

    data2_dict = base_sample_route_data.__dict__.copy()
    data2_dict["start_time"] = time_now - timedelta(hours=1)
    data2_dict["distance_m"] = 200
    data2 = RouteData(**data2_dict)

    data3_dict = base_sample_route_data.__dict__.copy()
    data3_dict["start_time"] = time_now - timedelta(hours=2)
    data3_dict["distance_m"] = 300
    data3 = RouteData(**data3_dict)

    storage.save(data1)
    storage.save(data2)
    storage.save(data3)

    loaded_data = storage.load(limit=2)
    assert len(loaded_data) == 2, "Should load exactly 2 records."

    loaded_distances = [d['distance_m'] for d in loaded_data]
    assert 100 in loaded_distances, "Data1 should be loaded."
    assert 200 in loaded_distances, "Data2 should be loaded."
    assert 300 not in loaded_distances, "Data3 should not be loaded due to limit."

def test_csv_load_data_order_and_structure(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    time_now = datetime(2023, 10, 26, 12, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    from datetime import timedelta

    # Create copies for modification
    data_recent_dict = base_sample_route_data.__dict__.copy()
    data_recent_dict["start_time"] = time_now
    data_recent_dict["distance_m"] = 1
    route_data_recent = RouteData(**data_recent_dict)

    data_older_dict = base_sample_route_data.__dict__.copy()
    data_older_dict["start_time"] = time_now - timedelta(minutes=10)
    data_older_dict["distance_m"] = 2
    route_data_older = RouteData(**data_older_dict)

    data_oldest_dict = base_sample_route_data.__dict__.copy()
    data_oldest_dict["start_time"] = time_now - timedelta(minutes=20)
    data_oldest_dict["distance_m"] = 3
    route_data_oldest = RouteData(**data_oldest_dict)

    storage.save(route_data_older) # Save out of order
    storage.save(route_data_oldest)
    storage.save(route_data_recent)

    loaded_data = storage.load(limit=3)
    assert len(loaded_data) == 3, "Should load all 3 records."

    assert loaded_data[0]['distance_m'] == route_data_recent.distance_m
    assert loaded_data[1]['distance_m'] == route_data_older.distance_m
    assert loaded_data[2]['distance_m'] == route_data_oldest.distance_m

    first_item = loaded_data[0]
    assert isinstance(first_item, dict)
    assert first_item['origin_lat'] == route_data_recent.origin_lat
    assert first_item['start_time'] == route_data_recent.start_time.isoformat()

def test_csv_delete_by_single_id(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    from copy import deepcopy
    data1 = deepcopy(base_sample_route_data)
    data1.distance_m = 101
    data2 = deepcopy(base_sample_route_data)
    data2.distance_m = 102
    storage.save(data1) # Row 1
    storage.save(data2) # Row 2

    storage.delete(id=1) # Delete first data row
    assert _get_csv_row_count(csv_file_path) == 1
    remaining_records = _read_all_csv_rows(csv_file_path)
    assert remaining_records[0]['distance_m'] == 102

def test_csv_delete_by_list_of_ids(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    from copy import deepcopy
    from datetime import timedelta
    
    # Create distinct data
    data1_dict = base_sample_route_data.__dict__.copy(); data1_dict.update({"distance_m": 201, "start_time": base_sample_route_data.start_time + timedelta(hours=1)}); data1 = RouteData(**data1_dict)
    data2_dict = base_sample_route_data.__dict__.copy(); data2_dict.update({"distance_m": 202, "start_time": base_sample_route_data.start_time + timedelta(hours=2)}); data2 = RouteData(**data2_dict)
    data3_dict = base_sample_route_data.__dict__.copy(); data3_dict.update({"distance_m": 203, "start_time": base_sample_route_data.start_time + timedelta(hours=3)}); data3 = RouteData(**data3_dict)

    storage.save(data1) # Row 1
    storage.save(data2) # Row 2
    storage.save(data3) # Row 3

    storage.delete(id=[1, 3])
    assert _get_csv_row_count(csv_file_path) == 1
    remaining_records = _read_all_csv_rows(csv_file_path)
    assert remaining_records[0]['distance_m'] == 202

    storage.delete(id=[]) # Empty list
    assert _get_csv_row_count(csv_file_path) == 1

    storage.delete(id=[99, 100]) # Non-existent IDs
    assert _get_csv_row_count(csv_file_path) == 1

def test_csv_delete_by_single_time(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    from datetime import timedelta
    time_base = datetime(2023, 10, 27, 10, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))

    data_t1_s0_dict = base_sample_route_data.__dict__.copy(); data_t1_s0_dict.update({"start_time": time_base, "distance_m": 301}); data_t1_s0 = RouteData(**data_t1_s0_dict)
    data_t1_s30_dict = base_sample_route_data.__dict__.copy(); data_t1_s30_dict.update({"start_time": time_base + timedelta(seconds=30), "distance_m": 302}); data_t1_s30 = RouteData(**data_t1_s30_dict)
    data_t2_dict = base_sample_route_data.__dict__.copy(); data_t2_dict.update({"start_time": time_base + timedelta(minutes=5), "distance_m": 303}); data_t2 = RouteData(**data_t2_dict)

    storage.save(data_t1_s0)
    storage.save(data_t1_s30)
    storage.save(data_t2)

    storage.delete(time=time_base) # Deletes records from 10:00:00 to 10:00:59
    assert _get_csv_row_count(csv_file_path) == 1
    remaining_records = _read_all_csv_rows(csv_file_path)
    assert remaining_records[0]['distance_m'] == 303

def test_csv_delete_by_time_range(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    from datetime import timedelta
    tz = pytz.timezone("Europe/Berlin")
    t_start_range = datetime(2023, 10, 27, 14, 0, 0, tzinfo=tz)
    t_end_range = datetime(2023, 10, 27, 15, 0, 0, tzinfo=tz) # Exclusive end

    # Create data points
    data_before_dict = base_sample_route_data.__dict__.copy(); data_before_dict.update({"start_time": t_start_range - timedelta(minutes=1), "distance_m": 501}); data_before = RouteData(**data_before_dict)
    data_in_dict = base_sample_route_data.__dict__.copy(); data_in_dict.update({"start_time": t_start_range + timedelta(minutes=30), "distance_m": 502}); data_in = RouteData(**data_in_dict)
    data_after_dict = base_sample_route_data.__dict__.copy(); data_after_dict.update({"start_time": t_end_range + timedelta(minutes=1), "distance_m": 503}); data_after = RouteData(**data_after_dict)

    storage.save(data_before)
    storage.save(data_in)
    storage.save(data_after)

    storage.delete(time_range=(t_start_range, t_end_range))
    assert _get_csv_row_count(csv_file_path) == 2
    remaining_distances = {r['distance_m'] for r in _read_all_csv_rows(csv_file_path)}
    assert 501 in remaining_distances
    assert 503 in remaining_distances
    assert 502 not in remaining_distances

def test_csv_delete_invalid_parameters(csv_file_path: str):
    storage = CsvStorage(file_path=csv_file_path)
    with pytest.raises(ValueError, match="Deletion requires exactly one condition."):
        storage.delete()
    with pytest.raises(ValueError, match="Deletion requires exactly one condition."):
        storage.delete(id=1, time=datetime.now(pytz.utc)) # type: ignore
    with pytest.raises(ValueError, match="time_range must be a tuple of two datetime objects."):
        storage.delete(time_range=(datetime.now(pytz.utc), "not-a-datetime")) # type: ignore
    with pytest.raises(ValueError, match="Start of time_range must be before end of time_range."):
        now = datetime.now(pytz.utc)
        from datetime import timedelta
        storage.delete(time_range=(now, now - timedelta(hours=1)))

def test_csv_delete_non_existent_data(csv_file_path: str, base_sample_route_data: RouteData):
    storage = CsvStorage(file_path=csv_file_path)
    from copy import deepcopy
    from datetime import timedelta
    data1 = deepcopy(base_sample_route_data)
    data1.distance_m = 601
    storage.save(data1)
    initial_count = _get_csv_row_count(csv_file_path)
    assert initial_count == 1

    storage.delete(id=999)
    assert _get_csv_row_count(csv_file_path) == initial_count

    non_existent_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
    storage.delete(time=non_existent_time)
    assert _get_csv_row_count(csv_file_path) == initial_count

    non_existent_range_start = datetime(2001, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
    non_existent_range_end = datetime(2001, 1, 1, 1, 0, 0, tzinfo=pytz.utc)
    storage.delete(time_range=(non_existent_range_start, non_existent_range_end))
    assert _get_csv_row_count(csv_file_path) == initial_count