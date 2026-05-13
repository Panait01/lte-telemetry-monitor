"""Configuración principal del proyecto."""

import os
from pathlib import Path
from typing import Final

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


# Ruta base del proyecto
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent

# Ruta del archivo .env
ENV_PATH: Final[Path] = BASE_DIR / ".env"


# Cargar variables de entorno
if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_PATH, override=False)


# =========================
# Configuración HS4
# =========================

HS4_API_BASE_URL: Final[str] = os.getenv(
    "HS4_API_BASE_URL",
    "",
).rstrip("/")

HS4_USERNAME: Final[str] = os.getenv(
    "HS4_USERNAME",
    "",
)

HS4_PASSWORD: Final[str] = os.getenv(
    "HS4_PASSWORD",
    "",
)


# =========================
# Configuración local
# =========================

DATABASE_PATH: Final[str] = os.getenv(
    "DATABASE_PATH",
    str(BASE_DIR / "lte_telemetry.db"),
)

POLL_INTERVAL: Final[int] = int(
    os.getenv("POLL_INTERVAL", "8")
)

LEARN_MINUTES: Final[int] = int(
    os.getenv("LEARN_MINUTES", "10")
)

GPS_PORT: Final[int] = int(
    os.getenv("GPS_PORT", "8766")
)

WEB_PORT: Final[int] = int(
    os.getenv("WEB_PORT", "8765")
)

LOG_LEVEL: Final[str] = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()

MAP_OUTPUT_HTML: Final[str] = os.getenv(
    "MAP_OUTPUT_HTML",
    "lte_telemetry_map.html",
)
