"""Weather data service using Open-Meteo (free, no API key required)."""
import requests


def get_weather(lat: float, lng: float, location_name: str = "Unknown") -> dict:
    """
    Fetch current weather and recent precipitation data from Open-Meteo.

    Args:
        lat: Latitude
        lng: Longitude
        location_name: Human-readable location name

    Returns:
        dict with weather data and flood risk assessment
    """
    try:
        # Open-Meteo API for current weather + 1-hour forecast
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lng}"
            "&current=temperature_2m,relative_humidity_2m,weather_code"
            "&hourly=precipitation,rain,weather_code"
            "&past_days=1&forecast_days=1"
            "&timezone=auto"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract hourly data for last few hours
        hourly = data.get('hourly', {})
        precipitation = hourly.get('precipitation', [])
        times = hourly.get('time', [])

        # Get current weather
        current = data.get('current', {})
        temperature = current.get('temperature_2m', 'N/A')
        humidity = current.get('relative_humidity_2m', 'N/A')
        weather_code = current.get('weather_code', 0)

        # Calculate recent precipitation (last 3 hours)
        recent_rain = 0
        last_hour_precip = 0
        max_rain_rate = 0

        if precipitation:
            now_hour = current.get('time', '')
            try:
                idx = times.index(now_hour)
            except (ValueError, TypeError):
                idx = len(precipitation) - 1

            for i in range(max(0, idx - 2), min(len(precipitation), idx + 1)):
                recent_rain += precipitation[i]

            if idx < len(precipitation):
                last_hour_precip = precipitation[idx]

        # Use last_hour_precip as rain rate proxy (mm/hr)
        max_rain_rate = last_hour_precip

        # Determine risk level based on precipitation
        risk_level = _assess_risk(recent_rain, max_rain_rate, weather_code)

        # Format rain rate
        if max_rain_rate > 0:
            if max_rain_rate < 0.5:
                rain_intensity = "Light rain"
            elif max_rain_rate < 2.0:
                rain_intensity = "Moderate rain"
            elif max_rain_rate < 10.0:
                rain_intensity = "Heavy rain"
            else:
                rain_intensity = "Very heavy rain"
        else:
            rain_intensity = "No recent rain" if weather_code < 60 else "Drizzle"

        return {
            'location_name': location_name,
            'coordinates': {'lat': lat, 'lng': lng},
            'temperature': temperature,
            'humidity': humidity,
            'weather_code': weather_code,
            'precipitation_mm': last_hour_precip,
            'recent_rainfall_3h': round(recent_rain, 1),
            'precipitation_rate': rain_intensity,
            'max_rain_rate_mm_h': round(max_rain_rate, 1),
            'risk_level': risk_level,
            'weather_description': _weather_code_to_text(weather_code)
        }
    except Exception as e:
        # Return fallback data if API fails
        return {
            'location_name': location_name,
            'coordinates': {'lat': lat, 'lng': lng},
            'temperature': 'N/A',
            'humidity': 'N/A',
            'weather_code': 0,
            'precipitation_mm': 0,
            'recent_rainfall_3h': 0,
            'precipitation_rate': 'unknown',
            'max_rain_rate_mm_h': 0,
            'risk_level': 'UNKNOWN',
            'weather_description': f'Data unavailable ({str(e)})',
            'error': str(e)
        }


def _assess_risk(recent_rain: float, rain_rate: float, weather_code: int) -> str:
    """
    Assess flood risk level based on precipitation data.

    Flood risk thresholds (approximate):
    - CRITICAL: > 50mm in 3 hours, or very heavy rain (>15mm/hr)
    - HIGH: 20-50mm in 3 hours, or heavy rain (5-15mm/hr)
    - MEDIUM: 5-20mm in 3 hours, or moderate rain (1-5mm/hr)
    - LOW: < 5mm in 3 hours, or light rain/drizzle
    """
    if rain_rate >= 15 or recent_rain >= 50:
        return "CRITICAL"
    elif rain_rate >= 5 or recent_rain >= 20:
        return "HIGH"
    elif rain_rate >= 1 or recent_rain >= 5:
        return "MEDIUM"
    else:
        return "LOW"


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to description."""
    codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    return codes.get(code, "Unknown")
