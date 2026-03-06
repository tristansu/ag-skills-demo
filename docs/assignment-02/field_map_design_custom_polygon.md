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

## Current Status (2026-03-06)

### Implementation Complete ✓

- `field_map_6.html` created from `field_map_5.html` base
- Polygon drawing via Leaflet.draw working
- Save/Open JSON functionality working
- Toolbar UI with Open, Save, Draw, Retrieve, Clear buttons

### Phase 1 & 2: Data Retrieval + DEM - Initial implementation

**Initial fixes (commit 1-2):**

- ✓ Added `fetchWithTimeout()` helper with configurable timeouts (30-60s)
- ✓ Fixed WKT string - changed `.join(',')` to `.join(', ')`
- ✓ Updated SQL pattern to use `SDA_Get_Mukey_from_intersection_with_WktWgs84()` function
- ✓ Added console logging throughout all fetch functions for debugging
- ✓ Extended crop codes mapping for Oregon crops

### Phase 3: Comprehensive Fix Pass (2026-03-04)

All APIs were still non-functional after Phase 1-2. Root causes and fixes:

**SSURGO/Soil:**

- SQL used `LIMIT 1` (MySQL syntax) - SDA uses T-SQL, requires `SELECT TOP 1`
- Column name `ph1_1e3_r` does not exist - corrected to `ph1to1h2o_r`
- Removed `(NOLOCK)` hints and `legend` join (unnecessary complexity)
- Response parsing assumed `result[0][0]` object - SDA returns `{ Table: [[...]] }` array format
- Fixed to parse `result.Table[0]` as positional array

**NASA POWER Weather:**

- 5-year date range caused slow/timeout responses - reduced to 2 years
- No filtering of `-999` fill values (NASA POWER sentinel for missing data) - added filtering
- Rain divisor hardcoded as `/ 5` - changed to `/ numYears` variable
- No error handling - fetch could throw and kill all parallel requests
- Wrapped entire function in try/catch with zero-filled fallback

**CDL/CropScape:**

- Used ArcGIS MapServer query endpoint (`CropScapeR28/MapServer/18/query`) - this is not a public-facing API
- Switched to official CropScape `GetCDLStat` REST service at `nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLStat`
- Sends polygon as coordinate pairs with `points=` parameter and `format=json`
- Added fallback parsing for text/CSV responses (API sometimes returns non-JSON)

**DEM/Elevation:**

- `fetchElevationRange()` used non-existent `query` endpoint on ImageServer
- Switched to `identify` endpoint which returns pixel value at a point
- `loadCustomDemOverlay()` used `L.tileLayer.wms().setBounds()` - `setBounds()` does not exist on WMS tile layers
- Replaced with `L.imageOverlay()` using USGS 3DEP `exportImage` endpoint with `Hillshade Gray` rendering rule
- Fixed popup DEM controls to use `demFieldId='custom'` instead of display name `'Custom Polygon'`

### API Endpoint Status

| API         | Endpoint                                                              | Status                                |
| ----------- | --------------------------------------------------------------------- | ------------------------------------- |
| NASA POWER  | `power.larc.nasa.gov/api/temporal/daily/point`                        | Fixed: 2yr range, -999 filter, 60s TO |
| SSURGO/Soil | `sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest`                    | Fixed: TOP 1, column names, parsing   |
| CDL/Crops   | `nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLValue`           | Fixed: point query, year fallback     |
| Elevation   | `elevation.nationalmap.gov/.../3DEPElevation/ImageServer/identify`    | Fixed: proper identify endpoint       |
| DEM Overlay | `elevation.nationalmap.gov/.../3DEPElevation/ImageServer/exportImage` | Fixed: L.imageOverlay + Hillshade     |

---

## Bug Tracker

| Date       | Bug Description                              | Fix Applied                                                                                                              | Status  | Notes                                                                                 |
| ---------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------------- |
| 2024-03-04 | Map blank, sidebar visible (no JS errors)    | Added `html, body { height: 100%; margin: 0; }` to CSS; Added `min-height: 0` to #map; Added tile loading debug handlers | Fixed   | Root cause was missing html/body height causing flex container to not render properly |
| 2024-03-04 | L.GeometryUtil not available in Leaflet core | Replaced with manual calculation                                                                                         | Fixed   | Implemented manual geodesic area calculation                                          |
| 2026-03-04 | SSURGO SQL uses LIMIT 1 (invalid T-SQL)      | Changed to SELECT TOP 1; fixed column name ph1to1h2o_r; fixed response parsing for Table format                          | Fixed   | SDA uses SQL Server, not MySQL                                                        |
| 2026-03-04 | NASA POWER timeout / bad data                | Reduced to 2yr range; filter -999 values; dynamic rain divisor; try/catch fallback                                       | Fixed   | 5yr payload too large for browser fetch                                               |
| 2026-03-04 | CDL uses wrong API endpoint                  | Switched from ArcGIS MapServer to official GetCDLStat REST service                                                       | Fixed   | MapServer/18/query was not a public API                                               |
| 2026-03-04 | Elevation used non-existent query endpoint   | Changed to ImageServer/identify endpoint                                                                                 | Fixed   | Returns pixel value at point                                                          |
| 2026-03-04 | DEM overlay used L.tileLayer.wms.setBounds() | Replaced with L.imageOverlay using exportImage URL with Hillshade Gray                                                   | Fixed   | setBounds() does not exist on WMS layers                                              |
| 2026-03-04 | DEM toggle used wrong fieldId                | Fixed createPopup to use demFieldId='custom' for toggle/opacity                                                          | Fixed   | Was passing 'Custom Polygon' display name instead                                     |
| 2026-03-04 | switchTab function missing                   | Added switchTab(popupId, tabId) function from field_map_5                                                                | Fixed   | Rainfall and Soil chart tabs were unclickable                                         |
| 2026-03-04 | SDA POST returns 400 Bad Request             | Changed Content-Type to x-www-form-urlencoded with form body                                                             | Fixed   | SDA expects form-encoded POST, not JSON body                                          |
| 2026-03-04 | CropScape GetCDLStat blocked by CORS         | Switched to GetCDLValue point query at centroid with year fallback                                                       | Fixed   | CropScape REST API has no CORS headers                                                |
| 2026-03-04 | Orphaned code from old CDL implementation    | Removed dead parseCdlJsonResponse/parseCdlTextResponse functions                                                         | Fixed   | Caused syntax errors                                                                  |
| 2026-03-06 | Satellite stats parsing wrong path           | Fixed: data[0].outputs.NDVI.bands.B0.stats instead of data[0].NDVI.stats                                                 | Fixed   | Stats now display in sidebar                                                          |
| 2026-03-06 | Satellite grid/overlay not working           | Statistical API only returns stats, not pixel values. Planned fix: Switch to Process API with GeoTIFF output             | Planned | Need to implement GeoTIFF decode in browser                                           |

---

## New Features Implemented (March 2026)

### Satellite Metrics (NDVI, NDRE, NDMI, EVI2)

Implemented comprehensive satellite vegetation analysis using Copernicus Data Space:

**Features Added:**

1. **Metric Selection Dropdown** - Choose between:
   - NDVI (Vegetation Health)
   - NDRE (Nitrogen Content)
   - NDMI (Moisture Stress)
   - EVI2 (Vegetation Density)

2. **Custom Date Picker** - User selects date range:
   - From/To date inputs
   - Preset buttons: Last 30 days, 3 months, 6 months, 1 year
   - Default: Last 30 days

3. **Satellite Overlay** - Display vegetation metrics on map:
   - Color-coded heatmap overlay
   - Color scales per metric:
     - NDVI/EVI2: Brown → Yellow → Green (bare to dense vegetation)
     - NDRE: Brown → Yellow → Purple (low to high nitrogen)
     - NDMI: Red → White → Blue (dry to wet)
   - Opacity slider control
   - Toggle show/hide

4. **Sidebar Display** - Shows statistics for selected metric:
   - Mean, Min, Max values
   - Interpretation (e.g., "Dense Vegetation", "Moderate", etc.)

**Technical Implementation:**

- Uses Sentinel-2 L2A data via Copernicus Statistical API
- Custom evalscript calculates all 4 indices in single request
- Resolution: 20m (matches Sentinel-2 band resolution)
- Parallel batch fetching for DEM (12 concurrent requests)
- User-selectable DEM resolution: 5m, 10m, 50m, 100m, 500m, 1000m
- Progress bar with ETA during data collection
- Auto-reload DEM when resolution changes

### DEM Improvements

- Added EPQS (Elevation Point Query Service) as primary fallback
- Parallel batch fetching (12 concurrent requests)
- Progress bar during grid sampling
- User-selectable resolution with auto-reload
- Capped at 5000 points max for browser performance

---

## Current Issues & Limitations

### CDL (Crop Data Layer) - NOT WORKING

The USDA NASS CDL endpoint returns "Error: Failed to get value" for all requests:

```
CDL response: Error: Failed to get value.
CDL: all years failed
```

This is an API issue on the USDA side - the endpoint itself is broken, not a CORS or authentication issue.

### Copernicus Satellite - BLOCKED BY CORS

The Copernicus Data Space API calls are blocked by browser CORS policy:

```
Access to fetch at 'https://identity.dataspace.copernicus.eu/...'
from origin 'https://tristansu.github.io' has been blocked by CORS policy
No 'Access-Control-Allow-Origin' header is present
```

Attempted fix: Using corsproxy.io CORS proxy broke the entire app, not just satellite features.

---

## New Direction: Cloudflare Worker Proxy

To solve the CORS and API access issues, we are implementing a Cloudflare Worker proxy.

### Architecture

```
Browser (field_map_6.html)
    ↓ requests to
ag-skills-proxy.yourname.workers.dev
    ↓ (no CORS restrictions)
External APIs (USDA, Copernicus, etc.)
    ↓ returns data
Browser
```

### Benefits

1. **No CORS issues** - Server-to-server calls have no restrictions
2. **Credentials hidden** - API keys stored in Cloudflare secrets, not in browser
3. **Can cache results** - Reduce API calls for same data
4. **Free tier** - 100K requests/day on Cloudflare Workers

### Endpoints to Implement

| Endpoint           | Purpose             | External API               |
| ------------------ | ------------------- | -------------------------- |
| `/cdl`             | Crop type data      | USDA NASS (or alternative) |
| `/satellite/token` | Get OAuth token     | Copernicus Identity        |
| `/satellite/stats` | NDVI/NDRE/NDMI/EVI2 | Copernicus Statistical API |
| `/dem`             | Elevation data      | USGS (if needed)           |

### Implementation Status

- Cloudflare Worker not yet created
- Field_map_6.html has all the frontend code ready
- Need to update API calls to point to Worker endpoints instead of direct external APIs

---

## Satellite Overlay: Current Status & Fix Plan

### Problem Discovered (2026-03-06)

After debugging, we found that the Copernicus Statistical API returns aggregated statistics (`stats: {mean, min, max, stDev}`), NOT pixel grid values for display as an overlay.

**Console logs showing the issue:**

```
[Satellite] Raw response: {"data":[{"outputs":{"NDVI":{"bands":{"B0":{"stats":{"min":...,"mean":...,"max":...}}}}}}],"status":"OK"}
[SatelliteGrid] Raw response: {"data":[{"outputs":{"metric":{"bands":{"B0":{"stats":{...}}}}}}],"status":"OK"}
```

The `metricData.values` array that the code expects does NOT exist in the response - only `stats` exist.

### Root Cause

The code was using the **Statistical API** which is designed for aggregations. To get actual pixel data for visualization, we need the **Process API** with GeoTIFF output.

### Solution: Switch to Process API with GeoTIFF

**New Approach:**

1. Use Process API instead of Statistical API
2. Request `format: 'image/tiff'` instead of JSON
3. In browser: decode GeoTIFF binary → pixel array → render as overlay

### Implementation Status (2026-03-06)

| Task                            | Status                                       |
| ------------------------------- | -------------------------------------------- |
| Add geotiff.js                  | DONE - added to head                         |
| Update request body             | DONE - switched to Process API format        |
| Add decodeGeoTIFF function      | DONE                                         |
| **Worker fix for GeoTIFF**      | **TODO - worker still calls Statistics API** |
| **Debug 173-byte response**     | **TODO - need to fix worker first**          |
| **Date UI - single date**       | **TODO**                                     |
| **Checkbox state preservation** | **TODO**                                     |

### Current Issues Found (2026-03-06)

**Issue 1: Worker ignores image/tiff request**

The worker (`worker.js`) always calls `/api/v1/statistics` (Statistics API) regardless of what the frontend requests. It also:

- Doesn't forward the `Accept` header
- Returns content as text instead of binary
- Always sets `Content-Type: application/json`

**Console evidence:**

```
[SatelliteGrid] Received GeoTIFF, size: 173 bytes
[decodeGeoTIFF] ReferenceError: GeoTIFF is not defined
```

173 bytes is an error message (JSON), not a real GeoTIFF (~10-50KB for small grid).

**Issue 2: Date UI still shows range**

The popup HTML still has From/To inputs and preset buttons, but the backend now uses single date.

**Issue 3: Checkbox unchecks on refresh**

`displayResults()` regenerates the entire popup HTML, losing checkbox state.

### Fix Plan

#### Fix 1: Update worker.js

- Detect if `Accept: image/tiff` header is present
- Call Process API (`/api/v1/process`) instead of Statistics API
- Forward Accept header to Copernicus
- Return binary data with correct content type

#### Fix 2: Add fallback for GeoTIFF library

- Check if `window.GeoTIFF` exists before calling
- Show error message if library not available

#### Fix 3: Single date UI

- Replace From/To inputs with single date input
- Remove preset buttons

#### Fix 4: Preserve checkbox state

- Save checkbox state before `displayResults()`
- Restore after

---

### Updated Implementation Plan

#### Step 1: Add geotiff.js Library

Add to `<head>`:

```html
<script src="https://unpkg.com/geotiff@2.0.7/dist/geotiff.min.js"></script>
<script src="https://unpkg.com/lerc@2.0.0/LercDecode.min.js"></script>
```

#### Step 2: Change Request Body Format

**Remove** aggregation section (returns stats only):

```javascript
// REMOVE THIS:
aggregation: {
  timeRange: { from, to },
  aggregationInterval: { of: 'P1M' },  // Causes stats-only response
  evalscript: evalscript,
}
```

**Use** Process API directly with single date and GeoTIFF output:

```javascript
var requestBody = {
  input: {
    bounds: { geometry, crs: 'http://opengis.net/def/crs/EPSG/0/4326' },
    data: [
      {
        type: 'sentinel-2-l2a',
        dataFilter: {
          timeRange: {
            from: selectedDate + 'T00:00:00Z',
            to: selectedDate + 'T23:59:59Z',
          },
        },
      },
    ],
  },
  output: {
    width: gridCols,
    height: gridRows,
    responses: [{ identifier: 'metric', format: 'image/tiff' }],
  },
  evalscript: evalscript,
};
```

#### Step 3: Fetch as ArrayBuffer

```javascript
var response = await fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'image/tiff', // Request binary GeoTIFF
    Authorization: 'Bearer ' + token,
  },
  body: JSON.stringify(requestBody),
});
var arrayBuffer = await response.arrayBuffer();
```

#### Step 4: Decode GeoTIFF

```javascript
async function decodeGeoTIFF(arrayBuffer, gridCols, gridRows) {
  var tiff = await GeoTIFF.fromArrayBuffer(arrayBuffer);
  var image = await tiff.getImage();
  var rasterData = image.readRasters();
  var pixelData = rasterData[0];

  var grid = [];
  for (var row = 0; row < gridRows; row++) {
    var rowData = [];
    for (var col = 0; col < gridCols; col++) {
      var idx = row * gridCols + col;
      var value = pixelData[idx];
      if (value === -9999 || value === null || isNaN(value)) {
        rowData.push(null);
      } else {
        rowData.push(value);
      }
    }
    grid.push(rowData);
  }
  return grid;
}
```

#### Step 5: Change UI - Single Date Selector

Replace date range inputs with single date picker. User picks a date, we fetch the scene closest to that date (most recent).

#### Step 6: Update Response Parsing

Parse the decoded grid instead of expecting `.stats` object.

### Files to Modify

| File               | Changes                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| `field_map_6.html` | Add geotiff.js, update request format, add decode logic, single date UI |
| `worker.js`        | No changes needed - existing endpoint works                             |

### Implementation Status

| Task                          | Status                  |
| ----------------------------- | ----------------------- |
| Fix stats parsing             | ✓ DONE - commit 264d3d8 |
| Add geotiff.js                | TODO                    |
| Update request to Process API | TODO                    |
| Fetch as arraybuffer          | TODO                    |
| Decode GeoTIFF                | TODO                    |
| Single date UI                | TODO                    |
| Test overlay display          | TODO                    |

### Code Locations to Modify

- `field_map_6.html:16` - Add geotiff.js CDN
- `field_map_6.html:1108-1127` - Update evalscript
- `field_map_6.html:1175-1201` - Update request body (single date, no aggregation, image/tiff)
- `field_map_6.html:1204-1220` - Fetch as arraybuffer
- `field_map_6.html:1248-1260` - Replace with GeoTIFF decode
- `field_map_6.html:3100-3145` - Update UI: single date picker
- `field_map_6.html:2086-2103` - Update refresh function
