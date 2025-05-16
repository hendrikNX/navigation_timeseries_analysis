import requests
import os
from datetime import datetime
import pytz
from typing import Optional, Tuple

try:
    from .data_models import RouteData
except ImportError: # Fallback for direct execution if needed for simple tests
    from data_models import RouteData

API_KEY = os.environ.get("API_KEY_GOOGLE_MAPS_PLATFORM")

class RouteFetcher:
    """
    Fetches route data from the Google Maps Distance Matrix API.

    Attributes:
        base_url (str): The base URL for the Distance Matrix API.
    """

    def __init__(self):
        self.base_url = "https://maps.googleapis.com/maps/api/distancematrix/json?"

    def get_current_route_data(self, origin_cords: Tuple[float,float], dest_cords: Tuple[float,float]) -> Optional[RouteData]:
        """
        Fetches route data for a given origin and destination.

        Args:
            origin_cords (Tuple[float, float]): Latitude and longitude of the origin.
            dest_cords (Tuple[float, float]): Latitude and longitude of the destination.
        Returns:
            Optional[RouteData]: Route data if successful, None otherwise.
        """
        
        if not API_KEY:
            print("Error: API_KEY_GOOGLE_MAPS_PLATFORM is not set.")
            return None

        url = f"{self.base_url}destinations={dest_cords[0]},{dest_cords[1]}&origins={origin_cords[0]},{origin_cords[1]}&units=metric&departure_time=now&traffic_model=best_guess&key={API_KEY}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            response_data = response.json()

            if not response_data["rows"] or not response_data["rows"][0]["elements"]:
                print(f"Error: Empty response or missing elements. Status: {response_data.get('status')}")
                return None

            row = response_data["rows"][0]
            element = row["elements"][0]

            if element["status"] == "OK":
                return RouteData(
                    origin_lat=origin_cords[0], origin_lon=origin_cords[1],
                    dest_lat=dest_cords[0], dest_lon=dest_cords[1],
                    distance_m=element["distance"]["value"], duration_s=element["duration"]["value"],
                    duration_in_traffic_s=element["duration_in_traffic"]["value"],
                    start_time=datetime.now(tz=pytz.timezone("Europe/Berlin")))
            else:
                print(f"Error: Could not retrieve route information. Status: {element['status']}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error: API request failed. {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Error: Unexpected API response structure. {e}")
            return None
