# Field Map 6: Custom Polygon Analysis

_Implementation guide for user-drawn polygon field analysis with save/load capability_

---

## Overview

This document provides a complete implementation guide for creating `field_map_6.html`. The new version replaces the pre-loaded field dataset with user-drawn polygon analysis. Users draw a polygon on the map, click "Retrieve", and the page fetches soil, weather, and crop data for that area.

**Key assumption**: You're working from the local repository at `/workspaces/ag-skills-demo` with `field_map_5.html` as the base reference at `docs/assignment-02/field_map_5.html`.

---

## Starting Point

You have:

- `docs/assignment-02/field_map_5.html` - Complete working map with pre-loaded fields (34078 lines)
- `docs/assignment-02/field_map_5_backup.html` - Backup copy
- This design document

**Your task**: Create `docs/assignment-02/field_map_6.html` that:

1. Removes all pre-loaded field data (the 50 fields in `fieldData`)
2. Adds polygon drawing capability
3. Adds "Retrieve" to fetch data from APIs
4. Adds Save/Open JSON functionality
5. Reuses all display logic from field_map_5 for results

---

## Implementation Order

Follow this exact order. Some tasks depend on previous ones.

### Phase 1: Setup & Toolbar (Tasks 1-3)

### Phase 2: Polygon Drawing (Tasks 4-5)

### Phase 3: API Integration (Tasks 6-9)

### Phase 4: Display & File Operations (Tasks 10-13)

---

## Phase 1: Setup & Toolbar

### Task 1: Create field_map_6.html from field_map_5.html

**Action**: Copy field_map_5.html to field_map_6.html

```bash
cp /workspaces/ag-skills-demo/docs/assignment-02/field_map_5.html /workspaces/ag-skills-demo/docs/assignment-02/field_map_6.html
```

**What to remove from field_map_6.html**:

- Lines ~365-33500: The entire `fieldData` variable (all 50 field features with coordinates, weather, soil)
- Keep `elevationRanges` object (needed for DEM overlay display)

**What to verify exists**:

- Leaflet CSS/JS imports (lines 7-11)
- Chart.js import (line 12)
- All CSS from field_map_5 (sidebar, charts, elevation panel)

---

### Task 2: Add Dependencies

**In the `<head>` section**, after the existing imports, add:

```html
<!-- Leaflet.draw for polygon drawing -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
```

**Verification**: These should be added after the Leaflet CSS but before the `<style>` block.

---

### Task 3: Add Toolbar UI

**Location**: In the HTML body, after `<div id="container">` and before `<div id="sidebar">`

**Add this HTML**:

```html
<div id="toolbar">
  <button id="open-btn" onclick="document.getElementById('file-input').click()">Open</button>
  <button id="save-btn" onclick="saveResults()" disabled>Save</button>
  <span class="toolbar-divider"></span>
  <button id="draw-btn" onclick="enableDrawing()">Draw</button>
  <button id="retrieve-btn" onclick="retrieveData()" disabled>Retrieve</button>
  <button id="clear-btn" onclick="clearAll()" disabled>Clear</button>
</div>

<input type="file" id="file-input" accept=".json" style="display:none" onchange="loadFile(event)" />
```

**Add to CSS** (in the `<style>` block, after `#sidebar` styles):

```css
#toolbar {
  position: absolute;
  top: 10px;
  left: 364px;
  z-index: 1000;
  display: flex;
  gap: 8px;
  transition: left 0.3s ease;
}

#toolbar.sidebar-expanded {
  left: 546px;
}

#toolbar button {
  padding: 8px 14px;
  background: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}

#toolbar button:hover {
  background: #f0f0f0;
}

#toolbar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

#toolbar button.primary {
  background: #1b5e20;
  color: white;
  border-color: #1b5e20;
}

#toolbar button.primary:hover {
  background: #2e7d32;
}

.toolbar-divider {
  width: 1px;
  background: #ddd;
  margin: 0 4px;
}
```

**Key detail**: The `#toolbar` needs to adjust its `left` position when sidebar expands. You'll handle this in Task 11.

---

## Phase 2: Polygon Drawing

### Task 4: Initialize Leaflet.draw

**Location**: After map initialization (around line 303 in the original file)

**Add this JavaScript**:

```javascript
// Polygon drawing setup
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
  draw: {
    polygon: {
      allowIntersection: false,
      showArea: true,
      shapeOptions: {
        color: '#1b5e20',
        fillOpacity: 0.2,
      },
    },
    polyline: false,
    rectangle: false,
    circle: false,
    marker: false,
    circlemarker: false,
  },
  edit: {
    featureGroup: drawnItems,
    remove: true,
  },
});

// Add draw control but hide it initially (we control via button)
map.addControl(drawControl);
map.removeControl(drawControl);

map.on(L.Draw.Event.CREATED, function (e) {
  drawnItems.clearLayers();
  drawnItems.addLayer(e.layer);
  document.getElementById('retrieve-btn').disabled = false;
  document.getElementById('clear-btn').disabled = false;
  document.getElementById('draw-btn').textContent = 'Draw';
  map.fire('draw:cancel'); // Exit drawing mode
});
```

---

### Task 5: Add Toolbar Functions

**Add these JavaScript functions** (after the map initialization code):

```javascript
// ===== Toolbar Functions =====

function enableDrawing() {
  // Add draw control to enable polygon drawing
  map.addControl(drawControl);

  // Start polygon drawing
  new L.Draw.Polygon(map, drawControl.options.draw.polygon).enable();

  document.getElementById('draw-btn').textContent = 'Drawing...';
}

function clearAll() {
  drawnItems.clearLayers();
  document.getElementById('retrieve-btn').disabled = true;
  document.getElementById('clear-btn').disabled = true;
  clearDisplay();
}

function getPolygonGeoJSON() {
  var layers = drawnItems.getLayers();
  if (layers.length === 0) return null;

  return layers[0].toGeoJSON();
}

function getPolygonCentroid(geojson) {
  var coords = geojson.geometry.coordinates[0];
  var latSum = 0,
    lonSum = 0;
  coords.forEach(function (coord) {
    lonSum += coord[0];
    latSum += coord[1];
  });
  return {
    lat: latSum / coords.length,
    lon: lonSum / coords.length,
  };
}

function getPolygonAreaAcres(geojson) {
  // Use turf.js or simple calculation
  // For simplicity, use Leaflet's geodesic area
  var layer = drawnItems.getLayers()[0];
  if (!layer) return 0;

  var areaSqMeters = L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]);
  var areaAcres = areaSqMeters * 0.000247105; // sq meters to acres
  return areaAcres;
}
```

**Note**: You'll need to verify `L.GeometryUtil` is available or add a utility function.

---

## Phase 3: API Integration

### Task 6: Implement Data Retrieval

**Add this function** after the toolbar functions:

```javascript
// ===== Data Retrieval =====

var currentResults = null;

async function retrieveData() {
  var geojson = getPolygonGeoJSON();
  if (!geojson) {
    alert('Please draw a polygon first');
    return;
  }

  showLoading('Fetching data...');

  try {
    var centroid = getPolygonCentroid(geojson);
    var areaAcres = getPolygonAreaAcres(geojson);

    // Fetch all data in parallel
    var [soilData, weatherData, cropData] = await Promise.all([
      fetchSoilData(geojson),
      fetchWeatherData(centroid),
      fetchCropData(geojson),
    ]);

    // Combine results
    currentResults = {
      version: '1.0',
      created: new Date().toISOString(),
      geometry: geojson,
      area: {
        centroid: centroid,
        area_acres: areaAcres,
      },
      data: {
        cdl_crop: cropData.crop,
        crop_dominant_pct: cropData.percent,
        soil_muname: soilData.muname,
        soil_drainage: soilData.drainage,
        soil_clay_pct: soilData.clay,
        soil_sand_pct: soilData.sand,
        soil_silt_pct: soilData.silt,
        soil_om_pct: soilData.om,
        soil_ph: soilData.ph,
        soil_cec: soilData.cec,
        elevation_range: [centroid.lat * 10, centroid.lat * 10 + 10], // Placeholder - need DEM
        weather_avg_monthly: weatherData,
      },
    };

    displayResults(currentResults);
    document.getElementById('save-btn').disabled = false;
    hideLoading();
  } catch (error) {
    hideLoading();
    alert('Error fetching data: ' + error.message);
    console.error(error);
  }
}

function showLoading(message) {
  var loader = document.createElement('div');
  loader.id = 'loading-overlay';
  loader.innerHTML = '<div class="loading-content"><div class="spinner"></div><p>' + message + '</p></div>';
  document.body.appendChild(loader);
}

function hideLoading() {
  var loader = document.getElementById('loading-overlay');
  if (loader) loader.remove();
}
```

---

### Task 7: Fetch Weather Data (NASA POWER)

**Add this function**:

```javascript
async function fetchWeatherData(centroid) {
  // Use 5 years of historical data
  var endDate = new Date();
  var startDate = new Date();
  startDate.setFullYear(startDate.getFullYear() - 5);

  var startStr = startDate.toISOString().slice(0, 10).replace(/-/g, '');
  var endStr = endDate.toISOString().slice(0, 10).replace(/-/g, '');

  var url =
    'https://power.larc.nasa.gov/api/temporal/daily/point?' +
    'parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR' +
    '&community=AG' +
    '&longitude=' +
    centroid.lon +
    '&latitude=' +
    centroid.lat +
    '&start=' +
    startStr +
    '&end=' +
    endStr +
    '&format=JSON';

  var response = await fetch(url);
  if (!response.ok) throw new Error('Weather API error');

  var data = await response.json();

  // Process into monthly averages
  var temps = data.properties.parameter;
  var months = {};

  Object.keys(temps.T2M).forEach(function (date) {
    var month = parseInt(date.substring(4, 6)) - 1;
    if (!months[month]) {
      months[month] = { high: [], low: [], rain: [] };
    }
    months[month].high.push(temps.T2M_MAX[date]);
    months[month].low.push(temps.T2M_MIN[date]);
    months[month].rain.push(temps.PRECTOTCORR[date] / 25.4); // mm to inches
  });

  var avgHigh = [],
    avgLow = [],
    avgRain = [];
  for (var i = 0; i < 12; i++) {
    var m = months[i];
    if (m) {
      avgHigh.push(
        (
          m.high.reduce(function (a, b) {
            return a + b;
          }, 0) / m.high.length
        ).toFixed(1)
      );
      avgLow.push(
        (
          m.low.reduce(function (a, b) {
            return a + b;
          }, 0) / m.low.length
        ).toFixed(1)
      );
      avgRain.push(
        (
          m.rain.reduce(function (a, b) {
            return a + b;
          }, 0) / 5
        ).toFixed(2)
      );
    } else {
      avgHigh.push(0);
      avgLow.push(0);
      avgRain.push(0);
    }
  }

  return {
    avg_high_c: avgHigh.map(Number),
    avg_low_c: avgLow.map(Number),
    avg_rain_in: avgRain.map(Number),
  };
}
```

---

### Task 8: Fetch Soil Data (SSURGO)

**Add this function**:

```javascript
async function fetchSoilData(geojson) {
  // Convert GeoJSON to WKT for SSURGO query
  var coords = geojson.geometry.coordinates[0];
  var wkt =
    'POLYGON((' +
    coords
      .map(function (c) {
        return c[0] + ' ' + c[1];
      })
      .join(', ') +
    '))';

  var query = {
    query:
      'SELECT musym, muname, drainagecl, claytotal_r, sandtotal_r, silttotal_r, om_r, ph1_1e3_r, cec7_r ' +
      'FROM component (NOLOCK) ' +
      'JOIN legend (NOLOCK) ON legend.lkey = component.lkey ' +
      'JOIN mapunit (NOLOCK) ON mapunit.mukey = component.mukey ' +
      "WHERE ST_Intersects(mapunit.shape, ST_GeomFromText('" +
      wkt +
      "', 4326)) = 1 " +
      'ORDER BY component.comppct_r DESC LIMIT 1',
  };

  var response = await fetch('https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query),
  });

  if (!response.ok) {
    // Return placeholder data on error
    return getPlaceholderSoilData();
  }

  var data = await response.json();

  if (!data || !data.length || !data[0].length) {
    return getPlaceholderSoilData();
  }

  var row = data[0][0];
  return {
    muname: row.muname || 'Unknown',
    drainage: row.drainagecl || 'Unknown',
    clay: row.claytotal_r || 0,
    sand: row.sandtotal_r || 0,
    silt: row.silttotal_r || 0,
    om: row.om_r || 0,
    ph: row.ph1_1e3_r || 0,
    cec: row.cec7_r || 0,
  };
}

function getPlaceholderSoilData() {
  return {
    muname: 'Data unavailable',
    drainage: 'Unknown',
    clay: 0,
    sand: 0,
    silt: 0,
    om: 0,
    ph: 0,
    cec: 0,
  };
}
```

---

### Task 9: Fetch Crop Data (CDL)

**Add this function**:

```javascript
async function fetchCropData(geojson) {
  var coords = geojson.geometry.coordinates[0];
  var ring = coords.map(function (c) {
    return [c[1], c[0]];
  });
  // Close the ring
  ring.push(ring[0]);

  var geometry = JSON.stringify({
    rings: [ring],
    spatialReference: { wkid: 4326 },
  });

  var url =
    'https://nassgeodata.gmu.edu/arcgis/rest/services/CropScapeR28/MapServer/18/query?' +
    'geometry=' +
    encodeURIComponent(geometry) +
    '&geometryType=esriGeometryPolygon' +
    '&spatialRel=esriSpatialRelIntersects' +
    '&outFields=*' +
    '&returnGeometry=false' +
    '&f=json';

  try {
    var response = await fetch(url);
    if (!response.ok) throw new Error('CDL API error');

    var data = await response.json();

    if (!data.features || data.features.length === 0) {
      return { crop: 'No crop data', percent: 0 };
    }

    // Find dominant crop
    var crops = {};
    data.features.forEach(function (f) {
      var val = f.attributes.Value;
      var pct = f.attributes.Percent;
      if (val && pct > 0) {
        crops[val] = (crops[val] || 0) + pct;
      }
    });

    var dominant = Object.keys(crops).reduce(function (a, b) {
      return crops[a] > crops[b] ? a : b;
    });

    return {
      crop: getCropName(parseInt(dominant)),
      percent: Math.round(crops[dominant]),
    };
  } catch (e) {
    return { crop: 'Data unavailable', percent: 0 };
  }
}

function getCropName(code) {
  var crops = {
    24: 'Winter Wheat',
    27: 'Other Hay',
    36: 'Alfalfa',
    37: 'Other Hay/Non Alfalfa',
    43: 'Sweet Corn',
    44: 'Corn',
    45: 'Popcorn',
    61: 'Fallow',
    63: 'Forest',
    81: 'Clouds/No Data',
    82: 'Developed',
    83: 'Water',
    87: 'Wetlands',
  };
  return crops[code] || 'Unknown (Code: ' + code + ')';
}
```

---

## Phase 4: Display & File Operations

### Task 10: Display Results

**Add this function** - reuse display logic from field_map_5:

```javascript
function displayResults(results) {
  var data = results.data;

  // Build field properties object to match field_map_5 format
  var props = {
    field_id: 'Custom Polygon',
    area_acres: results.area.area_acres,
    cdl_crop: data.cdl_crop,
    crop_dominant_pct: data.crop_dominant_pct,
    soil_muname: data.soil_muname,
    soil_drainage: data.soil_drainage,
    soil_clay_pct: data.soil_clay_pct,
    soil_sand_pct: data.soil_sand_pct,
    soil_silt_pct: data.soil_silt_pct,
    soil_om_pct: data.soil_om_pct,
    soil_ph: data.soil_ph,
    soil_cec: data.soil_cec,
    weather_avg_monthly: data.weather_avg_monthly,
  };

  // Show in sidebar (reuse showFieldDetails logic)
  currentFieldId = 'custom';
  document.getElementById('sidebar').classList.add('expanded');

  // Update toolbar position
  document.getElementById('toolbar').classList.add('sidebar-expanded');

  var detailsPanel = document.getElementById('field-details');
  var contentDiv = document.getElementById('field-content');

  // Use the same createPopup function from field_map_5
  contentDiv.innerHTML = createPopup(props, 'custom-popup');
  detailsPanel.classList.add('visible');

  // Initialize charts (reuse from field_map_5)
  initCharts(props, 'custom-popup');
}
```

**Important**: The `createPopup` and `initCharts` functions already exist in field_map_5.html - they're being reused unchanged.

---

### Task 11: Update Sidebar Expansion Logic

**Modify the `showFieldDetails` function** (already exists in field_map_5) to also update toolbar position:

```javascript
function showFieldDetails(props) {
  currentFieldId = props.field_id;
  document.getElementById('sidebar').classList.add('expanded');

  // Also move toolbar when sidebar expands
  document.getElementById('toolbar').classList.add('sidebar-expanded');

  // ... rest of existing function
}
```

And modify `closeFieldDetails` to reset toolbar:

```javascript
function closeFieldDetails() {
  document.getElementById('sidebar').classList.remove('expanded');
  document.getElementById('toolbar').classList.remove('sidebar-expanded');
  // ... rest of existing function
}
```

---

### Task 12: Save to JSON

**Add this function**:

```javascript
function saveResults() {
  if (!currentResults) {
    alert('No results to save');
    return;
  }

  var json = JSON.stringify(currentResults, null, 2);
  var blob = new Blob([json], { type: 'application/json' });
  var url = URL.createObjectURL(blob);

  var a = document.createElement('a');
  a.href = url;
  a.download = 'field-data-' + new Date().toISOString().slice(0, 10) + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

---

### Task 13: Open/Load JSON

**Add this function**:

```javascript
function loadFile(event) {
  var file = event.target.files[0];
  if (!file) return;

  var reader = new FileReader();
  reader.onload = function (e) {
    try {
      var data = JSON.parse(e.target.result);

      // Validate structure
      if (!data.version || !data.geometry || !data.data) {
        throw new Error('Invalid file format');
      }

      // Recreate polygon on map
      var layer = L.geoJSON(data.geometry, {
        style: {
          color: '#1b5e20',
          fillOpacity: 0.2,
        },
      }).addTo(map);

      drawnItems.addLayer(layer);
      map.fitBounds(layer.getBounds());

      // Display results
      currentResults = data;
      displayResults(data);

      document.getElementById('save-btn').disabled = false;
      document.getElementById('retrieve-btn').disabled = false;
      document.getElementById('clear-btn').disabled = false;
    } catch (err) {
      alert('Error loading file: ' + err.message);
    }
  };
  reader.readAsText(file);

  // Reset file input
  event.target.value = '';
}
```

---

## Additional CSS

**Add loading overlay styles** to the CSS section:

```css
#loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-content {
  background: white;
  padding: 30px 50px;
  border-radius: 8px;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #1b5e20;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 15px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
```

---

## Testing Checklist

After implementation, verify each item:

- [ ] Page loads without errors
- [ ] Toolbar displays with all 5 buttons
- [ ] Clicking "Draw" enables polygon drawing
- [ ] User can draw a polygon on the map
- [ ] "Retrieve" button enables after polygon is drawn
- [ ] Clicking "Retrieve" shows loading indicator
- [ ] Data displays in sidebar after retrieval
- [ ] Charts (temperature, rainfall, soil) render correctly
- [ ] "Save" button becomes enabled after retrieval
- [ ] Clicking "Save" downloads a JSON file
- [ ] "Open" button allows loading the JSON file
- [ ] Loaded JSON recreates polygon and displays data
- [ ] "Clear" removes polygon and resets state
- [ ] Sidebar expands/collapses correctly
- [ ] Toolbar moves with sidebar expansion

---

## API Rate Limits & Notes

| API        | Rate Limit | Notes                                     |
| ---------- | ---------- | ----------------------------------------- |
| NASA POWER | 1 req/sec  | Use 5-year historical data in single call |
| SSURGO     | 5 req/sec  | Query by polygon geometry                 |
| CDL        | ~          | No strict limit, but be respectful        |

---

## Reference: Code to Reuse from field_map_5.html

These functions/components are already implemented and should be reused unchanged:

| Function              | Location (approx) | Purpose                          |
| --------------------- | ----------------- | -------------------------------- |
| `createPopup()`       | Line 33780        | Generate HTML for field details  |
| `initCharts()`        | Line 33914        | Initialize Chart.js charts       |
| `showFieldDetails()`  | Line 33700        | Display field details in sidebar |
| `closeFieldDetails()` | Line 33678        | Close field details              |
| `switchTab()`         | Line 33555        | Switch between chart tabs        |
| Elevation color logic | Various           | DEM overlay display              |

---

## Summary: Key Differences from field_map_5

| Aspect          | field_map_5          | field_map_6               |
| --------------- | -------------------- | ------------------------- |
| Field data      | Pre-loaded 50 fields | User-drawn polygon        |
| Retrieval       | Click field on map   | Click "Retrieve" button   |
| File operations | None                 | Save/Open JSON            |
| Map interaction | Click to select      | Draw polygon              |
| Data source     | Embedded in HTML     | APIs (POWER, SSURGO, CDL) |

---

## File Structure

After creation:

```
docs/assignment-02/
├── field_map_1.html          # Original
├── field_map_2.html          # With search
├── field_map_3.html          # Enhanced
├── field_map_4.html          # More data
├── field_map_5.html          # Current production
├── field_map_5_backup.html   # Backup
├── field_map_6.html          # NEW: Custom polygon
└── field_map_design_custom_polygon.md  # This document
```

---

## Next Step

Once this implementation is complete, test thoroughly and report any issues with API calls or display logic.

---

## Current Status (2026-03-04)

### Implementation Complete ✓

- `field_map_6.html` created from `field_map_5.html` base
- Polygon drawing via Leaflet.draw working
- Save/Open JSON functionality working
- Toolbar UI with Open, Save, Draw, Retrieve, Clear buttons

### Phase 1 & 2: Data Retrieval + DEM - COMPLETE ✓

**Completed fixes:**

- ✓ Added `fetchWithTimeout()` helper with configurable timeouts (30-60s)
- ✓ Fixed WKT string - changed `.join(',')` to `.join(', ')`
- ✓ Updated SQL pattern to use `SDA_Get_Mukey_from_intersection_with_WktWgs84()` function
- ✓ Added console logging throughout all fetch functions for debugging
- ✓ Extended crop codes mapping for Oregon crops
- ✓ Reordered functions so fetchWithTimeout is defined before use
- ✓ Added `fetchElevationRange()` - calls USGS 3DEP API for elevation at centroid
- ✓ Added `loadCustomDemOverlay()` - uses USGS WMS for elevation raster overlay
- ✓ Added `getPolygonBounds()` - calculates bounds from polygon coordinates
- ✓ Modified `toggleDemOverlay()` - handles custom polygons
- ✓ Updated `displayResults()` - stores elevation range and polygon geometry
- ✓ Updated `createPopup()` - shows DEM controls for custom polygons

### API Endpoint Status

| API         | Current Endpoint                                   | Status                         |
| ----------- | -------------------------------------------------- | ------------------------------ |
| NASA POWER  | `power.larc.nasa.gov/api/temporal/daily/point`     | Updated with timeout + logging |
| SSURGO/Soil | `sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest` | Fixed WKT + SQL pattern        |
| CDL/Crops   | `nassgeodata.gmu.edu/.../MapServer/18/query`       | Added timeout + logging        |

---

## Bug Tracker

| Date       | Bug Description                              | Fix Applied                                                                                                              | Status | Notes                                                                                 |
| ---------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------- |
| 2024-03-04 | Map blank, sidebar visible (no JS errors)    | Added `html, body { height: 100%; margin: 0; }` to CSS; Added `min-height: 0` to #map; Added tile loading debug handlers | Fixed  | Root cause was missing html/body height causing flex container to not render properly |
| 2024-03-04 | L.GeometryUtil not available in Leaflet core | Replaced with manual calculation                                                                                         | Fixed  | Implemented manual geodesic area calculation                                          |
| 2026-03-04 | WKT string missing space after comma         | Fixed - changed `.join(',')` to `.join(', ')`                                                                            | Fixed  | Coordinates now properly formatted                                                    |
| 2026-03-04 | No timeout on API fetch calls                | Added fetchWithTimeout helper with 30-60s timeouts                                                                       | Fixed  | All API calls now have timeout protection                                             |
| 2026-03-04 | No error logging in fetch functions          | Added console.log/error throughout                                                                                       | Fixed  | Can now debug issues in browser console                                               |
| 2026-03-04 | SQL pattern outdated                         | Changed to SDA_Get_Mukey_from_intersection_with_WktWgs84                                                                 | Fixed  | More efficient spatial query                                                          |
| 2026-03-04 | DEM functionality not implemented            | Added fetchElevationRange(), loadCustomDemOverlay() using USGS 3DEP WMS                                                  | Fixed  | Uses WMS tile layer for elevation overlay                                             |
