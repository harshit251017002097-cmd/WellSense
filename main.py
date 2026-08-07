"""HydroRoute AI - Main Flask Application."""
import os
import json
from flask import Flask, request, jsonify, render_template
from backend.gemini_service import generate_flood_aware_route, generate_fallback_route
from backend.weather_service import get_weather
from backend.routing_service import geocode_location, get_route, reverse_geocode

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="",
    template_folder="templates"
)

import backend  # noqa


@app.route("/")
def serve():
    """Serve the main web app."""
    return render_template("index.html")


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "HydroRoute AI"})


@app.route("/api/geocode")
def geocode():
    """Geocode a location query to coordinates."""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Query parameter q is required"}), 400

    result = geocode_location(query)
    if result:
        return jsonify(result)
    return jsonify({"error": "Location not found"}), 404


@app.route("/api/reverse-geocode")
def reverse_geocode_endpoint():
    """Reverse geocode coordinates to location name."""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng parameters are required"}), 400

    name = reverse_geocode(lat, lng)
    return jsonify({"name": name, "lat": lat, "lng": lng})


@app.route("/api/weather")
def weather():
    """Get weather and flood risk data for a location."""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng parameters are required"}), 400

    location_name = request.args.get("name", "Unknown location")
    weather_data = get_weather(lat, lng, location_name)
    return jsonify(weather_data)


@app.route("/api/route", methods=["POST"])
def get_safe_route():
    """Main route planning endpoint - combines weather data + Gemini reasoning."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    origin = data.get("origin", "")
    destination = data.get("destination", "")
    mode = data.get("mode", "four-wheeler")
    location_input_type = data.get("location_input_type", "manual")
    origin_coords = data.get("origin_coords")
    destination_coords = data.get("destination_coords")

    if not origin or not destination:
        return jsonify({"error": "origin and destination are required"}), 400

    origin_coord = None
    if origin_coords and origin_coords.get("lat") and origin_coords.get("lng"):
        origin_coord = (origin_coords["lat"], origin_coords["lng"])
    else:
        geocoded = geocode_location(origin)
        if geocoded:
            origin_coord = (geocoded["lat"], geocoded["lng"])
            origin = geocoded["display_name"]

    destination_coord = None
    if destination_coords and destination_coords.get("lat") and destination_coords.get("lng"):
        destination_coord = (destination_coords["lat"], destination_coords["lng"])
    else:
        geocoded = geocode_location(destination)
        if geocoded:
            destination_coord = (geocoded["lat"], geocoded["lng"])
            destination = geocoded["display_name"]

    if not origin_coord or not destination_coord:
        return jsonify({"error": "Could not resolve one or both locations."}), 400

    origin_weather = get_weather(origin_coord[0], origin_coord[1], origin)
    osrm_route = get_route(origin_coord, destination_coord, mode)

    prompt_data = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "location_input_type": location_input_type,
        "weather_context": origin_weather,
        "origin_coords": origin_coord,
        "destination_coords": destination_coord
    }

    try:
        gemini_result = generate_flood_aware_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json")
    except Exception as e:
        gemini_result = generate_fallback_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json", {})

    response = {
        "text_response": text_response,
        "risk_level": parsed_json.get("risk_level", origin_weather.get("risk_level", "UNKNOWN")) if parsed_json else origin_weather.get("risk_level", "UNKNOWN"),
        "avoid_locations": parsed_json.get("avoid_locations", []) if parsed_json else [],
        "safe_waypoints": parsed_json.get("safe_waypoints", []) if parsed_json else [],
        "origin": {"name": origin, "coordinates": {"lat": origin_coord[0], "lng": origin_coord[1]}},
        "destination": {"name": destination, "coordinates": {"lat": destination_coord[0], "lng": destination_coord[1]}},
        "mode": mode,
        "weather": origin_weather,
        "route": osrm_route
    }

    return jsonify(response)


@app.route("/api/route-by-coords", methods=["POST"])
def get_safe_route_by_coords():
    """Route planning using explicit coordinates (GPS or map click)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    origin_lat = data.get("origin_lat")
    origin_lng = data.get("origin_lng")
    dest_lat = data.get("dest_lat")
    dest_lng = data.get("dest_lng")
    mode = data.get("mode", "four-wheeler")
    location_input_type = data.get("location_input_type", "gps")

    if None in [origin_lat, origin_lng, dest_lat, dest_lng]:
        return jsonify({"error": "origin_lat, origin_lng, dest_lat, dest_lng are required"}), 400

    origin_coord = (float(origin_lat), float(origin_lng))
    destination_coord = (float(dest_lat), float(dest_lng))

    origin_name = reverse_geocode(origin_coord[0], origin_coord[1])
    destination_name = reverse_geocode(destination_coord[0], destination_coord[1])

    weather_data = get_weather(origin_coord[0], origin_coord[1], origin_name)
    osrm_route = get_route(origin_coord, destination_coord, mode)

    prompt_data = {
        "origin": origin_name,
        "destination": destination_name,
        "mode": mode,
        "location_input_type": location_input_type,
        "weather_context": weather_data,
        "origin_coords": origin_coord,
        "destination_coords": destination_coord
    }

    try:
        gemini_result = generate_flood_aware_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json")
    except Exception:
        gemini_result = generate_fallback_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json", {})

    response = {
        "text_response": text_response,
        "risk_level": parsed_json.get("risk_level", weather_data.get("risk_level", "UNKNOWN")) if parsed_json else weather_data.get("risk_level", "UNKNOWN"),
        "avoid_locations": parsed_json.get("avoid_locations", []) if parsed_json else [],
        "safe_waypoints": parsed_json.get("safe_waypoints", []) if parsed_json else [],
        "origin": {"name": origin_name, "coordinates": {"lat": origin_coord[0], "lng": origin_coord[1]}},
        "destination": {"name": destination_name, "coordinates": {"lat": destination_coord[0], "lng": destination_coord[1]}},
        "mode": mode,
        "weather": weather_data,
        "route": osrm_route
    }

    return jsonify(response)


@app.route("/api/live-route", methods=["POST"])
def get_live_route():
    """Route planning using live GPS location + destination input."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    origin_lat = data.get("origin_lat")
    origin_lng = data.get("origin_lng")
    destination = data.get("destination", "")
    mode = data.get("mode", "four-wheeler")

    if None in [origin_lat, origin_lng] or not destination:
        return jsonify({"error": "origin_lat, origin_lng, and destination are required"}), 400

    origin_coord = (float(origin_lat), float(origin_lng))
    origin_name = reverse_geocode(origin_coord[0], origin_coord[1])

    dest_geocoded = geocode_location(destination)
    if not dest_geocoded:
        return jsonify({"error": "Could not find destination location"}), 404

    destination_coord = (dest_geocoded["lat"], dest_geocoded["lng"])
    destination_name = dest_geocoded["display_name"]

    weather_data = get_weather(origin_coord[0], origin_coord[1], origin_name)
    osrm_route = get_route(origin_coord, destination_coord, mode)

    prompt_data = {
        "origin": origin_name,
        "destination": destination_name,
        "mode": mode,
        "location_input_type": "live",
        "weather_context": weather_data,
        "origin_coords": origin_coord,
        "destination_coords": destination_coord
    }

    try:
        gemini_result = generate_flood_aware_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json")
    except Exception:
        gemini_result = generate_fallback_route(prompt_data)
        text_response = gemini_result["text_response"]
        parsed_json = gemini_result.get("parsed_json", {})

    response = {
        "text_response": text_response,
        "risk_level": parsed_json.get("risk_level", weather_data.get("risk_level", "UNKNOWN")) if parsed_json else weather_data.get("risk_level", "UNKNOWN"),
        "avoid_locations": parsed_json.get("avoid_locations", []) if parsed_json else [],
        "safe_waypoints": parsed_json.get("safe_waypoints", []) if parsed_json else [],
        "origin": {"name": origin_name, "coordinates": {"lat": origin_coord[0], "lng": origin_coord[1]}},
        "destination": {"name": destination_name, "coordinates": {"lat": destination_coord[0], "lng": destination_coord[1]}},
        "mode": mode,
        "weather": weather_data,
        "route": osrm_route
    }

    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
