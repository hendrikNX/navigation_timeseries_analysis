from abc import ABC, abstractmethod
try:
    from ..data_models import RouteData # For application context
except ImportError:
    from data_models import RouteData # For standalone testing if needed

class DataStorage(ABC):
    @abstractmethod
    def save(self, route_data: RouteData) -> None:
        pass

    @abstractmethod
    def load(self, limit: int) -> list[dict]:
        pass