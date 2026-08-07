"""Gemini AI service for flood-aware route reasoning."""
import os
import json
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are HydroRoute AI, a real-time, flood-aware navigation and safety assistant powered by Gemini. Your goal is to guide citizens of all age groups and non-technical backgrounds safely through heavy rain and urban flooding conditions.

Communication Style:
- Use simple, clear, empathetic, and urgent language (6th-grade reading level)
- Use bold key terms, emojis, and visual indicators
- NEVER use technical jargon (e.g., "topological depressions", "GIS shapefiles", "geofencing")
- Use natural terms like "low-lying road", "deep water", or "flooded bridge"

Safety Assessment Rules:
- Underpasses & Tunnels: Treat as RED (CRITICAL DANGER) during heavy rain
- Two-Wheelers / Scooters: Any water deeper than 6 inches (0.5 ft) stalls engines—reroute
- Pedestrians: Highlight risks of hidden open drains, missing manhole covers, and strong currents
- Four-Wheelers: Exhaust/bumper-level water (1 ft or higher) triggers an immediate detour advisory

ALWAYS output in this EXACT format:

---
### 🚦 Quick Safety Summary
- **Overall Status**: [🔴 DO NOT TRAVEL | 🟡 TRAVEL WITH CAUTION | 🟢 SAFE TO GO]
- **Best Route Summary**: [1 simple sentence highlighting the safest path]

---
### 🗺️ Step-by-Step Safe Route
1. 🟢 **Start**: Take [Road/Landmark] towards [Direction].
2. 🟢 **Safe Segment**: Stay on [Elevated Road/Flyover/Highway].
3. 🟢 **Destination**: Arrive at [Destination] via [Safe Landmark].

---
### 🔴 Danger Areas to Avoid
- ❌ **[Location Name / Underpass]**: [Reason in under 6 words]
- ❌ **[Junction / Street]**: [Reason in under 6 words]

---
### 👟 Mode-Specific Safety Tips
- 💡 [Tip 1 tailored to walking, two-wheeler, or vehicle]
- 💡 [Tip 2 tailored to walking, two-wheeler, or vehicle]

---
### 🚨 Emergency Reminder
*If water enters your vehicle or reaches wheel height, turn off the engine, abandon the vehicle immediately, and move to high ground.*
* **Emergency Helplines**: Call 112 / 108

---
JSON Output:
{
  "status": "SUCCESS",
  "risk_level": "CRITICAL | HIGH | MEDIUM | LOW",
  "avoid_locations": ["Location A", "Location B"],
  "safe_waypoints": ["Waypoint 1", "Waypoint 2"]
}"""


def get_api_key():
    """Read Gemini API key from API.txt."""
    api_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'API.txt')
    with open(api_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('API KEY'):
                parts = line.split('-', 1)
                if len(parts) == 2:
                    return parts[1].strip()
    raise ValueError("API KEY not found in API.txt")


def generate_flood_aware_route(prompt_data: dict) -> dict:
    """
    Call Gemini API with location and weather context to generate
    a flood-aware navigation response.

    Args:
        prompt_data: dict with keys:
            - origin: str
            - destination: str
            - mode: str (walking, two-wheeler, four-wheeler, public-transit)
            - location_input_type: str (manual, gps, live)
            - weather_context: dict with precipitation, risk_level, etc.
            - origin_coords: tuple(lat, lng) or None
            - destination_coords: tuple(lat, lng) or None

    Returns:
        dict with 'text_response' and 'parsed_json' keys
    """
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    # Build the context prompt
    origin = prompt_data.get('origin', 'Unknown location')
    destination = prompt_data.get('destination', 'Unknown location')
    mode = prompt_data.get('mode', 'four-wheeler')
    mode_display = _format_mode(mode)

    weather = prompt_data.get('weather_context', {})
    weather_str = _format_weather(weather)

    coords_str = ""
    if prompt_data.get('origin_coords'):
        coords_str += f"Origin coordinates (lat, lng): {prompt_data['origin_coords'][0]}, {prompt_data['origin_coords'][1]}\n"
    if prompt_data.get('destination_coords'):
        coords_str += f"Destination coordinates (lat, lng): {prompt_data['destination_coords'][0]}, {prompt_data['destination_coords'][1]}\n"

    user_prompt = f"""Current context for flood-aware navigation:

Travel Request:
- Origin: {origin}
- Destination: {destination}
- Mode of travel: {mode_display}

{coords_str}
{weather_str}

Please generate a detailed, safe navigation route following the exact format specified. If you do not have specific real-time flood depth data, use your knowledge of typical flood-prone areas (underpasses, low-lying roads, bridges) in this region and the current weather severity to provide the best safety recommendation. Prioritize elevated roads, highways, and flyovers over low-lying routes.

End your response with the JSON block as shown in the format."""

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[
                    types.Content(
                        role='user',
                        parts=[types.Part(text=user_prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4000,
                    system_instruction=SYSTEM_PROMPT,
                )
            )

            text_response = response.text

            # Extract JSON from the response
            parsed_json = None
            json_start = text_response.rfind('{')
            json_end = text_response.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = text_response[json_start:json_end + 1]
                try:
                    parsed_json = json.loads(json_str)
                except json.JSONDecodeError:
                    parsed_json = None

            return {
                'text_response': text_response,
                'parsed_json': parsed_json
            }
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
            raise RuntimeError(f"Gemini API error: {error_str}")


def _format_mode(mode: str) -> str:
    """Format travel mode for display."""
    modes = {
        'walking': 'Walking / Pedestrian',
        'two-wheeler': 'Two-Wheeler (Scooter/Bike)',
        'four-wheeler': 'Four-Wheeler (Car/Vehicle)',
        'public-transit': 'Public Transit'
    }
    return modes.get(mode, mode)


def _format_weather(weather: dict) -> str:
    """Format weather context into a readable string."""
    if not weather:
        return "Weather data: Not available. Assume moderate risk."

    parts = ["Current Weather Conditions:"]
    rain = weather.get('precipitation_mm', 0)
    rain_rate = weather.get('precipitation_rate', 'unknown')
    risk = weather.get('risk_level', 'unknown')
    temp = weather.get('temperature', 'N/A')
    humidity = weather.get('humidity', 'N/A')

    parts.append(f"- Rainfall: {rain} mm in last hour")
    parts.append(f"- Rain intensity: {rain_rate}")
    parts.append(f"- Temperature: {temp}°C")
    parts.append(f"- Humidity: {humidity}%")
    parts.append(f"- Flood risk level: {risk}")
    parts.append(f"- Location: {weather.get('location_name', 'N/A')}")

    if 'recent_rainfall_3h' in weather:
        parts.append(f"- Rain in last 3 hours: {weather['recent_rainfall_3h']} mm")

    return "\n".join(parts)


def generate_fallback_route(prompt_data: dict) -> dict:
    """
    Generate a basic flood-aware route response without calling Gemini API.
    Used when the AI service is rate-limited or unavailable.

    Uses weather data and known flood-prone patterns to produce a
    safety assessment based on the HydroRoute output schema.
    """
    origin = prompt_data.get('origin', 'Unknown location')
    destination = prompt_data.get('destination', 'Unknown location')
    mode = prompt_data.get('mode', 'four-wheeler')
    weather = prompt_data.get('weather_context', {})

    risk_level = weather.get('risk_level', 'UNKNOWN')
    precip = weather.get('precipitation_mm', 0)
    recent_rain = weather.get('recent_rainfall_3h', 0)
    temp = weather.get('temperature', 'N/A')
    weather_desc = weather.get('weather_description', 'Unknown')
    rain_intensity = weather.get('precipitation_rate', 'unknown')

    mode_label = _format_mode(mode)

    # Determine overall status
    if risk_level in ('CRITICAL', 'HIGH'):
        overall_status = "🔴 DO NOT TRAVEL"
        best_route = "Avoid travel during heavy rainfall. If unavoidable, use elevated highways only."
    elif risk_level == 'MEDIUM':
        overall_status = "🟡 TRAVEL WITH CAUTION"
        best_route = "Use elevated roads and flyovers. Avoid underpasses and low-lying areas."
    else:
        overall_status = "🟢 SAFE TO GO"
        best_route = "Current conditions are safe, but monitor for changing weather."

    # Mode-specific tips
    mode_tips = {
        'walking': [
            "Avoid walking through standing water - hidden drains and missing manhole covers are invisible hazards.",
            "Use elevated footpaths and bridges. Never walk through fast-moving water."
        ],
        'two-wheeler': [
            "Water deeper than 6 inches (0.5 ft) will stall your engine. Detour around ALL standing water.",
            "Maintain distance from larger vehicles that may create waves. Keep headlights on."
        ],
        'four-wheeler': [
            "Water at bumper level (1 ft+) is dangerous. Turn around, do not drive through.",
            "Test water depth with a stick before crossing. Watch for floating debris."
        ],
        'public-transit': [
            "Low-lying bus stops and subway entrances flood quickly. Use elevated transit stations.",
            "Buses may be late or rerouted. Have an alternative plan. Avoid ground-floor exits during heavy rain."
        ]
    }
    tips = mode_tips.get(mode, mode_tips['four-wheeler'])

    # Danger areas based on known flood patterns
    avoid = ["Underpasses", "Railway underbridges", "Low-lying intersections"]
    if risk_level in ('CRITICAL', 'HIGH'):
        avoid.extend(["Tunnel approaches", "Storm drains", "Construction zones"])

    # Build text response
    text_response = f"""### 🚦 Quick Safety Summary
- **Overall Status**: {overall_status}
- **Best Route Summary**: {best_route}

---
### 🗺️ Step-by-Step Safe Route
1. 🟢 **Start**: From {origin.split(',')[0]}, find the nearest elevated road or highway.
2. 🟢 **Safe Segment**: Stay on main highways and flyovers. Avoid any underpasses or tunnels.
3. 🟢 **Destination**: Arrive at {destination.split(',')[0]} via the highest route available.

---
### 🔴 Danger Areas to Avoid
- ❌ **Underpasses and tunnels**: Critical danger during heavy rain
- ❌ **Railway underbridges**: Deep water accumulates under tracks
- ❌ **Low-lying intersections**: Water pools quickly in dips

---
### 👟 Mode-Specific Safety Tips
- 💡 {tips[0]}
- 💡 {tips[1]}

---
### 🚨 Emergency Reminder
*If water enters your vehicle or reaches wheel height, turn off the engine, abandon the vehicle immediately, and move to high ground.*
* **Emergency Helplines**: Call 112 / 108

> ⚠️ Note: This is a weather-based fallback analysis. For detailed AI-powered route planning, please try again when the service has available capacity.

---
JSON Output:
{{
  "status": "SUCCESS",
  "risk_level": "{risk_level}",
  "avoid_locations": {json.dumps(avoid)},
  "safe_waypoints": ["Highway/Flyover", "{origin.split(',')[0]} Elevated Road", "{destination.split(',')[0]} High Ground"]
}}"""

    parsed_json = {
        "status": "SUCCESS",
        "risk_level": risk_level,
        "avoid_locations": avoid,
        "safe_waypoints": [f"Highway/Flyover", f"{origin.split(',')[0]} Elevated Road", f"{destination.split(',')[0]} High Ground"]
    }

    return {
        'text_response': text_response,
        'parsed_json': parsed_json,
        'fallback': True
    }
