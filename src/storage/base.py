from abc import ABC, abstractmethod
try:
    from ..data_models import RouteData # For application context
except ImportError:
    from data_models import RouteData # For standalone testing if needed
from typing import TypedDict, Union, List, Tuple
from typing_extensions import Unpack
from datetime import datetime

class DeleteParams(TypedDict, total=False):
    time: Union[datetime, List[datetime]]
    time_range: Tuple[datetime, datetime]
    id: Union[int, List[int]]

class DataStorage(ABC):

    @abstractmethod
    def save(self, route_data: RouteData) -> None:
        pass

    @abstractmethod
    def load(self, limit: int) -> list[dict]:
        pass

    @abstractmethod
    def delete(self, **kwargs: Unpack[DeleteParams]) -> None:
        pass

    def _time_round_minutes(self, time: datetime) -> datetime:
        return time.replace(second=0, microsecond=0)