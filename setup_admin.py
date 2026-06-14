"""
setup_admin.py — CoreStack Pro v0.9
Herramienta de consola para gestionar usuarios sin necesidad de abrir la app.

Uso:
    python setup_admin.py              → menú interactivo
    python setup_admin.py --list       → listar todos los usuarios
    python setup_admin.py --create     → crear usuario (flags opcionales)
    python setup_admin.py --reset-pw   → resetear contraseña
    python setup_admin.py --activate   → activar usuario
    python setup_admin.py --deactivate → desactivar usuario
"""

import hashlib
import sys
import argparse
import getpass

try:
    from db import execute_query, test_connection
except ImportError as e:
    print(f"\n  Error importando db.py: {e}")
    sys.exit(1)


# ── Helpers ────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _check_db():
    ok, msg = test_connection()
    if not ok:
        print(f"\n  Sin conexión a MySQL: {msg}")
        print("  Verificá que MySQL esté corriendo y que network.json sea correcto.\n")
        sys.exit(1)

def _get_roles() -> list:
    rows = execute_query(
        "SELECT idRole, name, is_system FROM roles ORDER BY idRole",
        fetch="all") or []
    return rows

def _get_users() -> list:
    rows = execute_query(
        "SELECT u.idUser, u.username, r.name, u.full_name, u.active "
        "FROM users u JOIN roles r ON r.idRole=u.idRole "
        "ORDER BY u.username",
        fetch="all") or []
    return rows

def _user_exists(username: str) -> bool:
    r = execute_query(
        "SELECT idUser FROM users WHERE username=%s",
        (username,), fetch="one")
    return r is not None

def _ask_password(label: str = "Contraseña") -> str:
    while True:
        pw1 = getpass.getpass(f"  {label}: ")
        pw2 = getpass.getpass(f"  Repetir {label.lower()}: ")
        if pw1 != pw2:
            print("  Las contraseñas no coinciden. Intentá de nuevo.\n")
            continue
        if len(pw1) < 4:
            print("  Mínimo 4 caracteres. Intentá de nuevo.\n")
            continue
        return pw1

def _pick_role(roles: list) -> int:
    print("\n  Roles disponibles:")
    for r in roles:
        system = " (sistema)" if r[2] else ""
        print(f"    [{r[0]}] {r[1]}{system}")
    while True:
        try:
            choice = int(input("\n  ID del rol: ").strip())
            if any(r[0] == choice for r in roles):
                return choice
            print("  ID inválido.")
        except ValueError:
            print("  Ingresá un número.")

def _divider():
    print("  " + "─" * 52)


# ── Acciones ───────────────────────────────────────────────────

def list_users():
    users = _get_users()
    if not users:
        print("\n  No hay usuarios registrados.\n")
        return
    print(f"\n  {'ID':<5} {'Usuario':<20} {'Rol':<18} {'Nombre':<22} {'Estado'}")
    _divider()
    for (uid, uname, role, fname, active) in users:
        estado = "✅ Activo" if active else "❌ Inactivo"
        print(f"  {uid:<5} {uname:<20} {role:<18} {(fname or '—'):<22} {estado}")
    print()


def create_user(username: str = "", full_name: str = "", role_id: int = 0):
    roles = _get_roles()
    if not roles:
        print("\n  No hay roles en la BD. ¿Importaste BD_CORESTACK.sql?\n")
        sys.exit(1)

    print("\n  ── Crear nuevo usuario ──────────────────────────────")

    if not username:
        username = input("  Nombre de usuario: ").strip()
    if not username:
        print("  El usuario no puede estar vacío.")
        return

    if _user_exists(username):
        print(f"\n  El usuario '{username}' ya existe.")
        overwrite = input("  ¿Resetear su contraseña en su lugar? [s/N]: ").strip().lower()
        if overwrite == "s":
            reset_password(username)
        return

    if not full_name:
        full_name = input("  Nombre completo (Enter para omitir): ").strip()

    if not role_id:
        role_id = _pick_role(roles)

    pw = _ask_password()

    execute_query(
        "INSERT INTO users (username, password_hash, idRole, full_name, active) "
        "VALUES (%s, %s, %s, %s, 1)",
        (username, _hash(pw), role_id, full_name or None))

    role_name = next((r[1] for r in roles if r[0] == role_id), str(role_id))
    print(f"\n  Usuario '{username}' creado con rol '{role_name}'.\n")


def reset_password(username: str = ""):
    if not username:
        list_users()
        username = input("  Usuario a modificar: ").strip()
    if not username:
        return

    if not _user_exists(username):
        print(f"\n  El usuario '{username}' no existe.\n")
        return

    pw = _ask_password("Nueva contraseña")
    execute_query(
        "UPDATE users SET password_hash=%s WHERE username=%s",
        (_hash(pw), username))
    print(f"\n  Contraseña de '{username}' actualizada.\n")


def set_active(username: str = "", active: bool = True):
    if not username:
        list_users()
        username = input("  Usuario: ").strip()
    if not username:
        return

    r = execute_query(
        "SELECT idUser FROM users WHERE username=%s",
        (username,), fetch="one")
    if not r:
        print(f"\n  El usuario '{username}' no existe.\n")
        return

    execute_query(
        "UPDATE users SET active=%s WHERE username=%s",
        (int(active), username))
    estado = "activado" if active else "desactivado"
    print(f"\n  Usuario '{username}' {estado}.\n")


# ── Menú interactivo ───────────────────────────────────────────

def interactive_menu():
    print("\n" + "=" * 56)
    print("  CoreStack Pro — Gestión de usuarios")
    print("=" * 56)

    _check_db()

    opciones = [
        ("1", "Listar usuarios",            list_users),
        ("2", "Crear usuario",               lambda: create_user()),
        ("3", "Resetear contraseña",         lambda: reset_password()),
        ("4", "Activar usuario",             lambda: set_active(active=True)),
        ("5", "Desactivar usuario",          lambda: set_active(active=False)),
        ("6", "Salir",                       None),
    ]

    while True:
        print()
        for num, label, _ in opciones:
            print(f"  [{num}] {label}")
        print()

        choice = input("  Opción: ").strip()
        fn = next((f for n, _, f in opciones if n == choice), None)

        if fn is None:
            if choice == "6":
                print("\n  Hasta luego.\n")
                break
            print("  Opción inválida.\n")
            continue

        try:
            fn()
        except KeyboardInterrupt:
            print("\n  Cancelado.\n")
        except Exception as e:
            print(f"\n  Error: {e}\n")


# ── Entry point ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CoreStack Pro — gestión de usuarios",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--list",       action="store_true", help="Listar usuarios")
    parser.add_argument("--create",     action="store_true", help="Crear usuario")
    parser.add_argument("--reset-pw",   action="store_true", help="Resetear contraseña")
    parser.add_argument("--activate",   action="store_true", help="Activar usuario")
    parser.add_argument("--deactivate", action="store_true", help="Desactivar usuario")
    parser.add_argument("--username",   type=str, default="", help="Nombre de usuario")
    parser.add_argument("--fullname",   type=str, default="", help="Nombre completo")
    parser.add_argument("--role-id",    type=int, default=0,  help="ID del rol")
    args = parser.parse_args()

    _check_db()

    if args.list:
        list_users()
    elif args.create:
        create_user(args.username, args.fullname, args.role_id)
    elif args.reset_pw:
        reset_password(args.username)
    elif args.activate:
        set_active(args.username, active=True)
    elif args.deactivate:
        set_active(args.username, active=False)
    else:
        # Sin flags → menú interactivo
        interactive_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelado por el usuario.\n")
        sys.exit(0)
