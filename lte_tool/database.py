"""SQLite storage for LTE telemetry readings and cell tower data."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


# =========================
# Database connection
# =========================


def connect_db(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection and enable row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn



# =========================
# Schema initialization
# =========================


def init_db(db_path: str) -> None:
    """Create readings and known_cells tables if they don't exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect_db(db_path)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            plmn TEXT,
            cell_id INTEGER,
            pci INTEGER,
            tac INTEGER,
            ecgi TEXT,
            band INTEGER,
            rsrp REAL,
            rsrq REAL,
            sinr REAL,
            alert_level TEXT,
            alert_msg TEXT,
            lat REAL,
            lon REAL,
            gps_acc REAL,
            tx_power REAL,
            dl_bandwidth TEXT,
            dl_earfcn INTEGER,
            battery INTEGER
        )""",
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS known_cells (
            ecgi TEXT PRIMARY KEY,
            plmn TEXT,
            cell_id INTEGER,
            pci INTEGER,
            tac INTEGER,
            band INTEGER,
            rsrp_avg REAL,
            rsrp_min REAL,
            rsrp_max REAL,
            seen_count INTEGER DEFAULT 1,
            first_seen TEXT,
            last_seen TEXT,
            tx_power_avg REAL,
            tx_power_max REAL
        )""",
    )
    conn.commit()
    conn.close()




# =========================
# Write operations
# =========================


def save_reading(db_path: str, data: Dict[str, Any], level: str, msg: str, gps_data: Dict[str, Any]) -> None:
    """Store a single telemetry reading with alert level and GPS coordinates."""
    conn = connect_db(db_path)
    c = conn.cursor()
    c.execute(
        """INSERT INTO readings
            (ts,plmn,cell_id,pci,tac,ecgi,band,rsrp,rsrq,sinr,alert_level,alert_msg,
             lat,lon,gps_acc,tx_power,dl_bandwidth,dl_earfcn,battery)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now().isoformat(),
            data.get("plmn"),
            data.get("cell_id"),
            data.get("pci"),
            data.get("tac"),
            data.get("ecgi"),
            data.get("band"),
            data.get("rsrp_val"),
            data.get("rsrq_val"),
            data.get("sinr_val"),
            level,
            msg,
            gps_data.get("lat"),
            gps_data.get("lon"),
            gps_data.get("acc"),
            data.get("tx_power"),
            data.get("dl_bandwidth"),
            data.get("dl_earfcn"),
            data.get("battery"),
        ),
    )
    conn.commit()
    conn.close()


def update_known_cell(db_path: str, data: Dict[str, Any]) -> None:
    """Update or insert a cell tower into known_cells based on new telemetry."""
    conn = connect_db(db_path)
    c = conn.cursor()
    ecgi = data.get("ecgi")
    rsrp = data.get("rsrp_val", -999)
    tx_power = data.get("tx_power")
    now = datetime.now().isoformat()
    row = c.execute(
        "SELECT rsrp_avg,rsrp_min,rsrp_max,seen_count,tx_power_avg,tx_power_max FROM known_cells WHERE ecgi=?",
        (ecgi,),
    ).fetchone()
    if row:
        avg, mn, mx, cnt, tp_avg, tp_max = row
        new_avg = (avg * cnt + rsrp) / (cnt + 1)
        if tx_power is not None:
            new_tp_avg = ((tp_avg or tx_power) * cnt + tx_power) / (cnt + 1)
            new_tp_max = max(tp_max or 0, tx_power)
        else:
            new_tp_avg, new_tp_max = tp_avg, tp_max
        c.execute(
            """UPDATE known_cells
                 SET rsrp_avg=?, rsrp_min=?, rsrp_max=?, seen_count=seen_count+1,
                     last_seen=?, tx_power_avg=?, tx_power_max=?
                 WHERE ecgi=?""",
            (new_avg, min(mn, rsrp), max(mx, rsrp), now, new_tp_avg, new_tp_max, ecgi),
        )
    else:
        c.execute(
            """INSERT INTO known_cells
                 (ecgi,plmn,cell_id,pci,tac,band,rsrp_avg,rsrp_min,rsrp_max,
                  first_seen,last_seen,tx_power_avg,tx_power_max)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ecgi,
                data.get("plmn"),
                data.get("cell_id"),
                data.get("pci"),
                data.get("tac"),
                data.get("band"),
                rsrp,
                rsrp,
                rsrp,
                now,
                now,
                tx_power,
                tx_power,
            ),
        )
    conn.commit()
    conn.close()




# =========================
# Read operations
# =========================


def get_known_cell(db_path: str, ecgi: str) -> Optional[sqlite3.Row]:
    """Retrieve historical data for a known cell tower by ECGI."""
    conn = connect_db(db_path)
    row = conn.execute("SELECT * FROM known_cells WHERE ecgi=?", (ecgi,)).fetchone()
    conn.close()
    return row


def total_known_cells(db_path: str) -> int:
    """Count how many unique towers have been detected."""
    conn = connect_db(db_path)
    result = conn.execute("SELECT COUNT(*) FROM known_cells").fetchone()[0]
    conn.close()
    return result



# =========================
# Analytics and exports
# =========================


def query_map_data(db_path: str) -> Dict[str, Any]:
    """Fetch all data needed to render an interactive map with statistics."""
    conn = connect_db(db_path)
    c = conn.cursor()

    # Get geographic bounds
    c.execute(
        "SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM readings WHERE lat IS NOT NULL AND lat != 0"
    )
    bounds = c.fetchone()

    # Apply default bounds if no GPS data exists
    min_lat = bounds[0] - 1 if bounds[0] else 14
    max_lat = bounds[1] + 1 if bounds[1] else 33
    min_lon = bounds[2] - 1 if bounds[2] else -120
    max_lon = bounds[3] + 1 if bounds[3] else -85

    # Compute statistics
    stats = {
        "total_readings": c.execute("SELECT COUNT(*) FROM readings").fetchone()[0],
        "total_towers": c.execute("SELECT COUNT(*) FROM known_cells WHERE ecgi != '0000000000000'").fetchone()[0],
        "with_gps": c.execute("SELECT COUNT(*) FROM readings WHERE lat IS NOT NULL AND lat != 0").fetchone()[0],
        "normal_readings": c.execute("SELECT COUNT(*) FROM readings WHERE alert_level = 'OK'").fetchone()[0],
        "anomalies": c.execute("SELECT COUNT(*) FROM readings WHERE alert_level IN ('DANGER','CRITICAL')").fetchone()[0],
        "period_start": c.execute("SELECT MIN(ts) FROM readings").fetchone()[0],
        "period_end": c.execute("SELECT MAX(ts) FROM readings").fetchone()[0],
    }

    # Fetch towers with averaged GPS position and RSRP statistics
    towers = c.execute(
        """SELECT k.ecgi, k.plmn, k.cell_id, k.pci, k.band,
                   k.rsrp_avg, k.rsrp_min, k.rsrp_max, k.seen_count,
                   AVG(r.lat) as lat, AVG(r.lon) as lon,
                   COUNT(r.lat) as gps_count
             FROM known_cells k
             LEFT JOIN readings r ON k.ecgi = r.ecgi
                AND r.lat BETWEEN ? AND ?
                AND r.lon BETWEEN ? AND ?
             WHERE k.ecgi != '0000000000000' AND k.plmn != '000000'
             GROUP BY k.ecgi
             ORDER BY k.seen_count DESC""",
        (min_lat, max_lat, min_lon, max_lon),
    ).fetchall()

    # Fetch GPS route points
    route = c.execute(
        """SELECT lat, lon, rsrp, sinr, alert_level, ts
             FROM readings
             WHERE lat BETWEEN ? AND ?
               AND lon BETWEEN ? AND ?
             ORDER BY id""",
        (min_lat, max_lat, min_lon, max_lon),
    ).fetchall()

    # Fetch anomaly events with coordinates
    alerts = c.execute(
        """SELECT ts, alert_level, alert_msg, lat, lon
             FROM readings
             WHERE alert_level IN ('DANGER','CRITICAL')
               AND lat BETWEEN ? AND ?
               AND lon BETWEEN ? AND ?
             ORDER BY id""",
        (min_lat, max_lat, min_lon, max_lon),
    ).fetchall()

    conn.close()

    return {
        "bounds": bounds,
        "stats": stats,
        "towers": towers,
        "route": route,
        "alerts": alerts,
    }
