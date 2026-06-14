"""
paths.py - Resolucion de rutas para CoreStack Pro
==================================================
Funciona igual en modo desarrollo (python main.py) y compilado
con PyInstaller (CoreStackPro.exe).

REGLA DE ORO:
  - resource_path()  -> archivos EMPAQUETADOS de solo lectura
                         (temas de customtkinter, iconos, plantillas)
  - data_path()      -> archivos PERSISTENTES de lectura/escritura
                         (config.ini, base SQLite, exports)
  - logs_path()      -> archivos de log

Importa esto desde init_db.py, db.py, config.py, etc. en lugar
de armar rutas con __file__ a mano.
"""
import os
import sys


def is_frozen() -> bool:
    """True si estamos corriendo desde el .exe compilado por PyInstaller."""
    return getattr(sys, "frozen", False)


if is_frozen():
    # Carpeta donde el usuario descomprimio el ZIP (junto al .exe)
    APP_DIR = os.path.dirname(sys.executable)
    # Carpeta temporal donde PyInstaller descomprime los recursos embebidos
    _BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = APP_DIR


def resource_path(relative: str) -> str:
    """Ruta a un recurso empaquetado (solo lectura)."""
    return os.path.join(_BUNDLE_DIR, relative)


def data_path(relative: str = "") -> str:
    """
    Ruta a un archivo de DATOS persistente. Crea la carpeta 'data'
    junto al ejecutable si no existe.
    Ej: data_path("corestack.db") -> .../CoreStackPro/data/corestack.db
    """
    d = os.path.join(APP_DIR, "data")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, relative) if relative else d


def logs_path(relative: str = "") -> str:
    """Ruta a un archivo de log. Crea la carpeta 'logs' si no existe."""
    d = os.path.join(APP_DIR, "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, relative) if relative else d
