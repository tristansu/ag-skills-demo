#!/usr/bin/env python3
"""
Create an interactive web map showing field boundaries colored by crop type.

Input:  data/assignment-02b/fields_complete.geojson
Output: docs/assignment-02b/field_map_1.html

Features:
- Satellite basemap (ESRI World Imagery)
- Fields colored by crop type (Berries, Alfalfa, Christmas Trees)
- Popup with field details + weather summary
- Crop legend
"""

import json
from pathlib import Path

import geopandas as gpd


def create_map():
    input_path = Path('data/assignment-02b/fields_complete.geojson')
    output_path = Path('docs/assignment-02b/field_map_1.html')
    
    print(f'Loading {input_path}...')
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

    crop_colors = {"Berries": "#E91E63", "Alfalfa": "#4CAF50", "Christmas Trees": "#1B5E20"}

    html_content = (
        """<!DOCTYPE html>
<html>
<head>
    <title>Oregon Specialty Crop Fields</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        #container { display: flex; height: 100vh; }
        
        #sidebar {
            width: 280px;
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
    </style>
</head>
<body>
    <div id="container">
        <div id="sidebar">
            <h1>Specialty Crop Fields</h1>
            <p style="font-size: 0.8em; color: #666; margin-bottom: 20px;">Oregon & Northern California</p>
            
            <div class="panel">
                <h3>Crops</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: #E91E63;"></div>
                    <span>Berries (27)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4CAF50;"></div>
                    <span>Alfalfa (16)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #1B5E20;"></div>
                    <span>Christmas Trees (7)</span>
                </div>
            </div>
        </div>
        
        <div id="map"></div>
    </div>
    
    <script>
        var map = L.map('map').setView("""
        + str(center_lat)
        + ", "
        + str(center_lon)
        + """, 6);
        
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri',
            maxZoom: 19
        }).addTo(map);
        
        var fieldData = """
        + json.dumps(geojson_data)
        + """;
        
        var cropColors = """
        + json.dumps(crop_colors)
        + """;
        
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
        
        function createPopup(props) {
            var weather = props.weather_monthly || [];
            var avgRain = 'N/A', avgHigh = 'N/A', avgLow = 'N/A';
            
            if (weather.length > 0) {
                var totalRain = 0;
                var years = {};
                var sumHigh = 0, sumLow = 0;
                
                weather.forEach(function(m) {
                    totalRain += m.total_rain_in || 0;
                    years[m.year] = true;
                    sumHigh += m.avg_high_c || 0;
                    sumLow += m.avg_low_c || 0;
                });
                
                var numYears = Object.keys(years).length;
                avgRain = (totalRain / Math.max(numYears, 1)).toFixed(1);
                avgHigh = (sumHigh / weather.length).toFixed(1);
                avgLow = (sumLow / weather.length).toFixed(1);
            }
            
            var html = '<div style="min-width:200px;"><h4 style="color:#1B5E20;margin-bottom:10px;">' + (props.field_id || 'Unknown') + '</h4>';
            html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Crop:</span><span>' + (props.cdl_crop || 'N/A') + '</span></div>';
            html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Area:</span><span>' + (props.area_acres ? props.area_acres.toFixed(1) + ' acres' : 'N/A') + '</span></div>';
            
            if (props.soil_muname) {
                html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #eee;">';
                html += '<div style="font-size:0.85em;color:#1B5E20;font-weight:600;margin-bottom:8px;">Soil</div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Type:</span><span>' + props.soil_muname.substring(0,25) + '</span></div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Drainage:</span><span>' + (props.soil_drainage || 'N/A') + '</span></div>';
                html += '</div>';
            }
            
            if (weather.length > 0) {
                html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #eee;">';
                html += '<div style="font-size:0.85em;color:#1B5E20;font-weight:600;margin-bottom:8px;">Weather (Avg)</div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Annual Rain:</span><span>' + avgRain + ' in</span></div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Avg High:</span><span>' + avgHigh + '°C</span></div>';
                html += '<div style="display:flex;justify-content:space-between;margin:4px 0;"><span style="color:#666;">Avg Low:</span><span>' + avgLow + '°C</span></div>';
                html += '</div>';
            }
            
            html += '</div>';
            return html;
        }
        
        L.geoJSON(fieldData, {
            style: getStyle,
            onEachFeature: function(feature, layer) {
                layer.bindPopup(createPopup(feature.properties), {maxWidth: 300});
            }
        }).addTo(map);
        
        map.fitBounds(L.geoJSON(fieldData).getBounds());
    </script>
</body>
</html>"""
    )

    with open(output_path, "w") as f:
        f.write(html_content)

    print(f"Created: {output_path}")
    print("Open this file in any web browser")


if __name__ == "__main__":
    create_map()
