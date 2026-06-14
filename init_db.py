"""
init_db.py — CoreStack Pro v0.9
Inicializa la base de datos SQLite desde cero.
Crea todas las tablas y carga los datos semilla.
Se puede ejecutar manualmente o se llama automáticamente
desde main.py si la DB no existe.

Uso:
    python init_db.py            → crea corestack.db con datos demo
    python init_db.py --reset    → borra y recrea desde cero
"""

import sqlite3
import pathlib
import sys
import hashlib

_BASE_DIR = pathlib.Path(__file__).parent
_DB_FILE  = _BASE_DIR / "corestack.db"


# ══════════════════════════════════════════════════════════════
#  SCHEMA SQLite (equivalente a BD_CORESTACK.sql)
# ══════════════════════════════════════════════════════════════

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── ROLES ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    idRole      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    DEFAULT NULL,
    is_system   INTEGER DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── PERMISOS POR ROL ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS role_permissions (
    idRole         INTEGER NOT NULL,
    permission_key TEXT    NOT NULL,
    enabled        INTEGER DEFAULT 0,
    PRIMARY KEY (idRole, permission_key),
    FOREIGN KEY (idRole) REFERENCES roles(idRole) ON DELETE CASCADE
);

-- ── USUARIOS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    idUser        INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    idRole        INTEGER NOT NULL DEFAULT 2,
    full_name     TEXT    DEFAULT NULL,
    active        INTEGER DEFAULT 1,
    salary        REAL    DEFAULT 0.00,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (idRole) REFERENCES roles(idRole)
);

-- ── PROVEEDORES ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    idSupplier INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier   TEXT    NOT NULL,
    city       TEXT    DEFAULT NULL,
    mail       TEXT    DEFAULT NULL,
    tel        TEXT    DEFAULT NULL,
    active     INTEGER DEFAULT 1
);

-- ── CATEGORÍAS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    name        TEXT NOT NULL PRIMARY KEY,
    description TEXT DEFAULT NULL,
    color       TEXT DEFAULT '#4fc3f7',
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── MÁRGENES POR CATEGORÍA ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS category_margins (
    category       TEXT NOT NULL PRIMARY KEY,
    margin_percent REAL NOT NULL DEFAULT 20
);

-- ── PRODUCTOS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    idProduct       INTEGER PRIMARY KEY AUTOINCREMENT,
    product         TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'Sin Categoría',
    cost_price      REAL    NOT NULL DEFAULT 0,
    price           REAL    NOT NULL,
    custom_margin   REAL    DEFAULT NULL,
    stock           INTEGER NOT NULL DEFAULT 0,
    idSupplier      INTEGER NOT NULL,
    barcode         TEXT    DEFAULT NULL UNIQUE,
    added_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    active          INTEGER DEFAULT 1,
    replacement_cost        REAL    DEFAULT NULL,
    replacement_updated_at  TEXT    DEFAULT NULL,
    FOREIGN KEY (idSupplier) REFERENCES suppliers(idSupplier)
);

-- ── VENTAS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sells (
    idSell         INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_type   TEXT    DEFAULT NULL,
    payment_method TEXT    DEFAULT NULL,
    total_amount   REAL    DEFAULT NULL,
    tax_rate       REAL    DEFAULT 21.00,
    tax_amount     REAL    DEFAULT 0.00,
    net_amount     REAL    DEFAULT 0.00,
    discount       REAL    DEFAULT 0.00,
    quantity       INTEGER NOT NULL DEFAULT 0,
    product_name   TEXT    DEFAULT NULL,
    created_at     TEXT    DEFAULT (datetime('now','localtime'))
);

-- ── DETALLE DE VENTAS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products_sells (
    idProduct_sell   INTEGER PRIMARY KEY AUTOINCREMENT,
    idSell           INTEGER NOT NULL,
    idProduct        INTEGER DEFAULT NULL,
    product_name     TEXT    DEFAULT NULL,
    cantidad_vendida INTEGER NOT NULL DEFAULT 1,
    unit_price       REAL    DEFAULT 0.00,
    subtotal         REAL    NOT NULL,
    cost_snapshot    REAL    DEFAULT 0.00,
    replacement_snapshot REAL DEFAULT 0.00,
    FOREIGN KEY (idSell)    REFERENCES sells(idSell)    ON DELETE CASCADE,
    FOREIGN KEY (idProduct) REFERENCES products(idProduct) ON DELETE SET NULL
);

-- ── CONFIGURACIÓN ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    setting_key   TEXT NOT NULL PRIMARY KEY,
    setting_value TEXT DEFAULT NULL
);

-- ── IMPUESTOS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxes (
    idTax       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    percent     REAL    NOT NULL,
    is_included INTEGER DEFAULT 1,
    active      INTEGER DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── AUDITORÍA IMPUESTOS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS tax_audit_log (
    idLog       INTEGER PRIMARY KEY AUTOINCREMENT,
    idTax       INTEGER DEFAULT NULL,
    old_percent REAL    DEFAULT NULL,
    new_percent REAL    DEFAULT NULL,
    is_included INTEGER DEFAULT NULL,
    action      TEXT    NOT NULL,
    idUser      INTEGER DEFAULT NULL,
    changed_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (idUser) REFERENCES users(idUser) ON DELETE SET NULL
);

-- ── AJUSTES DE INVENTARIO ────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_adjustments (
    idAdjustment INTEGER PRIMARY KEY AUTOINCREMENT,
    idProduct    INTEGER NOT NULL,
    old_stock    INTEGER NOT NULL,
    new_stock    INTEGER NOT NULL,
    reason       TEXT    DEFAULT NULL,
    idUser       INTEGER DEFAULT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (idProduct) REFERENCES products(idProduct),
    FOREIGN KEY (idUser)    REFERENCES users(idUser) ON DELETE SET NULL
);

-- ── SESIONES DE CAJA ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cash_sessions (
    idSession      INTEGER PRIMARY KEY AUTOINCREMENT,
    idUser         INTEGER NOT NULL,
    opened_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    closed_at      TEXT    DEFAULT NULL,
    opening_amount REAL    NOT NULL DEFAULT 0.00,
    closing_amount REAL    DEFAULT NULL,
    expected_cash  REAL    DEFAULT NULL,
    difference     REAL    DEFAULT NULL,
    notes          TEXT    DEFAULT NULL,
    status         TEXT    DEFAULT 'abierta' CHECK(status IN ('abierta','cerrada')),
    FOREIGN KEY (idUser) REFERENCES users(idUser)
);

-- ── INTENTOS MERCADOPAGO POINT ───────────────────────────────
CREATE TABLE IF NOT EXISTS mp_payment_intents (
    idIntent    INTEGER PRIMARY KEY AUTOINCREMENT,
    idSell      INTEGER DEFAULT NULL,
    intent_id   TEXT    DEFAULT NULL,
    amount      REAL    NOT NULL,
    status      TEXT    DEFAULT 'pending',
    device_id   TEXT    DEFAULT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── MÉTODOS DE PAGO ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payment_methods (
    idMethod       INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    commission_pct REAL    NOT NULL DEFAULT 0.0,
    commission_iva INTEGER DEFAULT 0,
    active         INTEGER DEFAULT 1,
    pos_label      TEXT    DEFAULT NULL
);

-- ── EGRESOS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expenses (
    idExpense    INTEGER PRIMARY KEY AUTOINCREMENT,
    description  TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    type         TEXT    NOT NULL DEFAULT 'variable',
    category     TEXT    DEFAULT 'General',
    expense_date TEXT    DEFAULT NULL,
    period_month INTEGER DEFAULT NULL,
    period_year  INTEGER DEFAULT NULL,
    notes        TEXT    DEFAULT NULL,
    idUser       INTEGER DEFAULT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (idUser) REFERENCES users(idUser) ON DELETE SET NULL
);

-- ── DEVOLUCIONES ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS returns (
    idReturn     INTEGER PRIMARY KEY AUTOINCREMENT,
    idSell       INTEGER DEFAULT NULL,
    idProduct    INTEGER DEFAULT NULL,
    product_name TEXT    NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    unit_price   REAL    DEFAULT 0.00,
    refund_amount REAL   DEFAULT 0.00,
    condition    TEXT    DEFAULT 'revendible',
    restock      INTEGER DEFAULT 0,
    reason       TEXT    DEFAULT NULL,
    idUser       INTEGER DEFAULT NULL,
    return_date  TEXT    DEFAULT (DATE('now','localtime')),
    FOREIGN KEY (idUser) REFERENCES users(idUser) ON DELETE SET NULL
);

-- ── HISTORIAL DE COTIZACIONES USD ────────────────────────────
CREATE TABLE IF NOT EXISTS currency_rates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_date   TEXT    NOT NULL UNIQUE,
    usd_oficial REAL    DEFAULT 0,
    usd_blue    REAL    DEFAULT 0,
    usd_mep     REAL    DEFAULT 0,
    usd_ccl     REAL    DEFAULT 0,
    source      TEXT    DEFAULT 'criptoya',
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── ÍNDICES ÚTILES ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sells_created    ON sells(created_at);
CREATE INDEX IF NOT EXISTS idx_products_active  ON products(active);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
"""


# ══════════════════════════════════════════════════════════════
#  DATOS SEMILLA
# ══════════════════════════════════════════════════════════════

def _seed(conn: sqlite3.Connection):
    cur = conn.cursor()

    # Roles
    cur.executemany(
        "INSERT OR IGNORE INTO roles (idRole,name,description,is_system) VALUES (?,?,?,?)",
        [
            (1, 'Administrador', 'Acceso total. No se puede eliminar.', 1),
            (2, 'Empleado',      'Acceso básico: ver y vender.',        1),
            (3, 'Cajero',        'Solo registrar ventas y ver stock.',   0),
            (4, 'Supervisor',    'Inventario y reportes sin config.',    0),
        ]
    )

    ALL_PERMS = [
        'ver_dashboard','ver_inventario','ver_ventas','ver_movimientos',
        'ver_proveedores','ver_emails','agregar_producto','editar_producto',
        'eliminar_producto','ver_precio_costo','editar_stock','aplicar_descuento',
        'registrar_venta','eliminar_venta','agregar_proveedor','editar_proveedor',
        'eliminar_proveedor','gestionar_usuarios','gestionar_roles',
        'ver_configuracion','editar_impuestos','ver_rendimientos','cargar_egresos',
        'ver_mercadolibre','editar_mercadolibre',
    ]
    PERMS_ADMIN = {p: 1 for p in ALL_PERMS}
    PERMS_EMP   = {p: 1 if p in ('ver_dashboard','ver_inventario','ver_ventas',
                                  'ver_movimientos','ver_proveedores','registrar_venta')
                   else 0 for p in ALL_PERMS}
    PERMS_CAJ   = {p: 1 if p in ('ver_dashboard','ver_inventario','ver_ventas',
                                  'registrar_venta')
                   else 0 for p in ALL_PERMS}
    PERMS_SUP   = {p: 1 if p in ('ver_dashboard','ver_inventario','ver_ventas',
                                  'ver_movimientos','ver_proveedores','ver_emails',
                                  'agregar_producto','editar_producto','ver_precio_costo',
                                  'editar_stock','aplicar_descuento','registrar_venta',
                                  'agregar_proveedor','editar_proveedor')
                   else 0 for p in ALL_PERMS}

    for id_role, perms in [(1, PERMS_ADMIN),(2, PERMS_EMP),(3, PERMS_CAJ),(4, PERMS_SUP)]:
        cur.executemany(
            "INSERT OR IGNORE INTO role_permissions (idRole,permission_key,enabled) VALUES (?,?,?)",
            [(id_role, k, v) for k, v in perms.items()])

    # Proveedores
    cur.executemany(
        "INSERT OR IGNORE INTO suppliers (idSupplier,supplier,city,mail,tel) VALUES (?,?,?,?,?)",
        [
            (1,'Femsa Argentina',     'CABA',           'ventas@femsa.com.ar', '1144556677'),
            (2,'Arcor SA',            'Cordoba',        'mayorista@arcor.com', '0351-445566'),
            (3,'Bimbo SRL',           'Pilar',          'pedidos@bimbo.com',   '1122334455'),
            (4,'Mondelez IT',         'General Pacheco','soporte@mondelez.com','1166778899'),
            (5,'Distribuidora Alsina','Lanus',          'alsina@distri.com',   '1133221100'),
        ]
    )

    # Categorías
    cur.executemany(
        "INSERT OR IGNORE INTO categories (name,color) VALUES (?,?)",
        [('Dulces','#ffa726'),('Salados','#4fc3f7'),('Agridulces','#ab47bc')]
    )

    # Márgenes
    cur.executemany(
        "INSERT OR IGNORE INTO category_margins (category,margin_percent) VALUES (?,?)",
        [('Dulces',25.0),('Salados',20.0),('Agridulces',22.0)]
    )

    # Productos demo
    cur.executemany(
        "INSERT OR IGNORE INTO products "
        "(idProduct,product,category,cost_price,price,custom_margin,stock,idSupplier,active) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, 'Coca Cola 500ml',    'Salados',    1240, 1488, None,  50, 1, 1),
            (2, 'Agua Villavicencio', 'Salados',     660,  792, None, 100, 1, 1),
            (3, 'Alfa Guaymallen',    'Dulces',      495,  619, None, 200, 2, 1),
            (4, 'Mogul Confitado',    'Dulces',      990, 1238, None,  80, 2, 1),
            (5, 'Bon o Bon',          'Dulces',      330,  413, None, 137, 2, 1),
            (6, 'Pan Lactal Bimbo',   'Salados',    2070, 2484, None,  20, 3, 1),
            (7, 'Mantecol 250g',      'Dulces',     1490, 1863, None,  40, 4, 1),
            (8, 'Oreo Original',      'Dulces',     1075, 1344, None,  60, 4, 1),
            (9, 'Cereal Mix',         'Agridulces',  745,  909, None,  25, 2, 0),
            (10,'Papas Lays',         'Salados',    1815, 2178, None,  25, 5, 1),
            (11,'Papas Blancas',      'Salados',      83,  100, 20.0, 10000, 5, 1),
        ]
    )

    # Configuración
    cur.executemany(
        "INSERT OR IGNORE INTO settings (setting_key,setting_value) VALUES (?,?)",
        [
            ('markup_percent',     '20'),
            ('tax_name',           'IVA'),
            ('tax_percent',        '21'),
            ('tax_included',       '1'),
            ('smtp_host',          ''),
            ('smtp_port',          '587'),
            ('smtp_user',          ''),
            ('smtp_password',      ''),
            ('smtp_from_name',     'CoreStack Pro'),
            ('company_name',       'Mi Negocio'),
            ('company_address',    ''),
            ('company_phone',      ''),
            ('company_cuit',       ''),
            ('company_email',      ''),
            ('low_stock_auto_email','0'),
            ('mp_access_token',    ''),
            ('mp_device_id',       ''),
            ('mp_integration',     '0'),
            ('pos_beep_enabled',   '1'),
            ('pos_hotkeys',        '1'),
            ('cash_session_mode',  '1'),
            ('ui_theme',           'dark'),
        ]
    )

    # IVA por defecto
    cur.execute(
        "INSERT OR IGNORE INTO taxes (idTax,name,percent,is_included,active) VALUES (1,'IVA',21.0,1,1)"
    )

    # Métodos de pago
    cur.executemany(
        "INSERT OR IGNORE INTO payment_methods "
        "(idMethod,name,commission_pct,commission_iva,active,pos_label) VALUES (?,?,?,?,?,?)",
        [
            (1, 'Efectivo',          0.0,  0, 1, 'Efectivo'),
            (2, 'Débito',            0.8,  1, 1, 'Débito'),
            (3, 'Crédito 1 cuota',   2.5,  1, 1, 'Crédito'),
            (4, 'Billetera Virtual', 0.8,  1, 1, 'Billetera Virtual'),
            (5, 'Transferencia',     0.0,  0, 1, 'Transferencia'),
            (6, 'MercadoPago Point', 2.99, 1, 1, 'MP_Point'),
        ]
    )

    # Ventas demo
    cur.executemany(
        "INSERT OR IGNORE INTO sells "
        "(idSell,payment_type,total_amount,tax_rate,tax_amount,net_amount,discount,quantity,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1,  'Efectivo',         2100.0,  21, 363.64,  1736.36, 0, 10, '2026-03-27 13:31:30'),
            (2,  'Billetera Virtual',3500.0,  21, 606.20,  2893.80, 0,  2, '2026-03-27 13:31:30'),
            (3,  'Debito',           1300.0,  21, 225.21,  1074.79, 0, 94, '2026-03-27 13:31:30'),
            (4,  'Efectivo',         2000.0,  21, 346.28,  1653.72, 0, 44, '2026-03-28 09:10:00'),
            (5,  'Efectivo',         7600.0,  21,1316.53,  6283.47, 0, 19, '2026-03-28 11:45:00'),
            (6,  'Efectivo',        59600.0,  21,10323.97,49276.03, 0,149, '2026-03-29 14:20:00'),
            (7,  'Efectivo',         8000.0,  21,1384.30,  6615.70, 0, 20, '2026-03-29 15:00:00'),
            (8,  'Efectivo',         5200.0,  21, 900.83,  4299.17, 0, 13, '2026-03-30 10:00:00'),
            (9,  'Efectivo',          800.0,  21, 138.43,   661.57, 0,  2, '2026-03-30 11:00:00'),
            (10, 'Efectivo',         1800.0,  21, 311.57,  1488.43, 0,  2, '2026-03-30 11:51:56'),
            (11, 'Efectivo',         1200.0,  21, 207.44,   992.56, 0,  3, '2026-03-30 12:00:00'),
            (12, 'Efectivo',          900.0,  21, 155.37,   744.63, 0,  1, '2026-03-30 12:28:14'),
        ]
    )

    cur.executemany(
        "INSERT OR IGNORE INTO products_sells "
        "(idSell,idProduct,product_name,cantidad_vendida,unit_price,subtotal) VALUES (?,?,?,?,?,?)",
        [
            (1, 1, 'Coca Cola 500ml',  1, 1488.0, 1488.0),
            (1, 3, 'Alfa Guaymallen',  1,  619.0,  619.0),
            (2, 6, 'Pan Lactal Bimbo', 1, 2484.0, 2484.0),
            (2, 9, 'Cereal Mix',       1,  909.0,  909.0),
            (3, 8, 'Oreo Original',    1, 1300.0, 1300.0),
        ]
    )

    conn.commit()
    print("[init_db] Datos semilla insertados correctamente.")


# ══════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════

def init_db(db_path: pathlib.Path = None, force_reset: bool = False):
    """
    Inicializa la base de datos SQLite.
    Si ya existe y force_reset=False, no hace nada destructivo
    (usa CREATE TABLE IF NOT EXISTS).
    """
    if db_path is None:
        db_path = _DB_FILE

    if force_reset and db_path.exists():
        db_path.unlink()
        print(f"[init_db] Base de datos anterior eliminada.")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA)
        _seed(conn)
        print(f"[init_db] Base de datos lista: {db_path}")
    finally:
        conn.close()


def ensure_db(db_path: pathlib.Path = None):
    """
    Llama init_db solo si la DB no existe o no tiene la tabla 'users'.
    Llamado automáticamente desde main.py al iniciar.
    """
    if db_path is None:
        # Leer db_path desde network.json si existe
        net = data_path("network.json")
        if net.exists():
            try:
                import json
                cfg = json.loads(net.read_text(encoding="utf-8"))
                if cfg.get("mode","server") == "server":
                    p = cfg.get("db_path")
                    if p:
                        db_path = pathlib.Path(p)
            except Exception:
                pass
        if db_path is None:
            db_path = _DB_FILE

    needs_init = True
    if db_path.exists():
        try:
            c = sqlite3.connect(str(db_path))
            c.execute("SELECT 1 FROM users LIMIT 1")
            c.close()
            needs_init = False
        except Exception:
            pass

    if needs_init:
        print("[CoreStack] Primera ejecución — inicializando base de datos SQLite...")
        init_db(db_path)
    return db_path


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset:
        print("⚠️  RESET: se eliminará y recreará la base de datos completa.")
        resp = input("¿Confirmar? [s/N]: ").strip().lower()
        if resp != "s":
            print("Cancelado.")
            sys.exit(0)
    init_db(force_reset=reset)
    print("\nListo. Ejecutá: python setup_admin.py → python main.py")
