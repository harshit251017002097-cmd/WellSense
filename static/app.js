/* HydroRoute AI - Frontend Application Logic */

// State management
let appState = {
    inputMode: "manual",
    travelMode: "four-wheeler",
    map: null,
    markers: [],
    routeLayer: null,
    originCoords: null,
    destinationCoords: null,
    liveLocation: null,
    isLoading: false
};

// DOM Elements
const els = {
    resultsPanel: document.getElementById("resultsPanel"),
    resultsContent: document.getElementById("resultsContent"),
    statusBar: document.getElementById("statusBar"),
    statusIcon: document.getElementById("statusIcon"),
    statusText: document.getElementById("statusText"),
    submitBtn: document.getElementById("submitRouteBtn"),
    loadingSpinner: document.getElementById("loadingSpinner")
};

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    updateStatus("System ready. Enter your locations to get a safe route.", "green");
});

function initMap() {
    appState.map = L.map("map").setView([20.5937, 78.9629], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors | HydroRoute AI"
    }).addTo(appState.map);

    appState.map.on("click", (e) => {
        if (appState.inputMode === "gps") handleMapClick(e.latlng);
    });
}

function setInputMode(mode) {
    appState.inputMode = mode;
    document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
    document.querySelector(`[data-mode="${mode}"]`).classList.add("active");
    document.getElementById("manualForm").classList.toggle("hidden", mode !== "manual");
    document.getElementById("gpsForm").classList.toggle("hidden", mode !== "gps");
    document.getElementById("liveForm").classList.toggle("hidden", mode !== "live");
    if (mode === "live") getCurrentLocation();
}

function setTravelMode(mode) {
    appState.travelMode = mode;
    document.querySelectorAll(".mode-option").forEach(b => b.classList.remove("active"));
    document.querySelector(`[data-travel="${mode}"]`).classList.add("active");
}

function handleMapClick(latlng) {
    if (!appState.originCoords) {
        appState.originCoords = [latlng.lat, latlng.lng];
        setMapMarker(appState.originCoords, "Origin", "#4caf50");
        document.getElementById("gpsOriginCoords").textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
        appState.map.setView(latlng, 14);
    } else if (!appState.destinationCoords) {
        appState.destinationCoords = [latlng.lat, latlng.lng];
        setMapMarker(appState.destinationCoords, "Destination", "#f44336");
        appState.map.setView(latlng, 14);
    }
}

function setMapMarker(coords, title, color) {
    clearMapMarkers();
    const icon = L.divIcon({
        className: "custom-marker",
        html: `<div class="marker-pin" style="background:${color}">${title === "Origin" ? "A" : "B"}</div>`,
        iconSize: [32, 32]
    });
    const marker = L.marker(coords, { icon }).addTo(appState.map);
    marker.bindPopup(`<b>${title}</b><br>${coords[0].toFixed(4)}, ${coords[1].toFixed(4)}`);
    appState.markers.push(marker);
}

function clearMapMarkers() {
    appState.markers.forEach(m => appState.map.removeLayer(m));
    appState.markers = [];
}

function getCurrentLocation() {
    if (!navigator.geolocation) return updateStatus("Geolocation not supported.", "danger");
    updateStatus("Detecting your location...", "info");
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const coords = [pos.coords.latitude, pos.coords.longitude];
            appState.liveLocation = coords;
            appState.originCoords = coords;
            document.getElementById("liveLocationCoords").textContent = `${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`;
            setMapMarker(coords, "Your Location", "#4caf50");
            appState.map.setView(coords, 14);
            updateStatus("Live location detected. Ready to find safe route.", "safe");
        },
        () => updateStatus("Could not get location. Use manual entry.", "danger"),
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

function handleSearchInput(query, inputId) {
    if (!query || query.length < 3) return hideSuggestions(inputId);
    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`, {
        headers: { "User-Agent": "HydroRoute-AI/1.0" }
    }).then(r => r.json()).then(results => showSuggestions(results, inputId)).catch(() => hideSuggestions(inputId));
}

function showSuggestions(results, inputId) {
    const el = document.getElementById(inputId.replace("Input", "Suggestions"));
    if (!el) return;
    el.innerHTML = "";
    el.classList.add("active");
    results.forEach(r => {
        const div = document.createElement("div");
        div.className = "suggestion-item";
        div.textContent = r.display_name.split(",").slice(0, 3).join(",");
        div.onclick = () => { fillInput(inputId, r); el.classList.remove("active"); };
        el.appendChild(div);
    });
}

function fillInput(inputId, result) {
    document.getElementById(inputId).value = result.display_name;
    const coords = [parseFloat(result.lat), parseFloat(result.lon)];
    if (inputId === "originInput") appState.originCoords = coords;
    else if (inputId === "destinationInput") appState.destinationCoords = coords;
    else if (inputId === "liveDestinationInput") appState.destinationCoords = coords;
}

function hideSuggestions(inputId) {
    const el = document.getElementById(inputId.replace("Input", "Suggestions"));
    if (el) el.classList.remove("active");
}

function submitRoute() {
    const origin = document.getElementById("originInput").value.trim();
    const destination = document.getElementById("destinationInput").value.trim();
    const liveDest = document.getElementById("liveDestinationInput").value.trim();

    let payload = { mode: appState.travelMode, location_input_type: appState.inputMode };

    if (appState.inputMode === "gps") {
        if (!appState.originCoords || !appState.destinationCoords) {
            return updateStatus("Set both origin and destination on the map.", "danger");
        }
        payload.origin_lat = appState.originCoords[0];
        payload.origin_lng = appState.originCoords[1];
        payload.dest_lat = appState.destinationCoords[0];
        payload.dest_lng = appState.destinationCoords[1];
        callAPI("/api/route-by-coords", payload);
    } else if (appState.inputMode === "live") {
        if (!appState.liveLocation || !liveDest) {
            return updateStatus(!appState.liveLocation ? "Enable location access." : "Enter a destination.", "danger");
        }
        payload.origin_lat = appState.liveLocation[0];
        payload.origin_lng = appState.liveLocation[1];
        payload.destination = liveDest;
        callAPI("/api/live-route", payload);
    } else {
        if (!origin || !destination) {
            return updateStatus("Enter both origin and destination.", "danger");
        }
        payload.origin = origin;
        payload.destination = destination;
        callAPI("/api/route", payload);
    }
}

function callAPI(endpoint, payload) {
    showLoading(true);
    showResultsPanel();
    updateStatus("Analyzing flood risk and planning safe route...", "info");

    fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        showLoading(false);
        if (data.error) showResultsError(data.error);
        else displayResults(data);
    })
    .catch(() => {
        showLoading(false);
        showResultsError("Network error. Please check your connection.");
    });
}

function showResultsPanel() {
    els.resultsPanel.classList.remove("hidden");
    els.resultsPanel.classList.add("show");
    els.resultsContent.innerHTML = `<div class="loading-results"><div class="spinner"></div><p>Analyzing flood risk...</p></div>`;
}

function showResultsError(msg) {
    els.resultsContent.innerHTML = `<div class="safety-box"><h3>Error</h3><p>${msg}</p></div>`;
}

function displayResults(data) {
    const risk = data.risk_level || "UNKNOWN";
    const textResponse = data.text_response || "No route information available.";
    const weather = data.weather || {};

    let weatherHtml = "";
    if (weather && !weather.error) {
        const emoji = getWeatherEmoji(weather.weather_code || 0, weather.precipitation_mm || 0);
        weatherHtml = `
            <div class="weather-card">
                <div class="weather-icon">${emoji}</div>
                <div class="weather-info">
                    <h4>${weather.location_name || "Unknown"}</h4>
                    <div class="weather-detail">Temp: ${weather.temperature || "?"}°C | Rain: ${weather.precipitation_mm || 0}mm/hr | 3h: ${weather.recent_rainfall_3h || 0}mm</div>
                    <span class="risk-badge ${getRiskClass(risk)}">${risk} RISK</span>
                </div>
            </div>`;
    }

    els.resultsContent.innerHTML = `
        ${weatherHtml}
        <div class="safety-box">${textResponse.replace(/\n/g, "<br>")}</div>`;

    if (data.route && data.route.geometry) drawRoute(data.route.geometry);
    updateStatusFromRisk(risk);
}

function getRiskClass(level) {
    return { CRITICAL: "danger", HIGH: "danger", MEDIUM: "medium", LOW: "low" }[level] || "";
}

function getWeatherEmoji(code, rain) {
    if (rain > 10 || (code >= 61 && code <= 67)) return "🌧️";
    if (rain > 2 || (code >= 80 && code <= 82)) return "🌦️";
    if (code >= 95) return "⛈️";
    return "☁️";
}

function updateStatusFromRisk(risk) {
    const msgs = {
        CRITICAL: ["🔴", "CRITICAL RISK: Do not travel unless absolutely necessary!"],
        HIGH: ["🟠", "HIGH RISK: Travel with extreme caution!"],
        MEDIUM: ["🟡", "MODERATE RISK: Check conditions before leaving."],
        LOW: ["🟢", "LOW RISK: Conditions are relatively safe."],
        UNKNOWN: ["⚪", "Status: Proceed with caution."]
    };
    const [icon, text] = msgs[risk] || msgs.UNKNOWN;
    els.statusIcon.textContent = icon;
    els.statusText.textContent = text;
    els.statusBar.className = "status-bar";
    if (risk === "CRITICAL" || risk === "HIGH") els.statusBar.classList.add("warning");
    if (risk === "LOW") els.statusBar.classList.add("safe");
}

function updateStatus(text, type) {
    els.statusText.textContent = text;
    els.statusIcon.textContent = { danger: "🔴", safe: "🟢", info: "ℹ️" }[type] || "🟡";
    els.statusBar.className = "status-bar";
    if (type === "danger") els.statusBar.classList.add("warning");
    if (type === "safe") els.statusBar.classList.add("safe");
}

function showLoading(show) {
    els.submitBtn.classList.toggle("disabled", show);
    els.submitBtn.querySelector(".btn-text").textContent = show ? "Processing..." : "Get Safe Route";
}

function drawRoute(geometry) {
    if (appState.routeLayer) appState.map.removeLayer(appState.routeLayer);
    appState.routeLayer = L.geoJSON(geometry, {
        style: { color: "#00bcd4", weight: 5, opacity: 0.8, dashArray: "10, 5" }
    }).addTo(appState.map);
    appState.map.fitBounds(appState.routeLayer.getBounds(), { padding: [80, 80] });
}

function closeResults() {
    els.resultsPanel.classList.remove("show");
    els.resultsPanel.classList.add("hidden");
}
