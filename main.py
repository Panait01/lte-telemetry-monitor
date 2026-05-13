"""Punto de entrada por consola para LTE Telemetry & Network Analysis Tool."""

import argparse
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from lte_tool.api_client import HS4ApiClient
from lte_tool.config import (
    DATABASE_PATH,
    GPS_PORT,
    LEARN_MINUTES,
    LOG_LEVEL,
    MAP_OUTPUT_HTML,
    POLL_INTERVAL,
)
from lte_tool.database import (
    get_known_cell,
    init_db,
    query_map_data,
    save_reading,
    update_known_cell,
)
from lte_tool.detector import Detector
from lte_tool.map_generator import generate_map
from lte_tool.server import gps_data, start_gps_server
from lte_tool.utils import configure_logging, is_valid_telemetry_reading

LOGGER = logging.getLogger(__name__)


def run_collection(db_path: str, duration: Optional[int] = None) -> None:
    """Inicia la recolección de telemetría y guarda los datos en SQLite."""
    init_db(db_path)

    client = HS4ApiClient()
    detector = Detector(learn_minutes=LEARN_MINUTES)

    gps_server = start_gps_server(GPS_PORT)
    server_thread = threading.Thread(target=gps_server.serve_forever, daemon=True)
    server_thread.start()

    LOGGER.info("Panel GPS disponible en http://localhost:%s", GPS_PORT)

    start_time = time.time()

    try:
        while duration is None or time.time() - start_time < duration:
            data = client.fetch_eng_info()

            if not is_valid_telemetry_reading(data):
                LOGGER.debug(
                    "No se recibió una lectura válida; reintentando en %s segundos",
                    POLL_INTERVAL,
                )
                time.sleep(POLL_INTERVAL)
                continue

            ecgi = str(data.get("ecgi", ""))
            known = get_known_cell(db_path, ecgi)
            data["known_cell"] = known

            level, message = detector.analyze(data)

            save_reading(db_path, data, level, message, gps_data)
            update_known_cell(db_path, data)

            LOGGER.info("Lectura guardada: level=%s message=%s gps=%s", level, message, gps_data)
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        LOGGER.info("La recolección fue detenida por el usuario")
    finally:
        gps_server.shutdown()
        LOGGER.info("Servidor GPS detenido")


def run_map_generation(db_path: str, output_file: str, public_mode: bool = False) -> None:
    """Genera el mapa HTML a partir de los datos guardados en la base."""
    init_db(db_path)
    data = query_map_data(db_path)

    output_path = generate_map(data, output_file, public_mode=public_mode)
    LOGGER.info("Mapa generado correctamente: %s", output_path)

    webbrowser.open(f"file://{Path(output_path).resolve()}", new=2)


def main(argv: Optional[list[str]] = None) -> int:
    """Procesa los comandos de consola."""
    configure_logging(LOG_LEVEL)

    parser = argparse.ArgumentParser(
        description="LTE Telemetry & Network Analysis Tool"
    )
    parser.add_argument(
        "--db",
        default=DATABASE_PATH,
        help="Ruta del archivo SQLite",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Recolectar telemetría LTE y guardarla en la base de datos",
    )
    collect_parser.add_argument(
        "--duration",
        type=int,
        help="Tiempo en segundos para ejecutar la recolección",
    )

    map_parser = subparsers.add_parser(
        "map",
        help="Generar un mapa HTML interactivo desde la base de datos",
    )
    map_parser.add_argument(
        "--output",
        default=MAP_OUTPUT_HTML,
        help="Ruta del archivo HTML de salida",
    )
    map_parser.add_argument(
        "--public",
        action="store_true",
        help="Generar una versión pública, cuidando datos sensibles",
    )

    args = parser.parse_args(argv)

    if args.command == "collect":
        run_collection(args.db, getattr(args, "duration", None))
        return 0

    if args.command == "map":
        run_map_generation(args.db, args.output, public_mode=args.public)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
