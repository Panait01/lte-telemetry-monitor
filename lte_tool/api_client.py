"""Cliente para conectarse a la API HS4 y obtener telemetría LTE."""

import hashlib
import logging
import random
import requests
from typing import Any, Dict, Optional

from .config import HS4_API_BASE_URL, HS4_PASSWORD, HS4_USERNAME
from .utils import parse_dbm

LOGGER = logging.getLogger(__name__)

API_ENDPOINT = f"{HS4_API_BASE_URL}/api.cgi" if HS4_API_BASE_URL else ""


class HS4ApiClient:
    """Client for HS4 LTE telemetry API."""

    def __init__(self, timeout: int = 10) -> None:
        if not HS4_API_BASE_URL:
            raise ValueError("HS4_API_BASE_URL is not configured")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Referer": f"{HS4_API_BASE_URL}/login.html",
                "Origin": HS4_API_BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _random_uid(length: int = 8) -> str:
        return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=length))

    def _post(self, params: Dict[str, Any], json_data: Dict[str, Any]) -> Optional[requests.Response]:
        try:
            return self.session.post(
                API_ENDPOINT + params.get("suffix", ""),
                json=json_data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            LOGGER.debug("API request failed: %s", exc)
            return None

    def authenticate(self) -> bool:
        """Authenticate to the HS4 API and keep the session available."""
        if not (HS4_USERNAME and HS4_PASSWORD):
            LOGGER.warning("HS4 credentials are not configured")
            return False

        uid = self._random_uid()
        try:
            self._post({"suffix": "?path=account&method=get_retrytimes_and_time&timeout=10"}, {"type": "admin"})
            rand_response = self._post(
                {"suffix": "?path=account&method=get_rand&timeout=10"},
                {"type": "admin", "user_id": uid},
            )
            if not rand_response:
                return False
            rand = rand_response.json().get("rand", "")
            password_hash = self._md5(rand + HS4_PASSWORD.lower())
            login_response = self._post(
                {"suffix": "?path=account&method=login&timeout=10"},
                {
                    "type": "admin",
                    "username": HS4_USERNAME,
                    "password": password_hash,
                    "user_id": uid,
                },
            )
            if not login_response:
                return False
            result = login_response.json().get("result")
            return result in (0, 3)
        except Exception as exc:
            LOGGER.debug("Authentication error: %s", exc)
            return False

    def fetch_eng_info(self) -> Optional[Dict[str, Any]]:
        """Fetch the modem engineering state and battery snapshot."""
        if not self.authenticate():
            LOGGER.warning("HS4 authentication failed")
            return None

        try:
            multicall = self.session.post(
                API_ENDPOINT + "?multicalls=1&timeout=20_=dashboard",
                json={
                    "requests": [
                        {"path": "cm", "method": "query_eng_info", "timeout": "8"},
                        {"path": "aoc", "method": "get_bat_info", "timeout": "3"},
                    ]
                },
                timeout=self.timeout,
            )
            multicall.raise_for_status()
            responses = multicall.json().get("responses", [])
            eng_wrap = responses[0].get("data", {}) if len(responses) > 0 else {}
            bat_data = responses[1].get("data", {}) if len(responses) > 1 else {}
            eng = eng_wrap.get("eng_info", {}).get("data", {})
            if not eng:
                raise ValueError("Empty engineering data")
            return {
                "plmn": eng.get("plmn", ""),
                "cell_id": eng.get("cell_id"),
                "pci": eng.get("pci"),
                "tac": eng.get("tac"),
                "ecgi": eng.get("ecgi", ""),
                "band": eng.get("band"),
                "dl_freq": eng.get("dl_freq", ""),
                "dl_bandwidth": eng.get("dl_bandwidth", ""),
                "dl_earfcn": eng.get("dl_earfcn"),
                "ul_earfcn": eng.get("ul_earfcn"),
                "operation_mode": eng.get("operation_mode", ""),
                "rsrp": eng.get("rsrp", ""),
                "rsrq": eng.get("rsrq", ""),
                "sinr": eng.get("sinr", ""),
                "rsrp_val": parse_dbm(eng.get("rsrp")),
                "rsrq_val": parse_dbm(eng.get("rsrq")),
                "sinr_val": parse_dbm(eng.get("sinr")),
                "tx_power": eng.get("tx_power"),
                "bateria": bat_data.get("capacity", "N/A"),
            }
        except Exception as exc:
            LOGGER.debug("Failed to fetch HS4 engineering info: %s", exc)
            return None
