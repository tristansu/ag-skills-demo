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
        console.log('[CDL] Converted coords:', coords);

        // Try multiple years (Axis2 only supports 1997-2019)
        const yearsToTry = [];
        if (year >= 1997 && year <= 2019) {
          yearsToTry.push(year);
        }
        // Add fallback years
        for (
          let y = Math.min(year, 2019);
          y >= 1997 && yearsToTry.length < 3;
          y--
        ) {
          if (!yearsToTry.includes(y)) yearsToTry.push(y);
        }

        for (const tryYear of yearsToTry) {
          // Try the older Axis2 web service endpoint
          const axis2Url = `http://nassgeodata.gmu.edu:8080/axis2/services/CDLService/GetCDLValue?year=${tryYear}&x=${coords.x.toFixed(3)}&y=${coords.y.toFixed(3)}`;
          console.log('[CDL] Trying year', tryYear, 'Axis2 URL:', axis2Url);

          try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);
            const axis2Response = await fetch(axis2Url, {
              signal: controller.signal,
            });
            clearTimeout(timeout);
            const axis2Text = await axis2Response.text();
            console.log('[CDL] Axis2 response:', axis2Text.substring(0, 300));

            // Check for error
            if (
              axis2Text.includes('faultstring') ||
              axis2Text.includes('Error:')
            ) {
              continue;
            }

            // Parse the Axis2 SOAP response - could be just a number or in a <return> tag
            let cdlValue = null;
            const returnMatch = axis2Text.match(
              /<return[^>]*>([^<]+)<\/return>/i
            );
            if (returnMatch && returnMatch[1]) {
              cdlValue = parseInt(returnMatch[1].trim(), 10);
            } else {
              // Maybe just a plain number?
              const plainMatch = axis2Text.match(/^(\d+)$/);
              if (plainMatch) cdlValue = parseInt(plainMatch[1], 10);
            }

            if (cdlValue !== null && !isNaN(cdlValue) && cdlValue > 0) {
              console.log('[CDL] Found value:', cdlValue, 'for year', tryYear);
              const cropName = getCropName(cdlValue);
              return new Response(
                JSON.stringify({
                  crop: cropName,
                  percent: 100,
                  value: cdlValue,
                  year: tryYear,
                }),
                {
                  headers: {
                    ...corsHeaders,
                    'Content-Type': 'application/json',
                  },
                }
              );
            }
          } catch (e) {
            console.log('[CDL] Year', tryYear, 'failed:', e.message);
          }
        }

        // Final fallback: Try CropScape endpoint
        const filename = year + '_tm_cdls.img';
        const targetUrl = `https://nassgeodata.gmu.edu/CropScape/GetCDLPixelValue?filename=${filename}&bandno=1&locx=${coords.x.toFixed(3)}&locy=${coords.y.toFixed(3)}`;
        console.log('[CDL] USDA URL:', targetUrl);

        try {
          const response = await fetch(targetUrl);
          const text = await response.text();
          console.log('[CDL] USDA raw response:', text.substring(0, 200));

          // Parse "Value: X" or "Value = X" from response
          const valueMatch = text.match(/Value\s*[:=]\s*(\d+)/i);
          if (valueMatch) {
            const cdlValue = parseInt(valueMatch[1], 10);
            console.log('[CDL] Found value:', cdlValue);
            const cropName = getCropName(cdlValue);
            return new Response(
              JSON.stringify({ crop: cropName, percent: 100, value: cdlValue }),
              {
                headers: { ...corsHeaders, 'Content-Type': 'application/json' },
              }
            );
          }
        } catch (e) {
          console.log('[CDL] CropScape failed:', e.message);
        }

        console.log('[CDL] No crop value found from any endpoint');
        return new Response(
          JSON.stringify({
            crop: 'No crop data',
            percent: 0,
          }),
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

        // Forward request to Copernicus - check if client wants JSON (stats) or image/tiff (process)
        const requestBody = await request.json();
        const acceptHeader = request.headers.get('Accept') || '';
        const isGeoTIFF = acceptHeader.includes('image/tiff');

        // Use Process API for images, Statistics API for stats
        const apiUrl = isGeoTIFF
          ? 'https://sh.dataspace.copernicus.eu/api/v1/process'
          : 'https://sh.dataspace.copernicus.eu/api/v1/statistics';

        console.log(
          '[Worker] Requesting:',
          isGeoTIFF ? 'Process API (GeoTIFF)' : 'Statistics API (JSON)'
        );

        const response = await fetch(apiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: acceptHeader,
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(requestBody),
        });

        if (isGeoTIFF) {
          // Return binary data for GeoTIFF
          const data = await response.arrayBuffer();
          const contentType =
            response.headers.get('Content-Type') || 'application/octet-stream';
          console.log(
            '[Worker] GeoTIFF response size:',
            data.byteLength,
            'bytes, content-type:',
            contentType
          );
          return new Response(data, {
            headers: {
              ...corsHeaders,
              'Content-Type': contentType,
              'Content-Length': data.byteLength,
            },
          });
        } else {
          // Return JSON for stats
          const data = await response.text();
          return new Response(data, {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }
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

  // Calculate n (azimuthal scale factor) - use intermediate vars to avoid parsing issues
  const logM1M2 = Math.log(m1 / m2);
  const tanLat2 = Math.tan(Math.PI / 4 + lat2 / 2);
  const sqrtLat2 = Math.sqrt(
    (1 - e * Math.sin(lat2)) / (1 + e * Math.sin(lat2))
  );
  const tanLat1 = Math.tan(Math.PI / 4 + lat1 / 2);
  const sqrtLat1 = Math.sqrt(
    (1 - e * Math.sin(lat1)) / (1 + e * Math.sin(lat1))
  );
  const n = logM1M2 / Math.log((tanLat2 * sqrtLat2) / (tanLat1 * sqrtLat1));

  // Calculate F (false easting/northing factor)
  const powTerm = Math.pow(tanLat1 * sqrtLat1, n);
  const F = m1 / (n * powTerm);

  // Calculate rho (radius to the point)
  const tanLatRad = Math.tan(Math.PI / 4 + latRad / 2);
  const sqrtLatRad = Math.sqrt(
    (1 - e * Math.sin(latRad)) / (1 + e * Math.sin(latRad))
  );
  const rho = a * F * Math.pow(tanLatRad * sqrtLatRad, n);

  const tanLat0 = Math.tan(Math.PI / 4 + lat0 / 2);
  const sqrtLat0 = Math.sqrt(
    (1 - e * Math.sin(lat0)) / (1 + e * Math.sin(lat0))
  );
  const rho0 = a * F * Math.pow(tanLat0 * sqrtLat0, n);

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
