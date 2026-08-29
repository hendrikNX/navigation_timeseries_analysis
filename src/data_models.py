from dataclasses import dataclass, fields, asdict
from datetime import datetime
from typing import List
import pandas as pd

@dataclass
class RouteData:
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    distance_m: int
    duration_s: int
    duration_in_traffic_s: int
    start_time: datetime # Should be timezone-aware

    def __post_init__(self):
        if not isinstance(self.start_time, datetime):
            raise TypeError(f"start_time must be a datetime object, but got {type(self.start_time)}.")
        if self.start_time.tzinfo is None or self.start_time.tzinfo.utcoffset(self.start_time) is None:
            raise ValueError("start_time must be timezone-aware.")        

    @classmethod
    def get_static_field_names(cls) -> List[str]:
        """Returns the field names of the dataclass as a class method."""
        return [field.name for field in fields(cls)]

    def get_field_names(self) -> List[str]:
        return self.get_static_field_names()

def route_data_list_to_dataframe(data_list: List[RouteData]) -> pd.DataFrame:
    """
    Converts a list of RouteData objects into a pandas DataFrame,
    sorted by start_time in ascending order.

    Args:
        data_list: A list of RouteData objects.

    Returns:
        A pandas DataFrame with the data, sorted by 'start_time'.
    """
    if not data_list:
        # Return an empty DataFrame with correct columns if the list is empty
        return pd.DataFrame(columns=RouteData.get_static_field_names())

    # Convert list of dataclass objects to DataFrame
    df = pd.DataFrame([asdict(data_item) for data_item in data_list])
    df['start_time'] = pd.to_datetime(df['start_time']) # Ensure start_time is datetime type
    df = df.sort_values(by='start_time', ascending=True).reset_index(drop=True)
    return df
