"""
neon_db.py – Capa de conexión a Neon Tech (PostgreSQL) para CoreStack Pro.
Usada EXCLUSIVAMENTE por ml_api.py (tablas ML).
El resto del sistema (XAMPP/MariaDB) no se toca.

Requiere:
    pip install psycopg2-binary

Configurar la connection string en neon_config.json
"""

import json
import re
import os
import threading
from pathlib import Path

NEON_DSN: str = ""
from paths import data_path
_CONFIG_FILE = Path(data_path("neon_config.json"))


def _load_config():
    global NEON_DSN
    if NEON_DSN:
        return
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            NEON_DSN = data.get("dsn", "")
        except Exception:
            pass
    # No lanzar excepción aquí — el error aparece en el primer query,
    # no al importar el módulo. Esto evita el crash al arrancar la app.


def save_neon_config(dsn: str):
    """Guarda la connection string en neon_config.json."""
    global NEON_DSN
    NEON_DSN = dsn.strip()
    _CONFIG_FILE.write_text(
        json.dumps({"dsn": NEON_DSN}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def get_neon_dsn() -> str:
    _load_config()
    return NEON_DSN


_local = threading.local()


def _get_conn():
    import psycopg2
    _load_config()
    if not NEON_DSN:
        raise RuntimeError(
            "Neon no configurado.\n"
            "Guardá la connection string desde Configuracion → MercadoLibre → Neon DB."
        )
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(NEON_DSN, connect_timeout=15)
        conn.autocommit = False
        _local.conn = conn
    else:
        try:
            conn.isolation_level
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = psycopg2.connect(NEON_DSN, connect_timeout=15)
            conn.autocommit = False
            _local.conn = conn
    return conn


def execute_query_pg(sql: str, params=None, fetch: str = "none"):
    """
    Ejecuta una query en Neon PostgreSQL.
    fetch: "none" | "one" | "all" | "lastid"
    Para INSERT que necesitan el id generado usar fetch="lastid"
    y asegurarse que la query termina con RETURNING <col>.
    """
    # Backticks de MariaDB → nada (PG no los necesita, nombres no reservados)
    sql_pg = sql.replace("`", "")

    # CURDATE() → CURRENT_DATE
    sql_pg = sql_pg.replace("CURDATE()", "CURRENT_DATE")

    # DATE_ADD(NOW(), INTERVAL n HOUR) → NOW() + INTERVAL 'n hours'
    sql_pg = re.sub(
        r"DATE_ADD\(NOW\(\),\s*INTERVAL\s+(\d+)\s+HOUR\)",
        lambda m: f"(NOW() + INTERVAL '{m.group(1)} hours')",
        sql_pg
    )
    sql_pg = re.sub(
        r"DATE_ADD\((\w+),\s*INTERVAL\s+(\d+)\s+HOUR\)",
        lambda m: f"({m.group(1)} + INTERVAL '{m.group(2)} hours')",
        sql_pg
    )

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql_pg, params or ())
        if fetch == "one":
            row = cur.fetchone()
            conn.commit()
            return row
        elif fetch == "all":
            rows = cur.fetchall()
            conn.commit()
            return rows
        elif fetch == "lastid":
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        else:
            conn.commit()
            return None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        raise


def test_connection() -> tuple[bool, str]:
    try:
        row = execute_query_pg("SELECT version()", fetch="one")
        return True, f"OK: {row[0][:70]}"
    except Exception as e:
        return False, str(e)