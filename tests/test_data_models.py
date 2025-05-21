from datetime import datetime, timedelta
import pytz
import pandas as pd

# Assuming the project structure places src/data_models.py relative to tests/
# Adjust the import path if your structure is different
from src.data_models import RouteData, route_data_list_to_dataframe

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
        duration_in_traffic_s=650,
        start_time=now
    )

    assert data.origin_lat == 48.0
    assert data.duration_s == 600
    assert data.duration_in_traffic_s == 650
    assert data.start_time == now
    assert isinstance(data, RouteData)

def test_route_data_get_field_names():
    """Tests if get_field_names returns the correct list of attribute names."""
    expected_fields = [
        "origin_lat", "origin_lon", "dest_lat", "dest_lon",
        "distance_m", "duration_s", "duration_in_traffic_s", "start_time"
    ]
    # Create a dummy instance just to call the method
    dummy_data = RouteData(0, 0, 0, 0, 0, 0, 0, datetime.now(tz=pytz.timezone("UTC")))
    assert dummy_data.get_field_names() == expected_fields

def test_route_data_list_to_dataframe():
    """Tests conversion of a list of RouteData objects to a sorted pandas DataFrame."""
    tz = pytz.timezone("Europe/Berlin")
    time1 = datetime(2023, 1, 1, 10, 0, 0, tzinfo=tz)
    time2 = datetime(2023, 1, 1, 9, 0, 0, tzinfo=tz) # Earlier time
    time3 = datetime(2023, 1, 1, 11, 0, 0, tzinfo=tz) # Later time

    data_list = [
        RouteData(1.0, 1.0, 1.1, 1.1, 100, 10, 11, time1),
        RouteData(2.0, 2.0, 2.1, 2.1, 200, 20, 22, time2),
        RouteData(3.0, 3.0, 3.1, 3.1, 300, 30, 33, time3),
    ]

    df = route_data_list_to_dataframe(data_list)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns) == RouteData.get_field_names(data_list[0])

    comparison_start_time_0 = (df.iloc[0]['start_time'] == time2)
    assert comparison_start_time_0.all() if isinstance(comparison_start_time_0, pd.Series) else comparison_start_time_0
    comparison_distance_0 = (df.iloc[0]['distance_m'] == 200)
    assert comparison_distance_0.all() if isinstance(comparison_distance_0, pd.Series) else comparison_distance_0

    comparison_start_time_1 = (df.iloc[1]['start_time'] == time1)
    assert comparison_start_time_1.all() if isinstance(comparison_start_time_1, pd.Series) else comparison_start_time_1
    comparison_distance_1 = (df.iloc[1]['distance_m'] == 100)
    assert comparison_distance_1.all() if isinstance(comparison_distance_1, pd.Series) else comparison_distance_1

    comparison_start_time_2 = (df.iloc[2]['start_time'] == time3)
    assert comparison_start_time_2.all() if isinstance(comparison_start_time_2, pd.Series) else comparison_start_time_2
    comparison_distance_2 = (df.iloc[2]['distance_m'] == 300)
    assert comparison_distance_2.all() if isinstance(comparison_distance_2, pd.Series) else comparison_distance_2

    # Test with an empty list
    empty_df = route_data_list_to_dataframe([])
    assert isinstance(empty_df, pd.DataFrame)
    assert len(empty_df) == 0
    # Check if columns are correctly set for an empty DataFrame
    dummy_data = RouteData(0,0,0,0,0,0,0, datetime.now(tz=pytz.timezone("UTC")))
    assert list(empty_df.columns) == dummy_data.get_field_names()

    # Test with a single item list
    single_item_list = [RouteData(4.0, 4.0, 4.1, 4.1, 400, 40, 44, time1)]
    single_df = route_data_list_to_dataframe(single_item_list)
    assert isinstance(single_df, pd.DataFrame)
    assert len(single_df) == 1
    comparison_single_distance = (single_df.iloc[0]['distance_m'] == 400)
    assert comparison_single_distance.all() if isinstance(comparison_single_distance, pd.Series) else comparison_single_distance
    comparison_single_start_time = (single_df.iloc[0]['start_time'] == time1)
    assert comparison_single_start_time.all() if isinstance(comparison_single_start_time, pd.Series) else comparison_single_start_time