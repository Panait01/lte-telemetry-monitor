import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

LOGGER = logging.getLogger(__name__)

gps_data = {"lat": None, "lon": None, "acc": None, "ts": None}

GPS_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>GPS Telemetry Feed</title>
  <style>
    body{background:#07141f;color:#8ed0ff;font-family:Arial,Helvetica,sans-serif;padding:20px;text-align:center;}
    h2{margin-bottom:12px;}
    #status{margin-top:12px;color:#d0e9ff;}
    button{padding:10px 14px;border:none;border-radius:8px;background:#1f4d8e;color:#fff;cursor:pointer;font-size:14px;}
  </style>
</head>
<body>
  <h2>GPS Telemetry Feed</h2>
  <p>Allow location access and it will post coordinates to the local telemetry service.</p>
  <button onclick=\"startGps()\">Start GPS</button>
  <div id=\"status\">Waiting for location data...</div>
  <script>
    function sendGps(lat, lon, acc) {
      fetch('/gps?lat=' + lat + '&lon=' + lon + '&acc=' + acc).finally(() => {
        document.getElementById('status').innerHTML =
          'lat=' + lat.toFixed(6) + ', lon=' + lon.toFixed(6) + ', acc=' + acc.toFixed(0) + 'm';
      });
    }
    function startGps() {
      if (!navigator.geolocation) {
        document.getElementById('status').textContent = 'Geolocation not supported';
        return;
      }
      navigator.geolocation.watchPosition(
        position => sendGps(position.coords.latitude, position.coords.longitude, position.coords.accuracy),
        error => document.getElementById('status').textContent = 'GPS error: ' + error.message,
        {enableHighAccuracy:true, maximumAge:5000, timeout:15000}
      );
    }
  </script>
</body>
</html>"""


class GPSRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/gps":
            params = parse_qs(parsed.query)
            try:
                gps_data["lat"] = float(params["lat"][0])
                gps_data["lon"] = float(params["lon"][0])
                gps_data["acc"] = float(params["acc"][0])
                gps_data["ts"] = self.date_time_string()
                LOGGER.debug("Received GPS update: %s", gps_data)
            except Exception as exc:
                LOGGER.debug("Invalid GPS parameters: %s", exc)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(GPS_HTML.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


def start_gps_server(port: int = 8766) -> HTTPServer:
    server = HTTPServer(("", port), GPSRequestHandler)
    LOGGER.info("Starting GPS server on http://localhost:%s", port)
    return server
