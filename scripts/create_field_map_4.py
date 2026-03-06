#!/usr/bin/env python3
"""
Create an interactive web map with address-based field search.
Includes search panel to find fields within a specified radius.

Input:  data/assignment-02/fields_complete.geojson
Output: docs/assignment-02/field_map_4.html

Features:
- Satellite basemap (ESRI World Imagery)
- Search panel: address input + radius selector + search button
- Geocoding via Nominatim (OpenStreetMap)
- Fields within radius displayed on map
- Popup with field details + 3 tabbed charts (Temp, Rainfall, Soil)
- Crop legend
"""

import json
from pathlib import Path

import geopandas as gpd


def calculate_monthly_averages(weather_monthly):
    """Calculate average high, low, and rain by month across all years."""
    if not weather_monthly:
        return None

    month_sums = {m: {"high": 0, "low": 0, "rain": 0, "count": 0} for m in range(1, 13)}

    for record in weather_monthly:
        month = record.get("month")
        if month and month in month_sums:
            month_sums[month]["high"] += record.get("avg_high_c", 0)
            month_sums[month]["low"] += record.get("avg_low_c", 0)
            month_sums[month]["rain"] += record.get("total_rain_in", 0)
            month_sums[month]["count"] += 1

    avg_high = [month_sums[m]["high"] / max(month_sums[m]["count"], 1) for m in range(1, 13)]
    avg_low = [month_sums[m]["low"] / max(month_sums[m]["count"], 1) for m in range(1, 13)]
    avg_rain = [month_sums[m]["rain"] / max(month_sums[m]["count"], 1) for m in range(1, 13)]

    return {
        "avg_high_c": [round(v, 1) for v in avg_high],
        "avg_low_c": [round(v, 1) for v in avg_low],
        "avg_rain_in": [round(v, 2) for v in avg_rain],
    }


def calculate_field_soil_averages(gdf):
    """Calculate average soil properties across all fields."""
    soil_props = [
        "soil_clay_pct",
        "soil_sand_pct",
        "soil_silt_pct",
        "soil_om_pct",
        "soil_ph",
        "soil_cec",
    ]
    averages = {}
    for prop in soil_props:
        values = gdf[prop].dropna()
        averages[prop] = round(values.mean(), 1) if len(values) > 0 else 0
    return averages


def create_map():
    input_path = Path("data/assignment-02/fields_complete.geojson")
    output_path = Path("docs/assignment-02/field_map_4.html")

    print(f"Loading {input_path}...")
    gdf = gpd.read_file(input_path)

    print(f"Original CRS: {gdf.crs}")

    if gdf.crs and gdf.crs != "EPSG:4326":
        print("Transforming to EPSG:4326 (WGS84)...")
        gdf = gdf.to_crs("EPSG:4326")

    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    print(f"Center: ({center_lat:.2f}, {center_lon:.2f})")

    geojson_data = json.loads(gdf.to_json())

    for feature in geojson_data["features"]:
        props = feature.get("properties", {})
        weather_monthly = props.get("weather_monthly", [])
        if weather_monthly:
            props["weather_avg_monthly"] = calculate_monthly_averages(weather_monthly)

    soil_averages = calculate_field_soil_averages(gdf)
    print("Calculated monthly weather averages for all fields")
    print(f"Soil averages: {soil_averages}")

    crop_counts = {}
    for _, row in gdf.iterrows():
        crop = row.get("cdl_crop", None)
        if crop:
            crop_counts[crop] = crop_counts.get(crop, 0) + 1

    color_palette = [
        "#E91E63",
        "#4CAF50",
        "#2196F3",
        "#FF9800",
        "#9C27B0",
        "#00BCD4",
        "#FF5722",
        "#795548",
        "#607D8B",
        "#8BC34A",
    ]
    crop_colors = {
        crop: color_palette[i % len(color_palette)]
        for i, crop in enumerate(sorted(crop_counts.keys()))
    }

    print(f"Crops in data: {crop_counts}")
    print(f"Colors: {crop_colors}")

    legend_items = ""
    for crop, count in sorted(crop_counts.items(), key=lambda x: -x[1]):
        color = crop_colors[crop]
        legend_items += f"""                <div class="legend-item">
                    <div class="legend-color" style="background: {color};"></div>
                    <span>{crop} ({count})</span>
                </div>
"""

    month_labels = (
        '["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]'
    )
    soil_labels = '["Clay %", "Sand %", "Silt %", "OM %", "pH", "CEC"]'
    soil_keys = (
        '["soil_clay_pct", "soil_sand_pct", "soil_silt_pct", "soil_om_pct", "soil_ph", "soil_cec"]'
    )

    html_content = (
        """<!DOCTYPE html>
<html>
<head>
    <title>Oregon Field Search</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        #container { display: flex; height: 100vh; }
        
        #sidebar {
            width: 300px;
            background: #ffffff;
            border-right: 1px solid #ddd;
            padding: 20px;
            overflow-y: auto;
            flex-shrink: 0;
        }
        
        #sidebar h1 {
            font-size: 1.2em;
            margin-bottom: 5px;
            color: #1B5E20;
        }
        
        .panel {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .panel h3 {
            font-size: 0.85em;
            color: #333;
            margin-bottom: 12px;
            text-transform: uppercase;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 8px 0;
            font-size: 0.9em;
        }
        
        .legend-color {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            margin-right: 10px;
            border: 1px solid rgba(0,0,0,0.2);
        }
        
        #map { flex: 1; }

        .search-panel {
            background: #e8f5e9;
            border: 1px solid #a5d6a7;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }

        .search-panel h3 {
            color: #1B5E20;
            margin-bottom: 12px;
        }

        .search-input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 0.9em;
            margin-bottom: 10px;
        }

        .search-row {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }

        .search-row select {
            flex: 1;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 0.9em;
        }

        .search-btn {
            width: 100%;
            padding: 10px;
            background: #1B5E20;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 600;
        }

        .search-btn:hover {
            background: #2e7d32;
        }

        .search-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .search-status {
            font-size: 0.85em;
            color: #666;
            margin-top: 8px;
        }

        .search-status.error {
            color: #c62828;
        }

        .search-status.success {
            color: #1B5E20;
        }

        .results-info {
            font-size: 0.85em;
            color: #1B5E20;
            margin-top: 8px;
            padding: 8px;
            background: #e8f5e9;
            border-radius: 4px;
        }

        .chart-tabs {
            display: flex;
            border-bottom: 1px solid #ddd;
            margin-bottom: 10px;
        }
        
        .chart-tab {
            flex: 1;
            padding: 8px 4px;
            text-align: center;
            cursor: pointer;
            font-size: 0.75em;
            color: #666;
            background: #f5f5f5;
            border: none;
            border-radius: 4px 4px 0 0;
            margin-right: 2px;
        }
        
        .chart-tab.active {
            background: #fff;
            color: #1B5E20;
            font-weight: 600;
            border-bottom: 2px solid #1B5E20;
        }
        
        .chart-container {
            display: none;
        }
        
        .chart-container.active {
            display: block;
        }

        .instructions {
            font-size: 0.75em;
            color: #666;
            margin-top: 8px;
            line-height: 1.4;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="sidebar">
            <h1>Oregon Field Search</h1>
            <p style="font-size: 0.8em; color: #666; margin-bottom: 20px;">Find agricultural fields by address</p>
            
            <div class="search-panel">
                <h3>Search Fields</h3>
                <input type="text" id="address-input" class="search-input" placeholder="Enter Oregon address (e.g., Portland OR)">
                <div class="search-row">
                    <select id="radius-select">
                        <option value="5">5 miles</option>
                        <option value="10" selected>10 miles</option>
                        <option value="25">25 miles</option>
                        <option value="50">50 miles</option>
                    </select>
                </div>
                <button id="search-btn" class="search-btn">Search Fields</button>
                <div id="search-status" class="search-status"></div>
                <div id="results-info" class="results-info" style="display: none;"></div>
                <p class="instructions">Enter an Oregon address or city to find fields within the selected radius. Results include field boundaries, weather data, and soil properties.</p>
            </div>
            
            <div class="panel">
                <h3>Crops</h3>
"""
        + legend_items
        + """            </div>
        </div>
        
        <div id="map"></div>
    </div>
    
    <script>
        var monthLabels = """
        + month_labels
        + """;
        var soilLabels = """
        + soil_labels
        + """;
        var soilKeys = """
        + soil_keys
        + """;
        var soilAverages = """
        + json.dumps(soil_averages)
        + """;

        var map = L.map('map').setView(["""
        + str(center_lat)
        + ", "
        + str(center_lon)
        + """], 7);
        
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri',
            maxZoom: 19
        }).addTo(map);
        
        var allFieldData = """
        + json.dumps(geojson_data)
        + """;
        
        var cropColors = """
        + json.dumps(crop_colors)
        + """;
        
        var charts = {};
        var currentLayer = null;
        var searchMarker = null;

        function getStyle(feature) {
            var crop = feature.properties.cdl_crop || 'Unknown';
            return {
                fillColor: cropColors[crop] || '#757575',
                weight: 2,
                opacity: 1,
                color: 'white',
                fillOpacity: 0.5
            };
        }

        function haversineDistance(lat1, lon1, lat2, lon2) {
            var R = 3959;
            var dLat = (lat2 - lat1) * Math.PI / 180;
            var dLon = (lon2 - lon1) * Math.PI / 180;
            var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                    Math.sin(dLon/2) * Math.sin(dLon/2);
            var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }

        function switchTab(popupId, tabId) {
            var popup = document.getElementById(popupId);
            if (!popup) return;
            
            popup.querySelectorAll('.chart-tab').forEach(function(t) { t.classList.remove('active'); });
            popup.querySelectorAll('.chart-container').forEach(function(c) { c.classList.remove('active'); });
            
            popup.querySelector('#' + tabId).classList.add('active');
            popup.querySelector('#' + tabId + '-chart').classList.add('active');
        }

        function createPopup(props, popupId) {
            if (charts[popupId]) {
                charts[popupId].destroy();
                delete charts[popupId];
            }

            var weather = props.weather_avg_monthly;
            
            var html = '<div id="' + popupId + '" style="min-width:260px;"><h4 style="color:#1B5E20;margin-bottom:10px;">' + (props.field_id || 'Unknown') + '</h4>';
            html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Crop:</span><span>' + (props.cdl_crop || 'N/A') + '</span></div>';
            html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Area:</span><span>' + (props.area_acres ? props.area_acres.toFixed(1) + ' acres' : 'N/A') + '</span></div>';
            
            if (props.soil_muname) {
                html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #eee;">';
                html += '<div style="font-size:0.85em;color:#1B5E20;font-weight:600;margin-bottom:8px;">Soil</div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Type:</span><span>' + props.soil_muname.substring(0,25) + '</span></div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Drainage:</span><span>' + (props.soil_drainage || 'N/A') + '</span></div>';
                html += '</div>';
            }
            
            if (weather || props.soil_clay_pct) {
                html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #eee;">';
                html += '<div class="chart-tabs">';
                html += '<button id="' + popupId + '-temp" class="chart-tab active" onclick="switchTab(\\'' + popupId + '\\', \\'' + popupId + '-temp\\')">Temperature</button>';
                html += '<button id="' + popupId + '-rain" class="chart-tab" onclick="switchTab(\\'' + popupId + '\\', \\'' + popupId + '-rain\\')">Rainfall</button>';
                html += '<button id="' + popupId + '-soil" class="chart-tab" onclick="switchTab(\\'' + popupId + '\\', \\'' + popupId + '-soil\\')">Soil</button>';
                html += '</div>';
                
                html += '<div id="' + popupId + '-temp-chart" class="chart-container active">';
                html += '<canvas id="canvas-' + popupId + '-temp" height="140"></canvas></div>';
                html += '<div id="' + popupId + '-rain-chart" class="chart-container">';
                html += '<canvas id="canvas-' + popupId + '-rain" height="140"></canvas></div>';
                html += '<div id="' + popupId + '-soil-chart" class="chart-container">';
                html += '<canvas id="canvas-' + popupId + '-soil" height="140"></canvas></div>';
                html += '</div>';
            }
            
            html += '</div>';
            return html;
        }

        function initCharts(props, popupId) {
            var weather = props.weather_avg_monthly;

            if (weather) {
                var tempCtx = document.getElementById('canvas-' + popupId + '-temp');
                if (tempCtx) {
                    charts[popupId + '-temp'] = new Chart(tempCtx, {
                        type: 'line',
                        data: {
                            labels: monthLabels,
                            datasets: [
                                {
                                    label: 'High',
                                    data: weather.avg_high_c,
                                    borderColor: '#E91E63',
                                    backgroundColor: 'rgba(233, 30, 99, 0.1)',
                                    tension: 0.3,
                                    fill: false
                                },
                                {
                                    label: 'Low',
                                    data: weather.avg_low_c,
                                    borderColor: '#2196F3',
                                    backgroundColor: 'rgba(33, 150, 243, 0.1)',
                                    tension: 0.3,
                                    fill: false
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
                            scales: {
                                y: { title: { display: true, text: '°C' }, ticks: { font: { size: 9 } } },
                                x: { ticks: { font: { size: 9 } } }
                            }
                        }
                    });
                }

                var rainCtx = document.getElementById('canvas-' + popupId + '-rain');
                if (rainCtx) {
                    charts[popupId + '-rain'] = new Chart(rainCtx, {
                        type: 'bar',
                        data: {
                            labels: monthLabels,
                            datasets: [{
                                label: 'Rainfall',
                                data: weather.avg_rain_in,
                                backgroundColor: 'rgba(76, 175, 80, 0.7)',
                                borderColor: '#388E3C',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { display: false } },
                            scales: {
                                y: { title: { display: true, text: 'inches' }, ticks: { font: { size: 9 } }, beginAtZero: true },
                                x: { ticks: { font: { size: 9 } } }
                            }
                        }
                    });
                }
            }

            if (props.soil_clay_pct !== undefined) {
                var soilCtx = document.getElementById('canvas-' + popupId + '-soil');
                if (soilCtx) {
                    var fieldValues = [];
                    for (var i = 0; i < soilKeys.length; i++) {
                        var key = soilKeys[i];
                        fieldValues.push(props[key] !== undefined ? props[key] : 0);
                    }
                    
                    charts[popupId + '-soil'] = new Chart(soilCtx, {
                        type: 'bar',
                        data: {
                            labels: soilLabels,
                            datasets: [
                                {
                                    label: 'Field',
                                    data: fieldValues,
                                    backgroundColor: 'rgba(255, 152, 0, 0.8)',
                                    borderColor: '#F57C00',
                                    borderWidth: 1
                                },
                                {
                                    label: 'Average',
                                    data: [soilAverages[soilKeys[0]], soilAverages[soilKeys[1]], soilAverages[soilKeys[2]], soilAverages[soilKeys[3]], soilAverages[soilKeys[4]], soilAverages[soilKeys[5]]],
                                    backgroundColor: 'rgba(158, 158, 158, 0.5)',
                                    borderColor: '#9E9E9E',
                                    borderWidth: 1
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
                            scales: {
                                y: { title: { display: true, text: 'Value' }, ticks: { font: { size: 9 } }, beginAtZero: true },
                                x: { ticks: { font: { size: 9 } } }
                            }
                        }
                    });
                }
            }
        }

        var popupIdCounter = 0;

        function addFieldsToMap(fieldsGeoJSON) {
            if (currentLayer) {
                map.removeLayer(currentLayer);
            }
            
            if (Object.keys(charts).length > 0) {
                for (var key in charts) {
                    if (charts[key]) {
                        charts[key].destroy();
                    }
                }
                charts = {};
            }
            popupIdCounter = 0;

            currentLayer = L.geoJSON(fieldsGeoJSON, {
                style: getStyle,
                onEachFeature: function(feature, layer) {
                    var thisPopupId = 'popup-' + popupIdCounter++;
                    layer.bindPopup(function(props) {
                        return createPopup(feature.properties, thisPopupId);
                    }, {
                        maxWidth: 300,
                        minWidth: 260
                    });
                    layer.on('popupopen', function() {
                        initCharts(feature.properties, thisPopupId);
                    });
                    layer.on('popupclose', function() {
                        var popupId = thisPopupId;
                        setTimeout(function() {
                            if (charts[popupId + '-temp']) { charts[popupId + '-temp'].destroy(); delete charts[popupId + '-temp']; }
                            if (charts[popupId + '-rain']) { charts[popupId + '-rain'].destroy(); delete charts[popupId + '-rain']; }
                            if (charts[popupId + '-soil']) { charts[popupId + '-soil'].destroy(); delete charts[popupId + '-soil']; }
                        }, 100);
                    });
                }
            }).addTo(map);
            
            if (fieldsGeoJSON.features.length > 0) {
                map.fitBounds(currentLayer.getBounds());
            }
        }

        function showAllFields() {
            addFieldsToMap(allFieldData);
            document.getElementById('results-info').style.display = 'none';
        }

        document.getElementById('search-btn').addEventListener('click', function() {
            var address = document.getElementById('address-input').value.trim();
            var radiusMiles = parseInt(document.getElementById('radius-select').value);
            var statusEl = document.getElementById('search-status');
            var resultsEl = document.getElementById('results-info');
            
            if (!address) {
                statusEl.textContent = 'Please enter an address';
                statusEl.className = 'search-status error';
                return;
            }
            
            statusEl.textContent = 'Searching...';
            statusEl.className = 'search-status';
            document.getElementById('search-btn').disabled = true;
            resultsEl.style.display = 'none';
            
            var query = address + ', Oregon, USA';
            var url = 'https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(query) + '&limit=1';
            
            fetch(url)
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data && data.length > 0) {
                        var lat = parseFloat(data[0].lat);
                        var lon = parseFloat(data[0].lon);
                        
                        if (searchMarker) {
                            map.removeLayer(searchMarker);
                        }
                        searchMarker = L.marker([lat, lon]).addTo(map)
                            .bindPopup('Search location: ' + address).openPopup();
                        
                        var filteredFeatures = [];
                        for (var i = 0; i < allFieldData.features.length; i++) {
                            var feature = allFieldData.features[i];
                            var fieldLat = feature.properties.lat;
                            var fieldLon = feature.properties.lon;
                            var distance = haversineDistance(lat, lon, fieldLat, fieldLon);
                            
                            if (distance <= radiusMiles) {
                                feature.properties.distance_miles = distance;
                                filteredFeatures.push(feature);
                            }
                        }
                        
                        if (filteredFeatures.length > 0) {
                            var filteredGeoJSON = {
                                type: 'FeatureCollection',
                                features: filteredFeatures
                            };
                            addFieldsToMap(filteredGeoJSON);
                            
                            statusEl.textContent = 'Found location: ' + data[0].display_name;
                            statusEl.className = 'search-status success';
                            
                            resultsEl.textContent = 'Found ' + filteredFeatures.length + ' field' + (filteredFeatures.length !== 1 ? 's' : '') + ' within ' + radiusMiles + ' mile' + (radiusMiles !== 1 ? 's' : '');
                            resultsEl.style.display = 'block';
                        } else {
                            statusEl.textContent = 'No fields found within ' + radiusMiles + ' miles of that location. Try increasing the radius.';
                            statusEl.className = 'search-status error';
                            showAllFields();
                        }
                    } else {
                        statusEl.textContent = 'Address not found. Please try a different search (e.g., "Salem OR" or "Benton County Oregon").';
                        statusEl.className = 'search-status error';
                        showAllFields();
                    }
                })
                .catch(function(error) {
                    statusEl.textContent = 'Error: ' + error.message;
                    statusEl.className = 'search-status error';
                })
                .finally(function() {
                    document.getElementById('search-btn').disabled = false;
                });
        });

        document.getElementById('address-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('search-btn').click();
            }
        });

        showAllFields();
    </script>
</body>
</html>"""
    )

    with open(output_path, "w") as f:
        f.write(html_content)

    print(f"Created: {output_path}")
    print("Open this file in any web browser")
    print("Enter an Oregon address to search for nearby fields")


if __name__ == "__main__":
    create_map()
