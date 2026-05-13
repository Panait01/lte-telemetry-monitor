import logging
from typing import Dict, List, Tuple

LOGGER = logging.getLogger(__name__)

PLMNS_MX = {"334140", "334050", "334020", "334030", "33414", "33405", "33402", "33403"}


class Detector:
    """Analyze LTE telemetry readings and classify anomaly levels."""

    def __init__(self, learn_minutes: int = 10) -> None:
        self.learning = True
        self.learn_end = None
        self.alerts = 0
        self.reads = 0
        self.prev = None
        self.learn_duration = learn_minutes * 60
        from time import time

        self.learn_end = time() + self.learn_duration

    def analyze(self, data: Dict[str, object]) -> Tuple[str, str]:
        """Return alert level and descriptive message for a reading."""
        from time import time

        self.reads += 1
        if time() < self.learn_end:
            LOGGER.debug("Learning mode: recording new cell data")
            return "LEARN", "Collecting baseline telemetry data"

        self.learning = False
        level = "OK"
        messages: List[str] = []
        ecgi = str(data.get("ecgi", ""))
        rsrp = data.get("rsrp_val")
        sinr = data.get("sinr_val")
        band = data.get("band")
        plmn = str(data.get("plmn", ""))
        cell_id = data.get("cell_id")
        pci = data.get("pci")
        known = data.get("known_cell")

        if not known or (known and known[9] < 3):
            messages.append("New tower detected")
            if level == "OK":
                level = "WARN"

        if self.prev and rsrp is not None and self.prev.get("rsrp_val") is not None:
            prev_rsrp = self.prev.get("rsrp_val")
            if prev_rsrp > -140 and rsrp is not None:
                delta = rsrp - prev_rsrp
                if delta > 12:
                    messages.append("Signal spike detected")
                    level = "DANGER"

        if known and rsrp is not None and known[6] is not None and rsrp > known[6] + 12:
            messages.append("RSRP exceed historical average")
            level = "DANGER"

        if self.prev and band and self.prev.get("band") and self.prev["band"] > 10 and band <= 5:
            messages.append("Downshift in radio band")
            level = "CRITICAL"

        if self.prev and cell_id and pci and self.prev.get("pci") == pci and self.prev.get("cell_id") != cell_id:
            prev_rsrp = self.prev.get("rsrp_val") or rsrp
            if rsrp is not None and prev_rsrp is not None and rsrp - prev_rsrp > 8:
                messages.append("Cell ID changed with same PCI")
                level = "DANGER"

        if plmn and plmn not in PLMNS_MX:
            messages.append("Unknown PLMN detected")
            level = "CRITICAL"

        if sinr is not None and sinr < -5:
            messages.append("Low SINR")
            if level == "OK":
                level = "WARN"

        tx_power = data.get("tx_power")
        known_tp_max = known[13] if known and len(known) > 13 else None
        if tx_power is not None and known_tp_max is not None and tx_power > known_tp_max + 5:
            messages.append("TX power above historical maximum")
            if level == "OK":
                level = "WARN"
            if tx_power >= 23:
                level = "DANGER"

        battery = data.get("battery")
        prev_battery = self.prev.get("battery") if self.prev else None
        if battery not in (None, "N/A") and prev_battery not in (None, "N/A"):
            try:
                delta_bat = int(prev_battery) - int(battery)
                if delta_bat >= 5 and tx_power is not None and tx_power >= 20:
                    messages.append("Battery drop correlated with high TX power")
                    if level in ["OK", "WARN"]:
                        level = "DANGER"
            except (TypeError, ValueError):
                pass

        self.prev = data.copy()
        if level in ["DANGER", "CRITICAL"]:
            self.alerts += 1

        return level, " | ".join(messages) if messages else "Normal telemetry"
