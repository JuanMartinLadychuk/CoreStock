"""
configure_lan.py — CoreStack Pro v0.9
Configura el modo de red de esta instalación.

Ejecutar en cada PC antes de lanzar main.py:
    python configure_lan.py

Modos:
  server  → Esta PC tiene la base de datos SQLite.
             El servidor LAN se inicia automáticamente al abrir la app.
             Solo debe haber UNA PC en modo servidor por red.

  client  → Esta PC se conecta al servidor de otra PC.
             Necesitás la IP del servidor (ej: 192.168.1.10).
"""

import json
import pathlib
import socket
import sys

_BASE_DIR = pathlib.Path(__file__).parent
_NET_FILE = _BASE_DIR / "network.json"


def get_local_ip() -> str:
    """Detecta la IP local de esta PC en la red."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def show_current():
    if _NET_FILE.exists():
        try:
            cfg = json.loads(_NET_FILE.read_text(encoding="utf-8"))
            print(f"\n  Configuración actual: {_NET_FILE}")
            for k, v in cfg.items():
                print(f"    {k}: {v}")
        except Exception:
            print("  (error leyendo network.json)")
    else:
        print("  (sin configuración — se usará modo servidor por defecto)")


def configure_server(port: int = 5001, db_name: str = "corestack.db"):
    cfg = {
        "mode":        "server",
        "server_host": "0.0.0.0",
        "server_port": port,
        "db_path":     db_name,
    }
    _NET_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    local_ip = get_local_ip()
    print(f"""
✅  Modo SERVIDOR configurado.
    Puerto: {port}
    Base de datos: {db_name}
    IP de esta PC en la red: {local_ip}

    Los clientes deben configurarse con:
      server_host = {local_ip}
      server_port = {port}

    Tip: si tenés firewall en Windows, abrí el puerto TCP {port}
    en Firewall → Reglas de entrada → Nueva regla → Puerto.
""")


def configure_client(server_ip: str, port: int = 5001):
    cfg = {
        "mode":        "client",
        "server_host": server_ip,
        "server_port": port,
    }
    _NET_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"""
✅  Modo CLIENTE configurado.
    Servidor: {server_ip}:{port}

    Asegurate de que:
    1. La PC servidor esté encendida y con CoreStack abierto.
    2. Estén en la misma red (WiFi o cable).
    3. El firewall del servidor permita el puerto TCP {port}.
""")


def test_connection(server_ip: str, port: int):
    import urllib.request
    import urllib.error
    url = f"http://{server_ip}:{port}/ping"
    print(f"\n  Probando conexión a {url}...")
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        print(f"  ✅  Servidor encontrado: {data.get('msg','OK')}")
        return True
    except urllib.error.URLError as e:
        print(f"  ❌  Sin respuesta: {e}")
        return False


def main():
    print("=" * 55)
    print("  CoreStack Pro — Configuración de Red LAN")
    print("=" * 55)
    show_current()
    print()
    print("  ¿Cómo querés usar esta PC?")
    print("  [1] SERVIDOR  — tiene la base de datos (PC principal)")
    print("  [2] CLIENTE   — se conecta al servidor de otra PC")
    print("  [3] Probar conexión con servidor existente")
    print("  [4] Salir sin cambios")
    print()

    choice = input("  Elegí una opción [1-4]: ").strip()

    if choice == "1":
        print()
        port_str = input("  Puerto del servidor [5001]: ").strip() or "5001"
        db_name  = input("  Nombre del archivo DB [corestack.db]: ").strip() or "corestack.db"
        try:
            port = int(port_str)
        except ValueError:
            print("  Puerto inválido, usando 5001.")
            port = 5001
        configure_server(port, db_name)

    elif choice == "2":
        print()
        local_scan = input("  ¿Querés que detecte servidores CoreStack en la red? [s/N]: ").strip().lower()
        if local_scan == "s":
            _scan_network()

        server_ip = input("  IP del servidor (ej: 192.168.1.10): ").strip()
        if not server_ip:
            print("  IP requerida.")
            sys.exit(1)
        port_str = input("  Puerto [5001]: ").strip() or "5001"
        try:
            port = int(port_str)
        except ValueError:
            port = 5001

        ok = test_connection(server_ip, port)
        if not ok:
            resp = input("\n  El servidor no respondió. ¿Guardar igual? [s/N]: ").strip().lower()
            if resp != "s":
                print("  Cancelado.")
                sys.exit(0)
        configure_client(server_ip, port)

    elif choice == "3":
        print()
        if _NET_FILE.exists():
            try:
                cfg = json.loads(_NET_FILE.read_text(encoding="utf-8"))
                host = cfg.get("server_host", "127.0.0.1")
                port = int(cfg.get("server_port", 5001))
                if host == "0.0.0.0":
                    host = "127.0.0.1"
                test_connection(host, port)
            except Exception as e:
                print(f"  Error: {e}")
        else:
            ip = input("  IP a probar: ").strip()
            test_connection(ip, 5001)

    elif choice == "4":
        print("  Sin cambios.")
    else:
        print("  Opción inválida.")

    print()


def _scan_network():
    """Escaneo rápido de la subred local buscando servidores CoreStack."""
    import threading
    import urllib.request

    local_ip = get_local_ip()
    subnet   = ".".join(local_ip.split(".")[:3])
    print(f"\n  Escaneando {subnet}.1-254 en puerto 5001 (puede tardar ~15s)...")

    found = []
    lock  = threading.Lock()

    def _check(ip):
        try:
            url = f"http://{ip}:5001/ping"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=0.8) as r:
                data = json.loads(r.read())
            with lock:
                found.append((ip, data.get("msg", "")))
        except Exception:
            pass

    threads = []
    for i in range(1, 255):
        t = threading.Thread(target=_check, args=(f"{subnet}.{i}",), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=2)

    if found:
        print(f"\n  Servidores CoreStack encontrados:")
        for ip, msg in found:
            print(f"    → {ip}  ({msg})")
    else:
        print("  No se encontraron servidores activos en la red.")
    print()


if __name__ == "__main__":
    main()
