import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

LOGGER = logging.getLogger(__name__)

PLMN_INFO = {
    "334140": ("BAIT / Altán", "#00ff88", "bait"),
    "334050": ("AT&T México", "#ff8800", "att"),
    "334020": ("Telcel", "#00aaff", "telcel"),
    "334030": ("Movistar MX", "#aa44ff", "movistar"),
    "33414": ("BAIT / Altán", "#00ff88", "bait"),
    "33405": ("AT&T México", "#ff8800", "att"),
    "33402": ("Telcel", "#00aaff", "telcel"),
    "33403": ("Movistar MX", "#aa44ff", "movistar"),
}


def _safe_range(bounds: Any) -> tuple[float, float, float, float]:
    if bounds and bounds[0] is not None:
        lat_min = bounds[0] - 1
        lat_max = bounds[1] + 1
        lon_min = bounds[2] - 1
        lon_max = bounds[3] + 1
    else:
        lat_min, lat_max = 14, 33
        lon_min, lon_max = -120, -85
    return lat_min, lat_max, lon_min, lon_max


def _format_towers(towers: List[Dict[str, Any]], public_mode: bool) -> tuple[List[Dict[str, Any]], str]:
    sidebar_html = ""
    result = []
    for i, tower in enumerate(towers):
        plmn = str(tower["plmn"])
        label, color, css = PLMN_INFO.get(plmn, (f"({plmn})", "#ff0044", "unknown"))
        lat = tower["lat"]
        lon = tower["lon"]
        gps_real = bool(tower["gps_count"] and lat is not None)
        tower_entry = {
            "id": i,
            "ecgi": tower["ecgi"],
            "operator": label,
            "color": color,
            "band": tower["band"],
            "cell_id": tower["cell_id"],
            "pci": tower["pci"],
            "rsrp_avg": round(tower["rsrp_avg"], 1) if tower["rsrp_avg"] is not None else 0,
            "rsrp_min": tower["rsrp_min"] or 0,
            "rsrp_max": tower["rsrp_max"] or 0,
            "seen": tower["seen_count"],
            "lat": round(lat, 6) if lat else None,
            "lon": round(lon, 6) if lon else None,
            "gps_real": gps_real,
            "primary": tower["seen_count"] > 10,
        }
        result.append(tower_entry)
        w = max(0, min(100, (((tower_entry["rsrp_avg"] or -120) + 120) / 30) * 100))
        gps_label = "📍 GPS real" if gps_real else "📐 No GPS"
        seen_label = "" if public_mode else f"Seen: {tower_entry['seen']} times<br>"
        sidebar_html += f"""
        <div class=\"tower-card {css}\" onclick=\"focusTower({i})\">
          <div class=\"tower-name\">{label} ···{tower_entry['ecgi'][-5:]}</div>
          <div class=\"tower-detail\">
            Cell ID: {tower_entry['cell_id']} | PCI: {tower_entry['pci']}<br>
            LTE band: {tower_entry['band']} | {gps_label}<br>
            {seen_label}RSRP: {tower_entry['rsrp_min']} / {tower_entry['rsrp_avg']} / {tower_entry['rsrp_max']} dBm
          </div>
          <div class=\"rsrp-bar-bg\">
            <div class=\"rsrp-bar-fill\" style=\"width:{w:.0f}%;background:{color}\"></div>
          </div>
        </div>"""
    return result, sidebar_html


def generate_map(data: Dict[str, Any], output_path: str, public_mode: bool = False) -> str:
    """Generate an interactive HTML map from telemetry database results."""
    bounds = data["bounds"]
    lat_min, lat_max, lon_min, lon_max = _safe_range(bounds)
    towers, sidebar_html = _format_towers(data["towers"], public_mode)
    route_points = [
        [round(row["lat"], 6), round(row["lon"], 6), row["rsrp"], row["alert_level"]]
        for row in data["route"]
        if row["lat"] is not None and row["lon"] is not None
    ]
    alerts = [
        {
            "ts": row["ts"][11:19],
            "level": row["alert_level"],
            "msg": (row["alert_msg"] or "")[:70],
            "lat": row["lat"],
            "lon": row["lon"],
        }
        for row in data["alerts"]
        if row["lat"] is not None and row["lon"] is not None
    ]

    if public_mode:
        import random as rnd

        fuzz = 0.004
        for tower in towers:
            if tower["lat"] and tower["lon"]:
                seed = int(tower["ecgi"], 16) if tower["ecgi"] else 0
                rnd.seed(seed)
                tower["lat"] = round(tower["lat"] + rnd.uniform(-fuzz, fuzz), 5)
                tower["lon"] = round(tower["lon"] + rnd.uniform(-fuzz, fuzz), 5)
            tower["seen"] = "—"
        for alert in alerts:
            alert["lat"] = round(alert["lat"] + rnd.uniform(-fuzz, fuzz), 5)
            alert["lon"] = round(alert["lon"] + rnd.uniform(-fuzz, fuzz), 5)
        route_points = []
        LOGGER.debug("Public export mode enabled: GPS path removed and coordinates obfuscated")

    if route_points:
        center_lat = sum(point[0] for point in route_points) / len(route_points)
        center_lon = sum(point[1] for point in route_points) / len(route_points)
        zoom = 15
    else:
        valid_towers = [t for t in towers if t["lat"] is not None and t["lon"] is not None]
        if valid_towers:
            center_lat = sum(t["lat"] for t in valid_towers) / len(valid_towers)
            center_lon = sum(t["lon"] for t in valid_towers) / len(valid_towers)
            zoom = 14
        else:
            center_lat, center_lon, zoom = 19.4326, -99.1332, 13

    period_start = data["stats"]["period_start"] or "—"
    period_end = data["stats"]["period_end"] or "—"
    try:
        period_start = datetime.fromisoformat(period_start).strftime("%d/%m %H:%M")
        period_end = datetime.fromisoformat(period_end).strftime("%d/%m %H:%M")
    except ValueError:
        period_start = period_end = "—"

    title = "LTE Telemetry Map"
    subtitle = f"LTE Network Analysis · {period_start} → {period_end}"
    if public_mode:
        subtitle = f"LTE Network Analysis · Public export · {period_start} → {period_end}"

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LTE Telemetry Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body{margin:0;font-family:Inter,system-ui,sans-serif;background:#0d1720;color:#d7e7ee;}
  #header{padding:16px;background:#0b1725;border-bottom:1px solid #163045;display:flex;align-items:center;gap:14px;}
  h1{font-size:18px;margin:0;color:#7ce3ff;}
  .subtitle{font-size:12px;color:#8fb8cb;}
  #main{display:flex;height:calc(100vh - 72px);overflow:hidden;}
  #sidebar{width:300px;background:#0c1825;border-right:1px solid #163248;overflow-y:auto;padding:14px;gap:12px;display:flex;flex-direction:column;}
  .panel{background:#102338;border:1px solid #1b3b5c;border-radius:10px;padding:12px;}
  .panel-title{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#72d5ff;margin-bottom:8px;}
  .stat-row{display:flex;justify-content:space-between;font-size:12px;color:#adcadf;margin-bottom:6px;}
  .stat-val{color:#e5f7ff;font-weight:700;}
  .tower-card{background:#122741;border:1px solid #1c4568;border-radius:8px;padding:10px;margin-bottom:10px;cursor:pointer;transition:transform .18s ease;}
  .tower-card:hover{transform:translateX(2px);}
  .tower-name{font-size:12px;font-weight:700;color:#8ee0ff;}
  .tower-detail{font-size:11px;line-height:1.6;color:#c4d8eb;}
  .rsrp-bar-bg{height:6px;background:#0d223a;border-radius:999px;margin-top:8px;}
  .rsrp-bar-fill{height:100%;border-radius:999px;}
  #map{flex:1;}
  .alert-item{font-size:11px;padding:8px;border-radius:8px;margin-bottom:8px;}
  .alert-ok{background:#0f2a18;border-left:4px solid #3ddc97;}
  .alert-warn{background:#30220f;border-left:4px solid #f5ae1d;}
  .alert-danger{background:#311b1f;border-left:4px solid #f05f60;}
  #legend{position:absolute;bottom:18px;right:18px;background:rgba(12,24,38,.94);border:1px solid #163047;border-radius:10px;padding:10px;font-size:11px;color:#a9c4d8;max-width:260px;}
  .leg-row{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
  .leg-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;}
</style>
</head>
<body>
<div id="header">
  <div>
    <h1>{TITLE}</h1>
    <div class="subtitle">{SUBTITLE}</div>
  </div>
</div>
<div id="main">
  <div id="sidebar">
    <div class="panel">
      <div class="panel-title">Summary</div>
      <div class="stat-row"><span>Total readings</span><span class="stat-val">{TOTAL_READINGS}</span></div>
      <div class="stat-row"><span>With GPS</span><span class="stat-val">{WITH_GPS}</span></div>
      <div class="stat-row"><span>Unique towers</span><span class="stat-val">{UNIQUE_TOWERS}</span></div>
      <div class="stat-row"><span>OK / Alerts</span><span class="stat-val">{OK_ALERTS}</span></div>
    </div>
    <div class="panel">
      <div class="panel-title">Detected towers</div>
      {SIDEBAR_HTML}
    </div>
    <div class="panel">
      <div class="panel-title">Anomalies</div>
      {ALERT_ITEMS}
    </div>
  </div>
  <div id="map"></div>
</div>
<div id="legend">
  <div class="leg-row"><div class="leg-dot" style="background:#00ff88"></div>BAIT / Altán</div>
  <div class="leg-row"><div class="leg-dot" style="background:#ff8800"></div>AT&T México</div>
  <div class="leg-row"><div class="leg-dot" style="background:#00aaff"></div>Telcel</div>
  <div class="leg-row"><div class="leg-dot" style="background:#aa44ff"></div>Movistar</div>
  <div class="leg-row"><div class="leg-dot" style="background:#ff4444"></div>Unknown / Alerts</div>
</div>
<script>
const map = L.map('map').setView([{CENTER_LAT}, {CENTER_LON}], {ZOOM});
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© OpenStreetMap'}).addTo(map);
const towers = {TOWERS_JSON};
const route = {ROUTE_JSON};
const alerts = {ALERTS_JSON};
const markers = [];
if(route.length > 1) {
  L.polyline(route.map(r => [r[0], r[1]]), {color:'#4488ff', weight:2, opacity:0.55, dashArray:'4,6'}).addTo(map);
  L.circleMarker([route[0][0], route[0][1]], {radius:5, color:'#00ff88', fillColor:'#00ff88', fillOpacity:1}).addTo(map).bindTooltip('Start');
  L.circleMarker([route[route.length-1][0], route[route.length-1][1]], {radius:5, color:'#ffaa00', fillColor:'#ffaa00', fillOpacity:1}).addTo(map).bindTooltip('End');
}
function rsrpRadius(r) { return r >= -90 ? 900 : r >= -100 ? 650 : r >= -110 ? 450 : 280; }
towers.forEach((tower, index) => {
  if (!tower.lat) { markers.push(null); return; }
  L.circle([tower.lat, tower.lon], {radius: rsrpRadius(tower.rsrp_avg), color: tower.color, fillColor: tower.color, fillOpacity:0.08, weight:1, dashArray:tower.primary ? null : '4,4'}).addTo(map);
  const size = tower.primary ? 20 : 14;
  const icon = L.divIcon({ html:`<div style="width:${size}px;height:${size}px;background:${tower.color};border-radius:50%;box-shadow:0 0 10px ${tower.color};border:2px solid ${tower.color}55;"></div>`, className:'', iconSize:[size,size], iconAnchor:[size/2,size/2] });
  const marker = L.marker([tower.lat,tower.lon], {icon}).addTo(map);
  marker.bindPopup(`
    <div style="background:#0b1624;color:#e1efff;font-family:Inter,system-ui,sans-serif;font-size:12px;padding:10px;min-width:200px;">
      <div style="color:${tower.color};font-weight:700;margin-bottom:6px;">${tower.operator}</div>
      <div><strong>ECGI:</strong> ${tower.ecgi}</div>
      <div><strong>Cell ID:</strong> ${tower.cell_id} | <strong>PCI:</strong> ${tower.pci}</div>
      <div><strong>Band:</strong> ${tower.band}</div>
      <div><strong>RSRP:</strong> ${tower.rsrp_avg} dBm</div>
      <div><strong>Range:</strong> ${tower.rsrp_min} / ${tower.rsrp_max} dBm</div>
      <div><strong>Seen:</strong> ${tower.seen}</div>
      <div style="margin-top:6px;color:#7eaacf;">${tower.gps_real ? '📍 GPS real' : '📐 No GPS'}</div>
    </div>
  `);
  markers.push(marker);
});
alerts.forEach(alert => {
  const icon = L.divIcon({ html:`<div style="width:12px;height:12px;background:#ff4444;border-radius:50%;box-shadow:0 0 8px rgba(255,68,68,0.9);border:2px solid rgba(255,68,68,0.6);"></div>`, className:'', iconSize:[12,12], iconAnchor:[6,6] });
  L.marker([alert.lat, alert.lon], {icon}).addTo(map).bindPopup(`
    <div style="background:#111d2e;color:#ffb7b7;font-family:Inter,system-ui,sans-serif;font-size:12px;padding:10px;max-width:220px;">
      <strong>${alert.level}</strong> ${alert.ts}<br>${alert.msg}
    </div>
  `);
});
function focusTower(id) {
  const tower = towers[id];
  if (!tower || !tower.lat) return;
  map.flyTo([tower.lat, tower.lon], 16, {duration:1.2});
  if (markers[id]) markers[id].openPopup();
}
</script>
</body>
</html>"""

    html = html.replace("{TITLE}", title)
    html = html.replace("{SUBTITLE}", subtitle)
    html = html.replace("{TOTAL_READINGS}", str(data["stats"]["total_readings"]))
    html = html.replace("{WITH_GPS}", str(data["stats"]["with_gps"]))
    html = html.replace("{UNIQUE_TOWERS}", str(data["stats"]["total_towers"]))
    html = html.replace("{OK_ALERTS}", str(data["stats"]["normal_readings"]) + " / " + str(data["stats"]["anomalies"]))
    html = html.replace("{SIDEBAR_HTML}", sidebar_html)
    html = html.replace("{ALERT_ITEMS}", "".join(
        f'<div class="alert-item {"alert-danger" if alert["level"] == "CRITICAL" else "alert-warn"}>[{alert["ts"]}] {alert["level"]}: {alert["msg"]}</div>'
        for alert in alerts
    ) or '<div class="alert-item alert-ok">✓ No alerts detected</div>'
    )
    html = html.replace("{CENTER_LAT}", str(center_lat))
    html = html.replace("{CENTER_LON}", str(center_lon))
    html = html.replace("{ZOOM}", str(zoom))
    html = html.replace("{TOWERS_JSON}", json.dumps(towers))
    html = html.replace("{ROUTE_JSON}", json.dumps(route_points))
    html = html.replace("{ALERTS_JSON}", json.dumps(alerts))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as html_file:
        html_file.write(html)

    LOGGER.info("Generated map file: %s", output_path)
    return output_path
