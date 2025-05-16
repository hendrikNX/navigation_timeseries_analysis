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
    start_time: datetime # Should be timezone-aware

    def get_field_names(self) -> List[str]:
        return [field.name for field in fields(self)]