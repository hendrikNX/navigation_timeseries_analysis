from dataclasses import dataclass, fields
from datetime import datetime
from typing import List

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

    def get_field_names(self) -> List[str]:
        return [field.name for field in fields(self)]