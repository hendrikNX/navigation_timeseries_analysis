from datetime import datetime
import pytz

# Assuming the project structure places src/data_models.py relative to tests/
# Adjust the import path if your structure is different
from src.data_models import RouteData

def test_route_data_creation():
    """Tests if a RouteData object can be created correctly."""
    now = datetime.now(tz=pytz.timezone("Europe/Berlin"))
    data = RouteData(
        origin_lat=48.0,
        origin_lon=9.0,
        dest_lat=48.1,
        dest_lon=9.1,
        distance_m=10000,
        duration_s=600,
        start_time=now
    )

    assert data.origin_lat == 48.0
    assert data.duration_s == 600
    assert data.start_time == now
    assert isinstance(data, RouteData)

def test_route_data_get_field_names():
    """Tests if get_field_names returns the correct list of attribute names."""
    expected_fields = [
        "origin_lat", "origin_lon", "dest_lat", "dest_lon",
        "distance_m", "duration_s", "start_time"
    ]
    # Create a dummy instance just to call the method
    dummy_data = RouteData(0, 0, 0, 0, 0, 0, datetime.now(tz=pytz.timezone("UTC")))
    assert dummy_data.get_field_names() == expected_fields