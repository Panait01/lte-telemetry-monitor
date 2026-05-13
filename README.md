# LTE Telemetry & Network Analysis Tool

Herramienta en Python para recolectar telemetría LTE, guardar datos en SQLite, detectar cambios raros y generar mapas interactivos.

## Qué hace

- Se conecta a dispositivos LTE compatibles con HS4 por medio de su API
- Guarda las lecturas en una base de datos SQLite
- Detecta cambios o comportamientos extraños en señal, PLMN, banda y potencia
- Incluye un panel local para ver datos GPS
- Genera un mapa HTML interactivo con torres detectadas, ruta y alertas
- Puede exportar una versión pública que cuide la privacidad

## Estructura del proyecto

- `main.py` - punto de entrada desde consola
- `lte_tool/config.py` - configuración usando variables de entorno
- `lte_tool/api_client.py` - cliente para consultar la API HS4
- `lte_tool/database.py` - esquema y guardado en SQLite
- `lte_tool/detector.py` - reglas para detectar anomalías
- `lte_tool/map_generator.py` - creación del mapa HTML
- `lte_tool/server.py` - servidor local para GPS y panel
- `lte_tool/utils.py` - utilidades de validación y parseo

## Instalación

1. Copia `.env.example` y renómbralo como `.env`
2. Cambia los valores según tu host y credenciales HS4
3. Instala las dependencias:

```bash
cd github
python -m pip install -r requirements.txt
Uso
Iniciar la recolección de telemetría
python main.py collect --db telemetry.db

Esto abre el panel local de GPS en http://localhost:8766 y empieza a consultar la API de HS4 con el intervalo configurado.

Generar un mapa
python main.py map --db telemetry.db --output lte_telemetry_map.html
Generar un mapa público, sin datos sensibles
python main.py map --db telemetry.db --output lte_telemetry_map_public.html --public
Configuración

Puedes poner estos valores en .env o definirlos directamente en el entorno:

HS4_API_BASE_URL - URL base de la API HS4
HS4_USERNAME - usuario de la API
HS4_PASSWORD - contraseña de la API
DATABASE_PATH - ruta del archivo SQLite
POLL_INTERVAL - segundos entre cada consulta
LEARN_MINUTES - tiempo para aprender una línea base
GPS_PORT - puerto del servidor local GPS
WEB_PORT - puerto local reservado para la web
LOG_LEVEL - nivel de logs
MAP_OUTPUT_HTML - nombre del archivo HTML por defecto
Limitaciones
Se probó con endpoints y formatos de telemetría estilo HS4
La compatibilidad puede cambiar según chipset, firmware y versión de la API
El soporte GPS depende del navegador y requiere acceso local a http://localhost:8766
Esta herramienta es experimental y está pensada solo para análisis y visualización

