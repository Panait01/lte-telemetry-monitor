import logging
from typing import Any, Optional


from typing import Any, Dict, Optional


def parse_dbm(value: Any) -> Optional[float]:
    """Parse a string like '-95 dBm' into a float value."""
    try:
        return float(str(value).split()[0])
    except (ValueError, TypeError):
        return None


def is_valid_telemetry_reading(data: Dict[str, Any]) -> bool:
    """Validate that a telemetry reading is a real cell lock and not an empty modem state."""
    if data is None:
        return False
    plmn = str(data.get("plmn", "")).strip()
    ecgi = str(data.get("ecgi", "")).strip()
    rsrp = data.get("rsrp_val")
    if not plmn or set(plmn) == {"0"}:
        return False
    if not ecgi or set(ecgi) == {"0"}:
        return False
    if rsrp is not None and rsrp <= -140:
        return False
    return True


def configure_logging(level: str = "INFO") -> None:
    """Configure the module-level logging settings."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
