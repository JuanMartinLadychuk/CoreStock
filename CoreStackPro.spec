# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  CoreStackPro.spec
#  Spec de PyInstaller para CoreStack Pro v0.9
#
#  Genera dist/CoreStackPro/  (modo --onedir):
#    - arranca mas rapido que --onefile
#    - menos falsos positivos de antivirus
#    - ideal para "descomprimir y listo"
#
#  Requisitos antes de compilar:
#    - Crear carpeta "assets/" con icon.ico (256x256 recomendado)
#      Si todavia no tenes icono, comenta las dos lineas que
#      dicen icon="assets/icon.ico"
# ============================================================

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Recursos internos de CustomTkinter (temas .json, fuentes) ──
ctk_datas = collect_data_files("customtkinter")

# ── Modulos importados DINAMICAMENTE por string en main.py ─────
#    (FRAME_REGISTRY usa importlib.import_module(mod_name) y
#     PyInstaller no los detecta solo --> hay que listarlos a mano)
dynamic_frame_modules = [
    "dashboard",
    "pos",
    "inventory",
    "sales",
    "dispatch",
    "suppliers",
    "analytics",
    "categories",
    "config",
    "users",
    "roles",
    "email_suppliers",
    "about",
]

# ── Modulos propios usados por los frames pero no importados ───
#    directamente desde main.py ───────────────────────────────
internal_modules = [
    "mercadolibre",
    "ml_api",
    "ml_calendar",
    "api",
    "db",
    "neon_db",
    "theme",
    "widgets",
    "init_db",
    "afip",        # opcional (AFIP) - se importa al vuelo en config.py
    "paths",
    "app_config",
]

# ── Drivers / libs que PyInstaller suele no detectar bien ───────
#    (db.py usa sqlite3 (stdlib) + Flask para el servidor LAN;
#     psycopg2 es para neon_db.py / modulo ML)
extra_hidden = (
    collect_submodules("psycopg2")
    + collect_submodules("flask")
    + [
        "PIL._tkinter_finder",
        "tkinter",
        "sqlite3",
        "reportlab.graphics.barcode",
        "openpyxl",
        "pandas",
    ]
)

hidden_imports = dynamic_frame_modules + internal_modules + extra_hidden

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=ctk_datas + [
        ("assets", "assets"),   # iconos / logos propios (crear carpeta)
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CoreStackPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                     # sin ventana de consola negra
    icon="assets/icon.ico",            # comentar si todavia no hay icono
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CoreStackPro",
)
