# HydroRoute AI - Flood-Aware Navigation System

A real-time, flood-aware navigation and safety assistant that guides citizens
safely through heavy rain and urban flooding conditions.

## Features

- **Three Input Modes**: Manual city/area names, GPS via map click, or live location
- **Multi-Modal Travel**: Walking, two-wheeler, four-wheeler, public transit
- **Real-Time Weather**: Integrates with Open-Meteo for live precipitation data
- **AI-Powered Reasoning**: Uses Google Gemini for flood-aware route analysis
- **Safety-First Routing**: Prioritizes elevated roads, highways, and flyovers
- **Emergency Ready**: Provides helpline numbers and immediate risk advisories

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python main.py

# 3. Open in browser
http://localhost:5000
```

## Quick Start (Docker)

```bash
docker build -t hydroroute-ai .
docker run -p 5000:5000 -v $(pwd)/API.txt:/app/API.txt hydroroute-ai
```

## Project Structure

```
H2S/
├── API.txt              # Gemini API key
├── main.py              # Flask application entry point
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container configuration
├── backend/
│   ├── __init__.py
│   ├── gemini_service.py    # Gemini AI integration
│   ├── weather_service.py    # Open-Meteo weather data
│   ├── routing_service.py    # OSRM + Nominatim routing
│   └── wsgi.py               # Production WSGI entry
├── templates/
│   └── index.html       # Main web interface
└── static/
    ├── app.js           # Frontend logic
    └── styles.css       # Styling
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main web interface |
| `/api/health` | GET | Health check |
| `/api/geocode` | GET | Geocode a location name |
| `/api/reverse-geocode` | GET | Reverse geocode coordinates |
| `/api/weather` | GET | Weather + flood risk for coordinates |
| `/api/route` | POST | Route planning (manual text input) |
| `/api/route-by-coords` | POST | Route planning (GPS/map click) |
| `/api/live-route` | POST | Route planning (live GPS + destination) |

## Technologies

- **Backend**: Python Flask
- **AI**: Google Gemini 2.0 Flash
- **Weather**: Open-Meteo API (free)
- **Maps**: OpenStreetMap + Leaflet
- **Routing**: OSRM (Open Source Routing Machine)
