"""Routing service using OSRM (Open Source Routing Machine) for map routing."""
import requests
import json


OSRM_SERVER = "https://router.project-osrm.org"


def geocode_location(query: str) -> dict:
    """
    Geocode a place name to coordinates using Nominatim (OpenStreetMap).

    Args:
        query: Human-readable location string (e.g., "Mumbai, India")

    Returns:
        dict with lat, lng, display_name, or None if not found
    """
    try:
        url = (
            "https://nominatim.openstreetmap.org/search?"
            f"q={requests.utils.quote(query)}"
            "&format=json&addressdetails=1&limit=1"
        )
        headers = {"User-Agent": "HydroRoute-AI/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        results = response.json()

        if results and len(results) > 0:
            return {
                'lat': float(results[0]['lat']),
                'lng': float(results[0]['lon']),
                'display_name': results[0]['display_name'],
                'boundingbox': results[0].get('boundingbox')
            }
        return None
    except Exception as e:
        return None


def get_route(origin: tuple, destination: tuple, mode: str = 'car') -> dict:
    """
    Get route between two coordinates using OSRM.

    Args:
        origin: tuple of (lat, lng)
        destination: tuple of (lat, lng)
        mode: 'car', 'walking', 'cycling', 'driving'

    Returns:
        dict with route geometry, distance, duration, and waypoints
    """
    mode_map = {
        'walking': 'foot',
        'two-wheeler': 'car',
        'four-wheeler': 'car',
        'public-transit': 'car'
    }
    profile = mode_map.get(mode, 'car')

    try:
        url = (
            f"{OSRM_SERVER}/route/v1/{profile}/"
            f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            "?overview=full&geometries=geojson&alternatives=true&steps=true"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            return {
                'geometry': route['geometry'],
                'distance_km': round(route['distance'] / 1000, 2),
                'duration_min': round(route['duration'] / 60, 1),
                'waypoints': _extract_waypoints(route.get('legs', [])),
                'alternatives': [
                    {
                        'geometry': r['geometry'],
                        'distance_km': round(r['distance'] / 1000, 2),
                        'duration_min': round(r['duration'] / 60, 1)
                    }
                    for r in data.get('routes', [])[1:3]
                ]
            }
        return None
    except Exception as e:
        return None


def reverse_geocode(lat: float, lng: float) -> str:
    """
    Reverse geocode coordinates to a readable location name.

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        Human-readable address string
    """
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse?"
            f"lat={lat}&lon={lng}&format=json&addressdetails=1"
        )
        headers = {"User-Agent": "HydroRoute-AI/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and data.get('display_name'):
            # Try to get a concise location name
            addr = data.get('address', {})
            parts = []
            for key in ['road', 'suburb', 'neighbourhood', 'city', 'town', 'village', 'state', 'country']:
                if key in addr:
                    parts.append(addr[key])
            if parts:
                return ', '.join(parts[-3:]) if len(parts) > 3 else ', '.join(parts)
            return data['display_name'].split(',')[0]
        return f"Location ({lat:.4f}, {lng:.4f})"
    except Exception:
        return f"Location ({lat:.4f}, {lng:.4f})"


def _extract_waypoints(legs: list) -> list:
    """Extract major waypoints from route legs."""
    waypoints = []
    for leg in legs:
        steps = leg.get('steps', [])
        for step in steps[:5]:  # Take first few key steps
            if step.get('name') and step['name'] not in [w['name'] for w in waypoints if 'name' in w]:
                waypoints.append({
                    'name': step['name'],
                    'instruction': step.get('maneuver', {}).get('instruction', ''),
                    'distance_km': round(step.get('distance', 0) / 1000, 2),
                    'location': {
                        'lat': step.get('geometry', {}).get('coordinates', [None, None])[1],
                        'lng': step.get('geometry', {}).get('coordinates', [None, None])[0]
                    }
                })
    return waypoints
