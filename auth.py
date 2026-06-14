"""
auth.py – Autenticación con SHA-256 (hashlib estándar de Python).

Por qué SHA-256 en lugar de bcrypt:
  · Sin dependencias externas en PyMEs con entornos controlados.
  · Velocidad suficiente para el volumen de usuarios de un comercio.
  · Compatible con todas las versiones de Python 3.x sin instalación extra.

Formato almacenado: "sha256:<hex_digest>" para identificar el algoritmo
en el futuro y permitir migraciones.
"""
import hashlib
import secrets
from db import execute_query
import api


def hash_password(password: str) -> str:
    """
    Hash SHA-256 con salt aleatorio de 16 bytes.
    Formato: sha256:<salt_hex>:<digest_hex>
    El salt garantiza que dos contraseñas iguales produzcan hashes distintos.
    """
    salt   = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"sha256:{salt}:{digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra el hash almacenado."""
    try:
        algo, salt, digest = stored_hash.split(":", 2)
        if algo != "sha256":
            return False
        return secrets.compare_digest(
            digest,
            hashlib.sha256((salt + password).encode("utf-8")).hexdigest(),
        )
    except ValueError:
        # Hash en formato antiguo sin salt (compatibilidad)
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash


def login(username: str, password: str) -> dict | None:
    """
    Intenta iniciar sesión.
    Devuelve dict del usuario con permisos cargados, o None.
    """
    row = execute_query(
        "SELECT u.idUser, u.username, u.password_hash, u.idRole, "
        "       u.full_name, r.name "
        "FROM users u JOIN roles r ON r.idRole = u.idRole "
        "WHERE u.username = %s AND u.active = 1",
        (username,), fetch="one",
    )
    if row and verify_password(password, row[2]):
        id_role     = row[3]
        permissions = api.get_user_permissions(id_role)
        return {
            "id":          row[0],
            "username":    row[1],
            "role_id":     id_role,
            "role_name":   row[5],
            "full_name":   row[4] or row[1],
            "permissions": permissions,
        }
    return None
