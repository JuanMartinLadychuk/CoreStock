"""
app_config.py - Configuracion persistente y editable de CoreStack Pro
=======================================================================
Crea/lee un archivo config.ini en la carpeta 'data' junto al ejecutable.
Esto permite que soporte tecnico cambie credenciales de DB, DSN de
Neon, etc. SIN recompilar el .exe -- solo edita el .ini con el
Bloc de notas y reinicia la app.

Uso:
    from app_config import load_config
    cfg = load_config()
    host = cfg.get("database", "host")
"""
import os
import configparser
from paths import data_path

CONFIG_FILE = data_path("config.ini")

_DEFAULTS = {
    "database": {
        "host": "localhost",
        "port": "3306",
        "user": "corestack",
        "password": "",
        "database": "corestack_pro",
    },
    "neon": {
        # Cadena de conexion PostgreSQL para el modulo MercadoLibre
        "dsn": "",
    },
    "app": {
        "ui_theme": "dark",
        "business_type": "ambos",
    },
}


def load_config() -> configparser.ConfigParser:
    """
    Carga config.ini. Si no existe, lo crea con valores por defecto
    (primer arranque tras descomprimir el ZIP).
    """
    cfg = configparser.ConfigParser()
    cfg.read_dict(_DEFAULTS)

    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE, encoding="utf-8")
    else:
        save_config(cfg)

    return cfg


def save_config(cfg: configparser.ConfigParser) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        cfg.write(f)


def get(section: str, key: str, fallback: str = "") -> str:
    cfg = load_config()
    return cfg.get(section, key, fallback=fallback)
