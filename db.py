"""
db.py — CoreStack Pro v0.9
Capa de datos 100% SQLite + servidor LAN (Flask HTTP).

MODOS (network.json):
  "mode": "server"  → SQLite local + servidor HTTP en background (puerto 5001)
  "mode": "client"  → proxy HTTP al servidor del modo server en la red

Si network.json no existe → modo server automático con defaults.
"""

import json
import os
import re as _re
import sqlite3
import pathlib
import threading
import time
import urllib.request
import urllib.error

_BASE_DIR = pathlib.Path(__file__).parent
_NET_FILE = _BASE_DIR / "network.json"
_DB_FILE  = _BASE_DIR / "corestack.db"

# ── Configuración ──────────────────────────────────────────────
_CFG: dict = {}

def _load_cfg() -> dict:
    global _CFG
    if _CFG:
        return _CFG
    if _NET_FILE.exists():
        try:
            _CFG = json.loads(_NET_FILE.read_text(encoding="utf-8"))
        except Exception:
            _CFG = {}
    if not _CFG:
        _CFG = {
            "mode":        "server",
            "server_host": "0.0.0.0",
            "server_port": 5001,
            "db_path":     str(_DB_FILE),
        }
        _NET_FILE.write_text(
            json.dumps(_CFG, indent=2, ensure_ascii=False), encoding="utf-8")
    return _CFG

def get_mode() -> str:
    return _load_cfg().get("mode", "server").lower()

def get_server_url() -> str:
    cfg  = _load_cfg()
    host = cfg.get("server_host", "localhost")
    port = int(cfg.get("server_port", 5001))
    if host in ("0.0.0.0", ""):
        host = "127.0.0.1"
    return f"http://{host}:{port}"

def get_db_path() -> pathlib.Path:
    cfg = _load_cfg()
    p   = cfg.get("db_path", str(_DB_FILE))
    return pathlib.Path(p)


# ══════════════════════════════════════════════════════════════
#  ADAPTADOR SQL  MySQL → SQLite
#  Orden de transformaciones es crítico.
# ══════════════════════════════════════════════════════════════

def _adapt_sql(sql: str) -> str:
    # 1. Parámetros %s → ?
    sql = sql.replace("%s", "?")

    # 2. NOW() / CURDATE() — primero, antes que las funciones que los usan como arg
    sql = _re.sub(r'\bNOW\(\)', "CURRENT_TIMESTAMP", sql, flags=_re.IGNORECASE)
    sql = _re.sub(r'\bCURDATE\(\)', "DATE('now','localtime')", sql, flags=_re.IGNORECASE)

    # 3. DATE_ADD / DATE_SUB  (primer arg puede tener paréntesis anidados)
    def _date_fn(sql_str, fn_name, sign):
        result = []
        i = 0
        pat = _re.compile(r'\b' + fn_name + r'\s*\(', _re.IGNORECASE)
        while i < len(sql_str):
            m = pat.search(sql_str, i)
            if not m:
                result.append(sql_str[i:])
                break
            result.append(sql_str[i:m.start()])
            pos   = m.end()
            depth = 1
            start = pos
            # Extraer primer argumento respetando paréntesis anidados
            col_chars = []
            while pos < len(sql_str) and depth > 0:
                ch = sql_str[pos]
                if ch == '(' : depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
                elif ch == ',' and depth == 1:
                    pos += 1
                    break
                col_chars.append(ch)
                pos += 1
            col = ''.join(col_chars).strip()
            # Extraer INTERVAL n UNIT
            rest_match = _re.match(
                r'\s*INTERVAL\s+(\d+)\s+(\w+)\s*\)',
                sql_str[pos:], _re.IGNORECASE)
            if rest_match:
                n, u = rest_match.group(1), rest_match.group(2).upper()
                u2 = {"DAY":"days","MONTH":"months","YEAR":"years","HOUR":"hours"}.get(u,"days")
                result.append(f"DATE({col}, '{sign}{n} {u2}')")
                pos += rest_match.end()
            else:
                # No matcheó — dejar original
                result.append(m.group(0) + col)
            i = pos
        return ''.join(result)

    sql = _date_fn(sql, 'DATE_SUB', '-')
    sql = _date_fn(sql, 'DATE_ADD', '+')

    # 4. YEARWEEK — antes de YEAR/MONTH para evitar capturas parciales
    def _yw(m):
        inner = m.group(1).strip()
        return f"strftime('%Y%W',{inner})"
    sql = _re.sub(
        r"\bYEARWEEK\(([^,]+(?:\([^)]*\))?),\s*\d+\)",
        _yw, sql, flags=_re.IGNORECASE)

    # 5. MONTH / YEAR / DAY
    # El argumento puede ser un expr simple (col_name) o una función anidada
    # como DATE('now','localtime') que contiene paréntesis. Usamos una función
    # de extracción que respeta el balance de paréntesis.
    def _extract_arg(sql_str, fn_name, fmt):
        """Reemplaza fn_name(expr) → CAST(strftime(fmt, expr) AS INTEGER)
        soportando expresiones con paréntesis anidados."""
        result = []
        i = 0
        pattern = _re.compile(r'\b' + fn_name + r'\s*\(', _re.IGNORECASE)
        while i < len(sql_str):
            m = pattern.search(sql_str, i)
            if not m:
                result.append(sql_str[i:])
                break
            result.append(sql_str[i:m.start()])
            # Avanzar después del '(' de apertura
            pos   = m.end()
            depth = 1
            start = pos
            while pos < len(sql_str) and depth > 0:
                if sql_str[pos] == '(':
                    depth += 1
                elif sql_str[pos] == ')':
                    depth -= 1
                pos += 1
            inner = sql_str[start:pos-1]
            result.append(f"CAST(strftime('{fmt}',{inner}) AS INTEGER)")
            i = pos
        return ''.join(result)

    sql = _extract_arg(sql, 'MONTH', '%m')
    sql = _extract_arg(sql, 'YEAR',  '%Y')
    sql = _extract_arg(sql, 'DAY',   '%d')

    # 6. GROUP_CONCAT con ORDER BY / SEPARATOR
    sql = _re.sub(
        r"GROUP_CONCAT\(([^)]+?)\s+ORDER BY\s+[^)]+?SEPARATOR\s+['\"]([^'\"]+)['\"]\)",
        lambda m: f"GROUP_CONCAT({m.group(1).strip()}, '{m.group(2)}')",
        sql, flags=_re.IGNORECASE)

    # 7. ILIKE → LIKE
    sql = _re.sub(r'\bILIKE\b', 'LIKE', sql, flags=_re.IGNORECASE)

    return sql


# ══════════════════════════════════════════════════════════════
#  MODO SERVER — ejecución local SQLite
# ══════════════════════════════════════════════════════════════

_local = threading.local()

def _get_local_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        db   = get_db_path()
        conn = sqlite3.connect(str(db), check_same_thread=False, timeout=30)
        conn.row_factory = None
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return conn


def _exec_local(sql: str, params=None, fetch=None):
    """Ejecuta en SQLite local; maneja ON DUPLICATE KEY UPDATE."""
    sql_raw = sql.strip()

    # ON DUPLICATE KEY UPDATE → INSERT OR REPLACE
    odk = _re.sub(
        r'\s+ON DUPLICATE KEY UPDATE.*$', '',
        sql_raw, flags=_re.IGNORECASE | _re.DOTALL)
    if len(odk) < len(sql_raw):
        sql_raw = _re.sub(
            r'^INSERT\b', 'INSERT OR REPLACE',
            odk, count=1, flags=_re.IGNORECASE)

    adapted = _adapt_sql(sql_raw)
    params  = list(params) if params else []

    conn = _get_local_conn()
    try:
        cur = conn.execute(adapted, params)
        if fetch == "one":
            row = cur.fetchone()
            conn.commit()
            return row
        elif fetch == "all":
            rows = cur.fetchall()
            conn.commit()
            return rows
        else:
            conn.commit()
            return cur.lastrowid
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


# ══════════════════════════════════════════════════════════════
#  MODO CLIENT — proxy HTTP
# ══════════════════════════════════════════════════════════════

import json as _json

def _exec_remote(sql: str, params=None, fetch=None):
    url     = get_server_url() + "/query"
    payload = _json.dumps({
        "sql":    sql,
        "params": list(params) if params else [],
        "fetch":  fetch or "none",
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = _json.loads(r.read())
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"No se pudo conectar al servidor CoreStack en {get_server_url()}.\n"
            f"Verificá que el servidor esté iniciado y la IP sea correcta.\n"
            f"Error: {e}") from e
    if resp.get("error"):
        raise RuntimeError(resp["error"])
    return resp.get("result")


# ══════════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════════

def execute_query(sql: str, params=None, fetch: str | None = None):
    """
    Punto de entrada único. Compatible 100% con la API anterior.
    Rutea a SQLite local (server) o HTTP remoto (client).
    """
    if get_mode() == "client":
        return _exec_remote(sql, params, fetch)
    else:
        return _exec_local(sql, params, fetch)


def test_connection() -> tuple[bool, str]:
    try:
        if get_mode() == "client":
            url = get_server_url() + "/ping"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = _json.loads(r.read())
            return True, f"Servidor LAN OK — {data.get('msg','')}"
        else:
            conn = _get_local_conn()
            conn.execute("SELECT 1")
            return True, f"SQLite local OK — {get_db_path().name}"
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════
#  SERVIDOR LAN (Flask) — daemon thread
# ══════════════════════════════════════════════════════════════

_server_started = False
_server_lock    = threading.Lock()


def start_lan_server():
    """Inicia el servidor Flask LAN en background. Idempotente."""
    global _server_started
    with _server_lock:
        if _server_started:
            return
        if get_mode() != "server":
            return
        _server_started = True

    def _run():
        try:
            from flask import Flask, request, jsonify
        except ImportError:
            print("[CoreStack] Flask no instalado — servidor LAN no disponible.")
            return

        import logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        app = Flask("corestack_lan")

        @app.route("/ping")
        def ping():
            import socket
            return jsonify({"msg": f"CoreStack LAN @ {socket.gethostname()}"})

        @app.route("/query", methods=["POST"])
        def query():
            try:
                body   = request.get_json(force=True)
                sql    = body.get("sql", "")
                params = body.get("params", [])
                fetch  = body.get("fetch", "none")
                if fetch == "none":
                    fetch = None
                result = _exec_local(sql, params, fetch)
                if isinstance(result, list):
                    result = [list(r) for r in result]
                elif isinstance(result, tuple):
                    result = list(result)
                return jsonify({"result": result, "error": None})
            except Exception as e:
                return jsonify({"result": None, "error": str(e)}), 200

        cfg  = _load_cfg()
        host = cfg.get("server_host", "0.0.0.0")
        port = int(cfg.get("server_port", 5001))
        print(f"[CoreStack] Servidor LAN iniciado → {host}:{port}")
        app.run(host=host, port=port, threaded=True, use_reloader=False)

    t = threading.Thread(target=_run, name="CoreStack-LAN", daemon=True)
    t.start()
    time.sleep(0.4)


# Auto-arranque al importar en modo server
if get_mode() == "server":
    start_lan_server()
