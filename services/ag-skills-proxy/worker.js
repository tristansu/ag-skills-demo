/**
 * Cloudflare Worker: ag-skills-proxy
 *
 * Proxies API calls to bypass CORS restrictions for:
 * - CDL (Crop Data Layer) from USDA
 * - Satellite metrics (NDVI/NDRE/NDMI/EVI2) from Copernicus Data Space
 *
 * Deploy to: https://dash.cloudflare.com/
 * Worker name: ag-skills-proxy
 *
 * Endpoints:
 * - POST /cdl { lat, lon, year } -> { crop, percent, value }
 * - GET  /satellite/token -> { access_token, expires_in }
 * - POST /satellite/stats (with request body) -> Copernicus API response
 *
 * Environment Variables (optional - will use fallback credentials if not set):
 * - COPERNICUS_CLIENT_ID
 * - COPERNICUS_CLIENT_SECRET
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Handle preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // === /cdl endpoint ===
      if (path === '/cdl') {
        const body = await request.json();
        const { lat, lon, year } = body;

        // Convert WGS84 to Albers Equal Area (for USDA CropScape)
        const coords = wgs84ToAlbersEqualArea(lat, lon);
        const filename = year + '_tm_cdls.img';
        const targetUrl = `https://nassgeodata.gmu.edu/CropScape/GetCDLPixelValue?filename=${filename}&bandno=1&locx=${coords.x.toFixed(3)}&locy=${coords.y.toFixed(3)}`;

        const response = await fetch(targetUrl);
        const text = await response.text();

        // Parse "Value: X" or "Value = X" from response
        const valueMatch = text.match(/Value\s*[:=]\s*(\d+)/i);
        if (valueMatch) {
          const cdlValue = parseInt(valueMatch[1], 10);
          const cropName = getCropName(cdlValue);
          return new Response(
            JSON.stringify({ crop: cropName, percent: 100, value: cdlValue }),
            {
              headers: { ...corsHeaders, 'Content-Type': 'application/json' },
            }
          );
        }
        return new Response(
          JSON.stringify({ crop: 'No crop data', percent: 0 }),
          {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }

      // === /satellite/token endpoint ===
      if (path === '/satellite/token') {
        // Get credentials from environment variables (safer than hardcoded)
        const clientId =
          env.COPERNICUS_CLIENT_ID || 'sh-b7c9d9d1-9963-4f33-a0aa-0c8cffa4a246';
        const clientSecret =
          env.COPERNICUS_CLIENT_SECRET || 'cMwfrjg1uUVTUrXepNpR8pgiOiHKjDcL';

        const tokenUrl =
          'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token';
        const tokenBody = `grant_type=client_credentials&client_id=${encodeURIComponent(clientId)}&client_secret=${encodeURIComponent(clientSecret)}`;

        const response = await fetch(tokenUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: tokenBody,
        });

        if (!response.ok) {
          return new Response('Failed to get token', { status: 500 });
        }

        const data = await response.json();
        return new Response(
          JSON.stringify({
            access_token: data.access_token,
            expires_in: data.expires_in,
          }),
          {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }

      // === /satellite/stats endpoint ===
      if (path === '/satellite/stats') {
        // Get token from Authorization header or fetch new one
        const authHeader = request.headers.get('Authorization');
        let token = authHeader?.replace('Bearer ', '');

        if (!token) {
          // Fetch token if not provided
          const clientId =
            env.COPERNICUS_CLIENT_ID ||
            'sh-b7c9d9d1-9963-4f33-a0aa-0c8cffa4a246';
          const clientSecret =
            env.COPERNICUS_CLIENT_SECRET || 'cMwfrjg1uUVTUrXepNpR8pgiOiHKjDcL';

          const tokenUrl =
            'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token';
          const tokenBody = `grant_type=client_credentials&client_id=${encodeURIComponent(clientId)}&client_secret=${encodeURIComponent(clientSecret)}`;

          const tokenResponse = await fetch(tokenUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: tokenBody,
          });

          if (!tokenResponse.ok) {
            return new Response('Failed to get token', { status: 500 });
          }
          const tokenData = await tokenResponse.json();
          token = tokenData.access_token;
        }

        // Forward request to Copernicus Statistics API
        const requestBody = await request.json();
        const statsUrl = 'https://sh.dataspace.copernicus.eu/api/v1/statistics';

        const response = await fetch(statsUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(requestBody),
        });

        const data = await response.text();
        return new Response(data, {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      // Default: 404
      return new Response('Not Found', { status: 404 });
    } catch (e) {
      return new Response('Error: ' + e.message, { status: 500 });
    }
  },
};

// === Utility Functions ===

function wgs84ToAlbersEqualArea(lat, lon) {
  // Albers Equal Area projection parameters for contiguous US
  const a = 6378137.0; // WGS84 semi-major axis
  const e = 0.00669437999014; // WGS84 first eccentricity squared
  const lat1 = (29.5 * Math.PI) / 180; // Standard parallel 1
  const lat2 = (45.5 * Math.PI) / 180; // Standard parallel 2
  const lat0 = (23.0 * Math.PI) / 180; // Reference latitude
  const lon0 = (-96.0 * Math.PI) / 180; // Reference longitude

  const latRad = (lat * Math.PI) / 180;
  const lonRad = (lon * Math.PI) / 180;

  // Calculate n (azimuthal scale factor)
  const sinLat1 = Math.sin(lat1);
  const sinLat2 = Math.sin(lat2);
  const cosLat1 = Math.cos(lat1);
  const cosLat2 = Math.cos(lat2);
  const m1 = cosLat1 / Math.sqrt(1 - e * sinLat1 * sinLat1);
  const m2 = cosLat2 / Math.sqrt(1 - e * sinLat2 * sinLat2);

  const n =
    Math.log(m1 / m2) /
    Math.log(
      (Math.tan(Math.PI / 4 + lat2 / 2) *
        Math.sqrt((1 - e * sinLat2) / (1 + e * sinLat2))) /
        (Math.tan(Math.PI / 4 + lat1 / 2) *
          Math.sqrt((1 - e * sinLat1) / (1 + e * sinLat1)))
    );

  // Calculate F (false easting/northing factor)
  const F =
    m1 /
    (n *
      Math.pow(
        Math.tan(Math.PI / 4 + lat1 / 2) *
          Math.sqrt((1 - e * sinLat1) / (1 + e * sinLat1)),
        n
      ));

  // Calculate rho (radius to the point)
  const rho =
    a *
    F *
    Math.pow(
      Math.tan(Math.PI / 4 + latRad / 2) *
        Math.sqrt((1 - e * Math.sin(latRad)) / (1 + e * Math.sin(latRad))),
      n
    );
  const rho0 =
    a *
    F *
    Math.pow(
      Math.tan(Math.PI / 4 + lat0 / 2) *
        Math.sqrt((1 - e * Math.sin(lat0)) / (1 + e * Math.sin(lat0))),
      n
    );

  // Calculate x, y
  const x = rho * Math.sin(n * (lonRad - lon0));
  const y = rho0 - rho * Math.cos(n * (lonRad - lon0));

  return { x: x, y: y };
}

function getCropName(code) {
  const crops = {
    1: 'Corn',
    5: 'Soybeans',
    24: 'Winter Wheat',
    27: 'Other Hay',
    28: 'Spring Wheat',
    36: 'Alfalfa',
    37: 'Other Hay/Non Alfalfa',
    38: 'Small Grains',
    42: 'Forest',
    43: 'Fallow/Idle',
    44: 'Corn',
    45: 'Popcorn',
    59: 'Grass/Pasture',
    61: 'Fallow/Idle',
    63: 'Forest',
    74: 'Horticulture',
    75: 'Berries',
    81: 'Clouds/No Data',
    82: 'Developed',
    83: 'Water',
    87: 'Wetlands',
    121: 'Developed/Open Space',
    122: 'Developed/Low Intensity',
    141: 'Deciduous Forest',
    142: 'Evergreen Forest',
    143: 'Mixed Forest',
    176: 'Grassland/Herbaceous',
    190: 'Woody Wetlands',
    195: 'Herbaceous Wetlands',
    204: 'Christmas Trees',
    205: 'Other',
    206: 'Other',
    207: 'Forest',
    208: 'Forest',
    209: 'Mixed Forest',
    210: 'Developed',
    211: 'Open Water',
    212: 'No Data',
    213: 'Developed',
    214: 'Wetlands',
    215: 'Nonag',
    216: 'Shrubland',
    222: 'Clouds',
  };
  return crops[code] || 'Unknown (Code: ' + code + ')';
}
