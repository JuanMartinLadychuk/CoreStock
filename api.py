"""
api.py – Capa de datos CoreStack Pro v0.9
Jerarquía de precios (3 niveles), roles personalizados,
permisos granulares, proveedor obligatorio.
Módulo de Rendimientos Reales: costo de reposición, egresos,
devoluciones, comisiones por método de pago, cotizaciones USD.
"""
from db import execute_query

STOCK_THRESHOLD = 10

ALL_PERMISSIONS: dict[str, str] = {
    "ver_dashboard":      "Ver Dashboard",
    "ver_inventario":     "Ver Inventario",
    "ver_ventas":         "Ver Ventas",
    "ver_movimientos":    "Ver Movimientos",
    "ver_proveedores":    "Ver Proveedores",
    "ver_emails":         "Ver / Enviar Emails",
    "agregar_producto":   "Agregar productos",
    "editar_producto":    "Editar productos",
    "eliminar_producto":  "Eliminar productos",
    "ver_precio_costo":   "Ver precio de costo",
    "editar_stock":       "Editar stock manualmente",
    "aplicar_descuento":  "Aplicar descuentos",
    "registrar_venta":    "Registrar ventas",
    "eliminar_venta":     "Eliminar ventas",
    "agregar_proveedor":  "Agregar proveedores",
    "editar_proveedor":   "Editar proveedores",
    "eliminar_proveedor": "Eliminar proveedores",
    "gestionar_usuarios": "Gestionar usuarios",
    "gestionar_roles":    "Gestionar roles y permisos",
    "ver_configuracion":  "Ver configuracion del sistema",
    "editar_impuestos":   "Editar tributos e impuestos",
    "ver_rendimientos":   "Ver Rendimientos y Finanzas",
    "cargar_egresos":     "Cargar egresos operativos",
    "ver_mercadolibre":   "Ver modulo MercadoLibre",
    "editar_mercadolibre":"Gestionar publicaciones ML",
}

# ── Roles ──────────────────────────────────────────────────────

def get_all_roles() -> list:
    return execute_query(
        "SELECT idRole,name,description,is_system FROM roles ORDER BY idRole",
        fetch="all") or []

def get_role_by_id(id_role: int) -> dict | None:
    r = execute_query(
        "SELECT idRole,name,description,is_system FROM roles WHERE idRole=%s",
        (id_role,), fetch="one")
    return {"id":r[0],"name":r[1],"desc":r[2],"system":bool(r[3])} if r else None

def add_role(name: str, description: str) -> int:
    return execute_query(
        "INSERT INTO roles (name,description) VALUES (%s,%s)", (name, description))

def update_role(id_role: int, name: str, description: str):
    execute_query(
        "UPDATE roles SET name=%s,description=%s WHERE idRole=%s AND is_system=0",
        (name, description, id_role))

def delete_role(id_role: int):
    execute_query("DELETE FROM roles WHERE idRole=%s AND is_system=0", (id_role,))

def get_role_permissions(id_role: int) -> dict[str, bool]:
    rows = execute_query(
        "SELECT permission_key,enabled FROM role_permissions WHERE idRole=%s",
        (id_role,), fetch="all") or []
    perms = {k: False for k in ALL_PERMISSIONS}
    for key, enabled in rows:
        if key in perms:
            perms[key] = bool(enabled)
    return perms

def save_role_permissions(id_role: int, permissions: dict[str, bool]):
    execute_query("DELETE FROM role_permissions WHERE idRole=%s", (id_role,))
    for key, enabled in permissions.items():
        execute_query(
            "INSERT INTO role_permissions (idRole,permission_key,enabled) VALUES (%s,%s,%s)",
            (id_role, key, int(enabled)))

def get_user_permissions(id_role: int) -> dict[str, bool]:
    role = get_role_by_id(id_role)
    if role and role["system"] and role["name"] == "Administrador":
        return {k: True for k in ALL_PERMISSIONS}
    return get_role_permissions(id_role)

# ── Settings ───────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    r = execute_query(
        "SELECT setting_value FROM settings WHERE setting_key=%s", (key,), fetch="one")
    return r[0] if (r and r[0] is not None) else default

def set_setting(key: str, value: str):
    execute_query(
        "INSERT INTO settings (setting_key,setting_value) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
        (key, value))

def get_all_settings() -> dict:
    rows = execute_query("SELECT setting_key,setting_value FROM settings", fetch="all")
    return {r[0]: (r[1] or "") for r in rows} if rows else {}

# ── Tipo de negocio ────────────────────────────────────────────

BUSINESS_TYPES = {
    "fisico":    "Local físico",
    "ecommerce": "E-commerce puro",
    "ambos":     "Local físico + E-commerce",
}

# Módulos habilitados por tipo de negocio
# Claves = keys del FRAME_REGISTRY en main.py
BUSINESS_MODULE_MAP: dict[str, set] = {
    "fisico": {
        "dashboard", "pos", "inventory", "sales", "suppliers",
        "analytics", "categories", "config", "users", "roles",
        "emails", "about",
    },
    "ecommerce": {
        "dashboard", "inventory", "sales", "suppliers", "analytics",
        "mercadolibre", "categories", "config", "users", "roles",
        "emails", "about",
    },
    "ambos": {
        "dashboard", "pos", "inventory", "sales", "suppliers", "analytics",
        "mercadolibre", "categories", "config", "users", "roles",
        "emails", "about",
    },
}

def get_business_type() -> str:
    return get_setting("business_type", "fisico")

def set_business_type(btype: str):
    if btype in BUSINESS_TYPES:
        set_setting("business_type", btype)

def get_enabled_modules() -> set:
    btype = get_business_type()
    return BUSINESS_MODULE_MAP.get(btype, BUSINESS_MODULE_MAP["ambos"])

# ── Tributos dinámicos ─────────────────────────────────────────

def get_all_taxes() -> list:
    """Devuelve [(idTax, name, percent, is_included, active), ...]"""
    return execute_query(
        "SELECT idTax, name, percent, is_included, active "
        "FROM taxes ORDER BY idTax",
        fetch="all") or []

def get_active_taxes() -> list:
    return execute_query(
        "SELECT idTax, name, percent, is_included "
        "FROM taxes WHERE active=1 ORDER BY idTax",
        fetch="all") or []

def get_tax_by_id(id_tax: int) -> dict | None:
    r = execute_query(
        "SELECT idTax,name,percent,is_included,active FROM taxes WHERE idTax=%s",
        (id_tax,), fetch="one")
    return {"id": r[0], "name": r[1], "percent": float(r[2]),
            "is_included": bool(r[3]), "active": bool(r[4])} if r else None

def add_tax(name: str, percent: float, is_included: bool, changed_by: int) -> int:
    id_tax = execute_query(
        "INSERT INTO taxes (name, percent, is_included) VALUES (%s, %s, %s)",
        (name, percent, int(is_included)))
    _log_tax_change(id_tax, None, percent, is_included, "CREADO", changed_by)
    return id_tax

def update_tax(id_tax: int, name: str, percent: float,
               is_included: bool, changed_by: int):
    old = get_tax_by_id(id_tax)
    execute_query(
        "UPDATE taxes SET name=%s, percent=%s, is_included=%s WHERE idTax=%s",
        (name, percent, int(is_included), id_tax))
    _log_tax_change(id_tax, old["percent"] if old else None, percent,
                    is_included, "EDITADO", changed_by)

def toggle_tax_active(id_tax: int, active: bool, changed_by: int):
    execute_query("UPDATE taxes SET active=%s WHERE idTax=%s", (int(active), id_tax))
    action = "ACTIVADO" if active else "DESACTIVADO"
    _log_tax_change(id_tax, None, None, None, action, changed_by)

def delete_tax(id_tax: int, changed_by: int):
    _log_tax_change(id_tax, None, None, None, "ELIMINADO", changed_by)
    execute_query("DELETE FROM taxes WHERE idTax=%s", (id_tax,))

def _log_tax_change(id_tax: int, old_pct, new_pct, is_included, action: str, user_id):
    execute_query(
        "INSERT INTO tax_audit_log (idTax, old_percent, new_percent, is_included, action, idUser) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (id_tax, old_pct, new_pct,
         int(is_included) if is_included is not None else None,
         action,
         user_id if user_id else None))

def get_tax_audit_log(limit: int = 200) -> list:
    return execute_query(
        "SELECT l.idLog, t.name, l.old_percent, l.new_percent, "
        "       l.is_included, l.action, "
        "       COALESCE(u.username, 'sistema') as username, "
        "       l.changed_at "
        "FROM tax_audit_log l "
        "LEFT JOIN taxes t ON t.idTax = l.idTax "
        "LEFT JOIN users u ON u.idUser = l.idUser "
        "ORDER BY l.idLog DESC LIMIT %s",
        (limit,), fetch="all") or []

def calculate_tax_breakdown_multi(total: float) -> tuple[float, list[dict]]:
    """
    Calcula desglose con todos los impuestos activos.
    Retorna (net_amount, [{"name", "percent", "amount", "is_included"}, ...])
    """
    taxes = get_active_taxes()
    if not taxes:
        rate     = float(get_setting("tax_percent", "21"))
        name     = get_setting("tax_name", "IVA")
        included = get_setting("tax_included", "1") == "1"
        if included:
            net = round(total / (1 + rate / 100), 2)
            return net, [{"name": name, "percent": rate,
                          "amount": round(total - net, 2), "is_included": True}]
        else:
            return total, [{"name": name, "percent": rate,
                            "amount": round(total * rate / 100, 2), "is_included": False}]

    included_total_rate = sum(float(t[2]) for t in taxes if t[3])
    net = round(total / (1 + included_total_rate / 100), 2) if included_total_rate else total

    breakdown = []
    for id_tax, name, pct, is_inc in taxes:
        pct = float(pct)
        amt = round(net * pct / 100, 2)
        breakdown.append({"name": name, "percent": pct,
                           "amount": amt, "is_included": bool(is_inc)})
    return net, breakdown

# ── Jerarquía de precios ───────────────────────────────────────

def get_category_margins() -> dict[str, float]:
    rows = execute_query(
        "SELECT category,margin_percent FROM category_margins", fetch="all") or []
    return {r[0]: float(r[1]) for r in rows}

def set_category_margin(category: str, margin: float):
    execute_query(
        "INSERT INTO category_margins (category,margin_percent) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE margin_percent=VALUES(margin_percent)",
        (category, margin))

def calculate_sell_price_hierarchy(
    cost_price: float,
    category: str = "",
    product_id: int | None = None,
) -> tuple[float, str, float]:
    """
    Devuelve (precio_venta, fuente, margen_pct).
    Nivel 1: custom_margin del producto
    Nivel 2: margen de la categoría
    Nivel 3: margen global
    """
    if product_id:
        r = execute_query(
            "SELECT custom_margin FROM products WHERE idProduct=%s",
            (product_id,), fetch="one")
        if r and r[0] is not None:
            m = float(r[0])
            return round(cost_price*(1+m/100), 2), "producto", m

    if category:
        r = execute_query(
            "SELECT margin_percent FROM category_margins WHERE category=%s",
            (category,), fetch="one")
        if r and r[0] is not None:
            m = float(r[0])
            return round(cost_price*(1+m/100), 2), f"categoría ({category})", m

    m = float(get_setting("markup_percent", "20"))
    return round(cost_price*(1+m/100), 2), "global", m

def calculate_sell_price(cost_price: float) -> float:
    m = float(get_setting("markup_percent", "20"))
    return round(cost_price*(1+m/100), 2)

def calculate_tax_breakdown(total: float) -> tuple[float, float]:
    rate = float(get_setting("tax_percent", "21"))
    included = get_setting("tax_included", "1") == "1"
    if included:
        net = round(total/(1+rate/100), 2)
        return net, round(total-net, 2)
    return total, round(total*rate/100, 2)

# ── Productos ──────────────────────────────────────────────────

def get_all_products(search: str = "", category: str = "") -> list:
    sql = (
        "SELECT p.idProduct,p.product,p.category,p.cost_price,p.price,"
        "p.custom_margin,p.stock,p.active,"
        "COALESCE(s.supplier,'Sin proveedor') "
        "FROM products p LEFT JOIN suppliers s ON s.idSupplier=p.idSupplier WHERE 1=1"
    )
    params: list = []
    if search:
        sql += " AND p.product LIKE %s"; params.append(f"%{search}%")
    if category:
        sql += " AND p.category=%s"; params.append(category)
    sql += " ORDER BY p.product"
    return execute_query(sql, params, fetch="all") or []

def get_active_products(search: str = "", category: str = "") -> list:
    sql = (
        "SELECT p.idProduct,p.product,p.category,p.cost_price,p.price,p.stock "
        "FROM products p WHERE p.active=1"
    )
    params: list = []
    if search:
        sql += " AND p.product LIKE %s"; params.append(f"%{search}%")
    if category:
        sql += " AND p.category=%s"; params.append(category)
    sql += " ORDER BY p.product"
    return execute_query(sql, params, fetch="all") or []

def get_product_by_id(id_product: int):
    return execute_query(
        "SELECT idProduct,product,category,cost_price,price,custom_margin,stock,idSupplier,"
        "COALESCE(barcode,'') "
        "FROM products WHERE idProduct=%s", (id_product,), fetch="one")

def search_product_by_name(name: str):
    return execute_query(
        "SELECT idProduct,product,category,cost_price,price,stock "
        "FROM products WHERE product=%s AND active=1", (name,), fetch="one")

def add_product(product: str, category: str, cost_price: float, price: float,
                custom_margin, stock: int, id_supplier: int) -> int:
    return execute_query(
        "INSERT INTO products (product,category,cost_price,price,custom_margin,stock,idSupplier) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (product, category, cost_price, price, custom_margin, stock, id_supplier))

def update_product(id_product: int, product: str, category: str,
                   cost_price: float, price: float, custom_margin,
                   stock: int, id_supplier: int):
    execute_query(
        "UPDATE products SET product=%s,category=%s,cost_price=%s,price=%s,"
        "custom_margin=%s,stock=%s,idSupplier=%s WHERE idProduct=%s",
        (product, category, cost_price, price, custom_margin, stock, id_supplier, id_product))

def update_product_replacement_cost(id_product: int, replacement_cost: float):
    """Actualiza el costo de reposición de un producto (precio proveedor HOY)."""
    execute_query(
        "UPDATE products SET replacement_cost=%s, replacement_updated_at=NOW() "
        "WHERE idProduct=%s",
        (replacement_cost, id_product))

def delete_product(id_product: int):
    execute_query("UPDATE products SET active=0 WHERE idProduct=%s", (id_product,))

def restore_product(id_product: int):
    execute_query("UPDATE products SET active=1 WHERE idProduct=%s", (id_product,))

def deduct_stock(id_product: int, qty: int):
    execute_query("UPDATE products SET stock=stock-%s WHERE idProduct=%s", (qty, id_product))
    # ── Auto-push a MercadoLibre (background, no bloquea el POS) ──
    _push_stock_to_ml_async(id_product)

def _push_stock_to_ml_async(id_product: int):
    """Dispara el sync ML en un thread daemon para no bloquear la UI."""
    import threading
    def _do():
        try:
            new_stock_row = execute_query(
                "SELECT stock FROM products WHERE idProduct=%s",
                (id_product,), fetch="one")
            if not new_stock_row:
                return
            new_qty = int(new_stock_row[0])
            from ml_api import push_stock_after_sale
            push_stock_after_sale(id_product, new_qty)
        except Exception:
            pass  # silencioso — ML no configurado o Neon offline no rompe el POS
    threading.Thread(target=_do, daemon=True).start()

def adjust_stock(id_product: int, new_stock: int, reason: str, user_id: int):
    old = execute_query("SELECT stock FROM products WHERE idProduct=%s", (id_product,), fetch="one")
    execute_query("UPDATE products SET stock=%s WHERE idProduct=%s", (new_stock, id_product))
    execute_query(
        "INSERT INTO inventory_adjustments (idProduct,old_stock,new_stock,reason,idUser) "
        "VALUES (%s,%s,%s,%s,%s)",
        (id_product, old[0] if old else 0, new_stock, reason, user_id))
    # ── Auto-push a MercadoLibre ──
    _push_stock_to_ml_async(id_product)

def get_low_stock_products(threshold: int = STOCK_THRESHOLD) -> list:
    return execute_query(
        "SELECT p.product,p.stock,s.mail,s.supplier "
        "FROM products p LEFT JOIN suppliers s ON s.idSupplier=p.idSupplier "
        "WHERE p.active=1 AND p.stock<=%s ORDER BY p.stock",
        (threshold,), fetch="all") or []

def get_inventory_value() -> float:
    r = execute_query("SELECT SUM(price*stock) FROM products WHERE active=1", fetch="one")
    return float(r[0]) if r and r[0] else 0.0

# ── Proveedores ────────────────────────────────────────────────

def get_all_suppliers(search: str = "") -> list:
    sql = "SELECT idSupplier,supplier,city,mail,tel FROM suppliers WHERE active=1"
    params: list = []
    if search:
        sql += " AND supplier LIKE %s"; params.append(f"%{search}%")
    sql += " ORDER BY supplier"
    return execute_query(sql, params, fetch="all") or []

def get_supplier_by_id(id_supplier: int):
    return execute_query(
        "SELECT idSupplier,supplier,city,mail,tel FROM suppliers WHERE idSupplier=%s",
        (id_supplier,), fetch="one")

def add_supplier(supplier: str, address: str = "", city: str = "",
                 email: str = "", phone: str = "", description: str = "") -> int:
    return execute_query(
        "INSERT INTO suppliers (supplier,city,mail,tel) VALUES (%s,%s,%s,%s)",
        (supplier, city, email, phone))

def update_supplier(id_supplier: int, supplier: str = "", address: str = "",
                    city: str = "", email: str = "", phone: str = "",
                    description: str = ""):
    execute_query(
        "UPDATE suppliers SET supplier=%s,city=%s,mail=%s,tel=%s WHERE idSupplier=%s",
        (supplier, city, email, phone, id_supplier))

def delete_supplier(id_supplier: int):
    execute_query("DELETE FROM suppliers WHERE idSupplier=%s", (id_supplier,))

# ── Métodos de pago con comisiones ────────────────────────────

def get_all_payment_methods() -> list:
    """[(idMethod, name, commission_pct, commission_iva, active, pos_label), ...]"""
    return execute_query(
        "SELECT idMethod, name, commission_pct, commission_iva, active, pos_label "
        "FROM payment_methods ORDER BY idMethod",
        fetch="all") or []

def get_active_payment_methods() -> list:
    return execute_query(
        "SELECT idMethod, name, commission_pct, commission_iva, pos_label "
        "FROM payment_methods WHERE active=1 ORDER BY idMethod",
        fetch="all") or []

def get_payment_method_by_label(pos_label: str) -> dict | None:
    r = execute_query(
        "SELECT idMethod, name, commission_pct, commission_iva "
        "FROM payment_methods WHERE pos_label=%s AND active=1 LIMIT 1",
        (pos_label,), fetch="one")
    if not r:
        return None
    return {"id": r[0], "name": r[1], "commission_pct": float(r[2]),
            "commission_iva": bool(r[3])}

def save_payment_method(idMethod: int | None, name: str, commission_pct: float,
                        commission_iva: bool, pos_label: str, active: bool):
    if idMethod:
        execute_query(
            "UPDATE payment_methods SET name=%s, commission_pct=%s, commission_iva=%s, "
            "pos_label=%s, active=%s WHERE idMethod=%s",
            (name, commission_pct, int(commission_iva), pos_label, int(active), idMethod))
    else:
        execute_query(
            "INSERT INTO payment_methods (name, commission_pct, commission_iva, pos_label, active) "
            "VALUES (%s,%s,%s,%s,%s)",
            (name, commission_pct, int(commission_iva), pos_label, int(active)))

def calculate_commission(amount: float, pos_label: str) -> float:
    """
    Devuelve el monto de comisión para un pago dado.
    Ej: amount=10000, pos_label='Billetera Virtual' -> 80.0 (si commission_pct=0.8)
    """
    pm = get_payment_method_by_label(pos_label)
    if not pm or pm["commission_pct"] == 0:
        return 0.0
    return round(amount * pm["commission_pct"] / 100, 2)

# ── Ventas ─────────────────────────────────────────────────────

def add_sell_v2(payment_type: str, quantity: int, total_amount: float,
                product_name: str, discount: float = 0.0) -> int:
    """
    Registra una venta:
    - Fotografía cost_price y replacement_cost del producto al momento de la venta
    - Calcula y guarda la comisión del método de pago
    - Descuenta stock
    """
    r = execute_query(
        "SELECT idProduct, cost_price, COALESCE(replacement_cost, cost_price) "
        "FROM products WHERE product=%s AND active=1",
        (product_name,), fetch="one")
    if not r:
        raise ValueError(f"Producto '{product_name}' no encontrado.")
    id_product, cost_snap, repl_snap = r[0], float(r[1]), float(r[2])

    s = execute_query("SELECT stock FROM products WHERE idProduct=%s",
                      (id_product,), fetch="one")
    if not s or s[0] < quantity:
        raise ValueError(f"Stock insuficiente para '{product_name}'.")

    net, breakdown = calculate_tax_breakdown_multi(total_amount)
    total_tax_am   = sum(t["amount"] for t in breakdown)
    effective_rate = round(sum(t["percent"] for t in breakdown), 4)
    commission     = calculate_commission(total_amount, payment_type)

    id_sell = execute_query(
        "INSERT INTO sells (payment_type, total_amount, tax_rate, tax_amount, "
        "net_amount, discount, quantity, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())",
        (payment_type, total_amount, effective_rate, total_tax_am,
         net, discount, quantity))

    execute_query(
        "INSERT INTO products_sells "
        "(idSell, idProduct, cantidad_vendida, subtotal, cost_snapshot, replacement_snapshot) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (id_sell, id_product, quantity, total_amount,
         round(cost_snap * quantity, 2),
         round(repl_snap * quantity, 2)))

    deduct_stock(id_product, quantity)
    return id_sell

def get_sells_detailed(limit: int = 500, date_from: str = "",
                        date_to: str = "", payment: str = "") -> list:
    sql = (
        "SELECT s.idSell,"
        "  GROUP_CONCAT(p.product ORDER BY p.product SEPARATOR ', '),"
        "  s.payment_type,"
        "  COALESCE(s.net_amount,s.total_amount),"
        "  COALESCE(s.tax_rate,21),"
        "  COALESCE(s.tax_amount,0),"
        "  s.total_amount,s.quantity,s.created_at "
        "FROM sells s "
        "LEFT JOIN products_sells ps ON ps.idSell=s.idSell "
        "LEFT JOIN products p ON p.idProduct=ps.idProduct WHERE 1=1"
    )
    params: list = []
    if date_from: sql += " AND DATE(s.created_at)>=%s"; params.append(date_from)
    if date_to:   sql += " AND DATE(s.created_at)<=%s"; params.append(date_to)
    if payment:   sql += " AND s.payment_type=%s";       params.append(payment)
    sql += " GROUP BY s.idSell ORDER BY s.idSell DESC LIMIT %s"
    params.append(limit)
    return execute_query(sql, params, fetch="all") or []

def get_all_sells(limit: int = 200) -> list:
    return execute_query(
        "SELECT idSell,payment_type,total_amount,quantity,created_at "
        "FROM sells ORDER BY idSell DESC LIMIT %s", (limit,), fetch="all") or []

def get_sell_detail(id_sell: int) -> list:
    return execute_query(
        "SELECT p.product,ps.cantidad_vendida,ps.subtotal "
        "FROM products_sells ps JOIN products p ON p.idProduct=ps.idProduct "
        "WHERE ps.idSell=%s", (id_sell,), fetch="all") or []

def get_sales_by_product() -> list:
    return execute_query(
        "SELECT p.product,SUM(ps.cantidad_vendida),SUM(ps.subtotal) "
        "FROM products_sells ps JOIN products p ON p.idProduct=ps.idProduct "
        "GROUP BY p.idProduct ORDER BY 2 DESC LIMIT 10", fetch="all") or []

def get_sales_summary_last_days(days: int = 7) -> list:
    return execute_query(
        "SELECT DATE(created_at), SUM(total_amount) FROM sells "
        "WHERE DATE(created_at) >= DATE(datetime('now', -%s || ' days')) "
        "  AND created_at IS NOT NULL "
        "GROUP BY DATE(created_at) ORDER BY 1", (days,), fetch="all") or []

def get_sells_summary() -> dict:
    def q(sql):
        r = execute_query(sql, fetch="one")
        return (r[0] or 0, float(r[1] or 0)) if r else (0, 0.0)
    td = q("SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM sells WHERE DATE(created_at)=DATE('now')")
    wk = q("SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM sells WHERE strftime('%Y-%W',created_at)=strftime('%Y-%W','now')")
    mo = q("SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM sells WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now')")
    tx = execute_query("SELECT COALESCE(SUM(tax_amount),0) FROM sells WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now')", fetch="one")
    return {"today_count":td[0],"today_revenue":td[1],
            "week_count":wk[0],"week_revenue":wk[1],
            "month_count":mo[0],"month_revenue":mo[1],
            "month_tax":float(tx[0]) if tx else 0.0}

def get_payment_methods() -> list[str]:
    """Devuelve lista de payment_type distintos usados en ventas (para filtros UI)."""
    rows = execute_query(
        "SELECT DISTINCT payment_type FROM sells WHERE payment_type IS NOT NULL ORDER BY 1",
        fetch="all")
    return [r[0] for r in rows] if rows else []

# ── Egresos ────────────────────────────────────────────────────

def get_expenses(month: int = None, year: int = None,
                 type_filter: str = "") -> list:
    """
    Devuelve egresos filtrados.
    [(idExpense, description, amount, type, category,
      period_month, period_year, expense_date, username, notes), ...]
    """
    sql = (
        "SELECT e.idExpense, e.description, e.amount, e.type, e.category, "
        "       e.period_month, e.period_year, e.expense_date, "
        "       COALESCE(u.username,'sistema'), e.notes "
        "FROM expenses e LEFT JOIN users u ON u.idUser=e.idUser "
        "WHERE 1=1"
    )
    params: list = []
    if month:
        sql += " AND e.period_month=%s"; params.append(month)
    if year:
        sql += " AND e.period_year=%s"; params.append(year)
    if type_filter:
        sql += " AND e.type=%s"; params.append(type_filter)
    sql += " ORDER BY e.expense_date DESC, e.idExpense DESC"
    return execute_query(sql, params, fetch="all") or []

def get_expenses_current_month() -> list:
    from datetime import date
    today = date.today()
    return get_expenses(month=today.month, year=today.year)

def add_expense(description: str, amount: float, type_: str,
                category: str, expense_date: str,
                period_month: int = None, period_year: int = None,
                notes: str = "", id_user: int = None) -> int:
    return execute_query(
        "INSERT INTO expenses (description, amount, type, category, "
        "expense_date, period_month, period_year, notes, idUser) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (description, amount, type_, category, expense_date,
         period_month, period_year, notes or None, id_user))

def update_expense(id_expense: int, description: str, amount: float,
                   type_: str, category: str, expense_date: str,
                   period_month: int = None, period_year: int = None,
                   notes: str = ""):
    execute_query(
        "UPDATE expenses SET description=%s, amount=%s, type=%s, category=%s, "
        "expense_date=%s, period_month=%s, period_year=%s, notes=%s "
        "WHERE idExpense=%s",
        (description, amount, type_, category, expense_date,
         period_month, period_year, notes or None, id_expense))

def delete_expense(id_expense: int):
    execute_query("DELETE FROM expenses WHERE idExpense=%s", (id_expense,))

def get_expense_total_month(month: int, year: int) -> dict:
    """Totales de gastos del mes separados por tipo."""
    r = execute_query(
        "SELECT "
        "  SUM(CASE WHEN type='fijo'     THEN amount ELSE 0 END), "
        "  SUM(CASE WHEN type='variable' THEN amount ELSE 0 END), "
        "  SUM(amount) "
        "FROM expenses WHERE period_month=%s AND period_year=%s",
        (month, year), fetch="one")
    if not r:
        return {"fixed": 0.0, "variable": 0.0, "total": 0.0}
    return {
        "fixed":    float(r[0] or 0),
        "variable": float(r[1] or 0),
        "total":    float(r[2] or 0),
    }

def register_shortage_as_expense(amount: float, detail: str, id_user: int = None):
    """
    Registra un faltante de caja como gasto variable automáticamente.
    Llamado desde close_cash_session cuando difference < 0.
    """
    from datetime import date
    today = date.today()
    add_expense(
        description=f"Faltante de caja: {detail}",
        amount=abs(amount),
        type_="variable",
        category="Faltante de caja",
        expense_date=str(today),
        period_month=today.month,
        period_year=today.year,
        notes="Registrado automáticamente al cerrar caja",
        id_user=id_user,
    )

# ── Devoluciones ───────────────────────────────────────────────

def get_returns(month: int = None, year: int = None) -> list:
    """
    [(idReturn, idSell, product_name, quantity, unit_price,
      refund_amount, condition, restock, reason, username, return_date), ...]
    """
    sql = (
        "SELECT r.idReturn, r.idSell, r.product_name, r.quantity, "
        "       r.unit_price, r.refund_amount, r.condition, r.restock, "
        "       r.reason, COALESCE(u.username,'sistema'), r.return_date "
        "FROM returns r LEFT JOIN users u ON u.idUser=r.idUser "
        "WHERE 1=1"
    )
    params: list = []
    if month:
        sql += " AND strftime('%m',r.return_date)=%s"; params.append(f"{int(month):02d}")
    if year:
        sql += " AND strftime('%Y',r.return_date)=%s"; params.append(str(year))
    sql += " ORDER BY r.return_date DESC, r.idReturn DESC"
    return execute_query(sql, params, fetch="all") or []

def add_return(id_sell: int, id_product: int | None, product_name: str,
               quantity: int, unit_price: float, refund_amount: float,
               condition: str, reason: str = "", id_user: int = None) -> int:
    """
    Registra una devolución.
    condition: 'revendible' | 'danado' | 'perdida'
    Si condition == 'revendible', repone stock automáticamente.
    """
    from datetime import date
    today = date.today()

    id_return = execute_query(
        "INSERT INTO returns "
        "(idSell, idProduct, product_name, quantity, unit_price, refund_amount, "
        "condition, reason, idUser, return_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (id_sell, id_product, product_name, quantity, unit_price,
         refund_amount, condition, reason or None, id_user, str(today)))

    if condition == "revendible" and id_product:
        execute_query(
            "UPDATE products SET stock=stock+%s WHERE idProduct=%s",
            (quantity, id_product))
        execute_query(
            "UPDATE returns SET restock=1 WHERE idReturn=%s", (id_return,))

    return id_return

def get_return_losses_month(month: int, year: int) -> float:
    """
    Suma de refund_amount de devoluciones con condition IN ('danado','perdida').
    Representa pérdida directa al rendimiento.
    """
    r = execute_query(
        "SELECT COALESCE(SUM(refund_amount), 0) FROM returns "
        "WHERE strftime('%m',return_date)=%s AND strftime('%Y',return_date)=%s "
        "AND condition IN ('danado','perdida')",
        (f"{month:02d}", str(year)), fetch="one")
    return float(r[0]) if r else 0.0

def get_return_total_refunds_month(month: int, year: int) -> float:
    """Total de dinero devuelto a clientes en el mes."""
    r = execute_query(
        "SELECT COALESCE(SUM(refund_amount), 0) FROM returns "
        "WHERE strftime('%m',return_date)=%s AND strftime('%Y',return_date)=%s",
        (f"{month:02d}", str(year)), fetch="one")
    return float(r[0]) if r else 0.0

# ── Cotizaciones de moneda ─────────────────────────────────────

def fetch_and_save_currency_rates() -> dict:
    """
    Consulta CriptoYa para obtener cotizaciones del dólar y las guarda
    en settings y en la tabla currency_rates.
    No requiere API key.
    """
    import urllib.request
    import json
    try:
        url = "https://criptoya.com/api/dolar"
        req = urllib.request.Request(url, headers={"User-Agent": "CoreStack/0.9"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        rates = {
            "usd_oficial": float(data.get("oficial", {}).get("ask", 0) or 0),
            "usd_blue":    float(data.get("blue",    {}).get("ask", 0) or 0),
            "usd_mep":     float((data.get("mep", {}).get("al30") or {}).get("ask", 0) or 0),
            "usd_ccl":     float((data.get("ccl", {}).get("al30") or {}).get("ask", 0) or 0),
        }
        for key, val in rates.items():
            if val > 0:
                set_setting(key, str(val))

        from datetime import date
        today = date.today().isoformat()
        set_setting("currency_last_update", today)

        # Guardar histórico
        execute_query(
            "INSERT INTO currency_rates (rate_date,usd_oficial,usd_blue,usd_mep,usd_ccl,source) "
            "VALUES (%s,%s,%s,%s,%s,'criptoya') "
            "ON DUPLICATE KEY UPDATE "
            "usd_oficial=VALUES(usd_oficial), usd_blue=VALUES(usd_blue), "
            "usd_mep=VALUES(usd_mep), usd_ccl=VALUES(usd_ccl), fetched_at=NOW()",
            (today, rates["usd_oficial"], rates["usd_blue"],
             rates["usd_mep"], rates["usd_ccl"]))
        return rates
    except Exception:
        return {}

def get_latest_currency_rates() -> dict:
    return {
        "usd_oficial":  float(get_setting("usd_oficial", "0") or 0),
        "usd_blue":     float(get_setting("usd_blue",    "0") or 0),
        "usd_mep":      float(get_setting("usd_mep",     "0") or 0),
        "last_update":  get_setting("currency_last_update", ""),
    }

def get_currency_history(days: int = 30) -> list:
    return execute_query(
        "SELECT rate_date,usd_oficial,usd_blue,usd_mep FROM currency_rates "
        "WHERE rate_date >= DATE(datetime('now', -%s || ' days')) "
        "ORDER BY rate_date",
        (days,), fetch="all") or []

# ── Rendimiento Neto Real (fórmula definitiva) ─────────────────

def get_real_performance(month: int, year: int) -> dict:
    """
    Calcula el Rendimiento Neto Real del mes.

    Fórmula:
      Rendimiento Neto = Ventas Brutas
                       - Comisiones de medios de pago
                       - COGS (costo reposición si disponible, sino costo compra)
                       - Impuestos del mes
                       - Gastos operativos (fijos + variables)
                       - Salarios
                       - Pérdidas por devoluciones irrecuperables

    Retorna dict completo con todos los componentes para mostrar en UI.
    """
    # 1. Ventas brutas
    r_ventas = execute_query(
        "SELECT COALESCE(SUM(total_amount),0), COUNT(*) "
        "FROM sells WHERE strftime('%m',created_at)=%s AND strftime('%Y',created_at)=%s",
        (f"{month:02d}", str(year)), fetch="one")
    gross_sales  = float(r_ventas[0]) if r_ventas else 0.0
    ticket_count = int(r_ventas[1])   if r_ventas else 0

    # 2. Comisiones por método de pago
    r_comm = execute_query(
        "SELECT s.payment_type, SUM(s.total_amount) "
        "FROM sells s "
        "WHERE strftime('%m',s.created_at)=%s AND strftime('%Y',s.created_at)=%s "
        "GROUP BY s.payment_type",
        (f"{month:02d}", str(year)), fetch="all") or []
    total_commissions = 0.0
    commission_detail = []
    for pay_type, subtotal in r_comm:
        comm = calculate_commission(float(subtotal or 0), pay_type or "")
        total_commissions += comm
        if comm > 0:
            commission_detail.append({
                "method": pay_type,
                "subtotal": float(subtotal),
                "commission": comm,
            })

    # 3. COGS: prioriza replacement_snapshot sobre cost_snapshot
    r_cogs = execute_query(
        "SELECT "
        "  COALESCE(SUM(ps.replacement_snapshot), 0), "
        "  COALESCE(SUM(ps.cost_snapshot), 0) "
        "FROM products_sells ps "
        "JOIN sells s ON s.idSell=ps.idSell "
        "WHERE strftime('%m',s.created_at)=%s AND strftime('%Y',s.created_at)=%s",
        (f"{month:02d}", str(year)), fetch="one")
    repl_cogs = float(r_cogs[0]) if r_cogs and r_cogs[0] else 0.0
    cost_cogs = float(r_cogs[1]) if r_cogs and r_cogs[1] else 0.0
    cogs = repl_cogs if repl_cogs > 0 else cost_cogs

    # 4. Impuestos del mes
    r_tax = execute_query(
        "SELECT COALESCE(SUM(tax_amount),0) FROM sells "
        "WHERE strftime('%m',created_at)=%s AND strftime('%Y',created_at)=%s",
        (f"{month:02d}", str(year)), fetch="one")
    total_taxes = float(r_tax[0]) if r_tax else 0.0

    # 5. Gastos operativos
    exp = get_expense_total_month(month, year)
    total_expenses = exp["total"]

    # 6. Salarios
    # Prioridad: si hay egresos de categoría "Sueldos" en el período → usarlos.
    # Fallback: suma de users.salary activos (nómina configurada en el sistema).
    # Esto evita doble conteo cuando el usuario registra sueldos como egreso.
    r_sal_expense = execute_query(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE category='Sueldos' AND period_month=%s AND period_year=%s",
        (month, year), fetch="one")
    salary_from_expenses = float(r_sal_expense[0]) if r_sal_expense else 0.0

    r_sal_users = execute_query(
        "SELECT COALESCE(SUM(salary), 0) FROM users WHERE active=1 AND salary > 0",
        fetch="one")
    salary_from_users = float(r_sal_users[0]) if r_sal_users else 0.0

    # Si hay egresos de sueldos registrados, esos ya están incluidos en total_expenses.
    # En ese caso salary_line = 0 para no duplicar.
    # Si NO hay egresos de sueldos, usamos la nómina configurada (salary_from_users).
    if salary_from_expenses > 0:
        total_salaries   = 0.0          # ya contabilizado en expenses
        salary_source    = "egresos"
        salary_displayed = salary_from_expenses
    else:
        total_salaries   = salary_from_users
        salary_source    = "nomina"
        salary_displayed = salary_from_users

    # 7. Devoluciones irrecuperables
    return_losses = get_return_losses_month(month, year)
    total_refunds = get_return_total_refunds_month(month, year)

    # 8. Resultado final
    net_sales        = round(gross_sales - total_commissions, 2)
    gross_profit     = round(net_sales - cogs, 2)
    net_performance  = round(
        gross_sales
        - total_commissions
        - cogs
        - total_taxes
        - total_expenses
        - total_salaries
        - return_losses,
        2)
    margin_pct = round((net_performance / gross_sales * 100), 2) if gross_sales > 0 else 0.0

    # 9. Equivalente en USD
    usd_blue   = float(get_setting("usd_blue", "0") or 0)
    usd_oficial = float(get_setting("usd_oficial", "0") or 0)

    return {
        # Ingresos
        "gross_sales":         gross_sales,
        "ticket_count":        ticket_count,
        "net_sales":           net_sales,
        # Costos de producto
        "cogs":                cogs,
        "cogs_by_purchase":    cost_cogs,
        "cogs_diff":           round(cogs - cost_cogs, 2),  # impacto inflación
        # Deducciones
        "commissions":         total_commissions,
        "commission_detail":   commission_detail,
        "taxes":               total_taxes,
        "expenses_fixed":      exp["fixed"],
        "expenses_variable":   exp["variable"],
        "expenses_total":      total_expenses,
        "salaries":            total_salaries,            # monto que se resta (puede ser 0 si ya está en expenses)
        "salary_displayed":    salary_displayed,          # monto a mostrar en UI (siempre informativo)
        "salary_source":       salary_source,             # "egresos" | "nomina"
        "return_losses":       return_losses,
        "total_refunds":       total_refunds,
        # Resultado
        "gross_profit":        gross_profit,
        "net_performance":     net_performance,
        "margin_pct":          margin_pct,
        # USD
        "net_usd_blue":        round(net_performance / usd_blue, 2)   if usd_blue > 0 else None,
        "net_usd_oficial":     round(net_performance / usd_oficial, 2) if usd_oficial > 0 else None,
    }

# ── Ajustes de inventario ──────────────────────────────────────

def get_adjustments() -> list:
    return execute_query(
        "SELECT ia.idAdjustment,p.product,ia.old_stock,ia.new_stock,"
        "ia.reason,u.username,ia.created_at "
        "FROM inventory_adjustments ia "
        "JOIN products p ON p.idProduct=ia.idProduct "
        "JOIN users u ON u.idUser=ia.idUser ORDER BY ia.idAdjustment DESC",
        fetch="all") or []

# ── Analytics / Proyecciones ───────────────────────────────────

def get_monthly_revenue_history(months: int = 6) -> list:
    return execute_query(
        "SELECT strftime('%Y',created_at), CAST(strftime('%m',created_at) AS INTEGER), SUM(total_amount) "
        "FROM sells "
        "WHERE created_at >= DATE(datetime('now', -%s || ' months')) "
        "  AND created_at IS NOT NULL "
        "GROUP BY strftime('%Y',created_at), strftime('%m',created_at) "
        "ORDER BY 1, 2",
        (months,), fetch="all") or []

def get_daily_revenue_current_month() -> list:
    return execute_query(
        "SELECT CAST(strftime('%d',created_at) AS INTEGER), SUM(total_amount) "
        "FROM sells "
        "WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now') "
        "  AND created_at IS NOT NULL "
        "GROUP BY strftime('%d',created_at) ORDER BY 1",
        fetch="all") or []

def get_revenue_by_payment_method_month() -> list:
    return execute_query(
        "SELECT payment_type, SUM(total_amount), COUNT(*) "
        "FROM sells "
        "WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now') "
        "  AND created_at IS NOT NULL "
        "GROUP BY payment_type ORDER BY 2 DESC",
        fetch="all") or []

# ── Usuarios ───────────────────────────────────────────────────

def authenticate_user(username: str, password_hash: str) -> dict | None:
    r = execute_query(
        "SELECT u.idUser, u.username, r.name, u.full_name, u.active, u.idRole "
        "FROM users u JOIN roles r ON r.idRole=u.idRole "
        "WHERE u.username=%s AND u.password_hash=%s",
        (username, password_hash), fetch="one")
    if not r:
        return None
    id_user, uname, role_name, full_name, active, id_role = r
    permissions = get_user_permissions(id_role)
    return {
        "id":          id_user,
        "username":    uname,
        "role":        role_name,
        "full_name":   full_name,
        "active":      bool(active),
        "id_role":     id_role,
        "permissions": permissions,
    }

def get_all_users() -> list:
    return execute_query(
        "SELECT u.idUser,u.username,r.name,u.full_name,u.active,u.created_at,u.idRole "
        "FROM users u JOIN roles r ON r.idRole=u.idRole ORDER BY u.username",
        fetch="all") or []

def add_user(username: str, password_hash: str, id_role: int, full_name: str) -> int:
    return execute_query(
        "INSERT INTO users (username,password_hash,idRole,full_name) VALUES (%s,%s,%s,%s)",
        (username, password_hash, id_role, full_name))

def update_user(id_user: int, id_role: int, full_name: str, active: bool):
    execute_query(
        "UPDATE users SET idRole=%s,full_name=%s,active=%s WHERE idUser=%s",
        (id_role, full_name, int(active), id_user))

def update_user_password(id_user: int, password_hash: str):
    execute_query(
        "UPDATE users SET password_hash=%s WHERE idUser=%s", (password_hash, id_user))

def get_all_users_with_salary() -> list:
    return execute_query(
        "SELECT u.idUser, u.username, r.name, u.full_name, u.active, "
        "       u.created_at, u.idRole, "
        "       COALESCE(u.salary, 0) as salary "
        "FROM users u JOIN roles r ON r.idRole=u.idRole ORDER BY u.username",
        fetch="all") or []

def update_user_salary(id_user: int, salary: float):
    execute_query(
        "UPDATE users SET salary=%s WHERE idUser=%s", (salary, id_user))

# ── Categorías dinámicas ───────────────────────────────────────

def get_all_categories() -> list[str]:
    rows = execute_query("SELECT name FROM categories ORDER BY name", fetch="all")
    if rows:
        return [r[0] for r in rows]
    rows2 = execute_query(
        "SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category",
        fetch="all")
    return [r[0] for r in rows2] if rows2 else ["Sin Categoría"]

def add_category(name: str, description: str = "", color: str = "#4fc3f7"):
    execute_query(
        "INSERT INTO categories (name, description, color) VALUES (%s, %s, %s)",
        (name.strip(), description, color))

def delete_category(name: str):
    execute_query("DELETE FROM categories WHERE name=%s", (name,))

def get_category_details() -> list:
    return execute_query(
        "SELECT c.name, c.description, c.color, "
        "       COUNT(p.idProduct) as product_count "
        "FROM categories c "
        "LEFT JOIN products p ON p.category = c.name AND p.active = 1 "
        "GROUP BY c.name ORDER BY c.name",
        fetch="all") or []

# ── Búsqueda por código de barras ──────────────────────────────

def search_product_by_barcode(barcode: str):
    return execute_query(
        "SELECT idProduct, product, category, cost_price, price, stock "
        "FROM products WHERE barcode=%s AND active=1",
        (barcode.strip(),), fetch="one")

def update_product_barcode(id_product: int, barcode: str | None):
    execute_query(
        "UPDATE products SET barcode=%s WHERE idProduct=%s",
        (barcode if barcode else None, id_product))

def get_products_without_barcode() -> list:
    return execute_query(
        "SELECT idProduct, product, category FROM products "
        "WHERE (barcode IS NULL OR barcode='') AND active=1 ORDER BY product",
        fetch="all") or []

# ── Sesiones de caja (POS) ─────────────────────────────────────

def open_cash_session(id_user: int, opening_amount: float) -> int:
    execute_query(
        "UPDATE cash_sessions SET status='cerrada', closed_at=NOW() "
        "WHERE idUser=%s AND status='abierta'", (id_user,))
    return execute_query(
        "INSERT INTO cash_sessions (idUser, opening_amount) VALUES (%s, %s)",
        (id_user, opening_amount))

def close_cash_session(id_session: int, closing_amount: float,
                        expected_cash: float, notes: str = "",
                        id_user: int = None) -> float:
    """
    Cierra la caja. Si hay faltante (difference < 0),
    lo registra automáticamente como gasto variable en expenses.
    """
    difference = closing_amount - expected_cash
    execute_query(
        "UPDATE cash_sessions SET status='cerrada', closed_at=NOW(), "
        "closing_amount=%s, expected_cash=%s, difference=%s, notes=%s "
        "WHERE idSession=%s",
        (closing_amount, expected_cash, difference, notes, id_session))
    if difference < 0:
        register_shortage_as_expense(
            abs(difference),
            f"Sesión #{id_session} - {notes or 'sin observaciones'}",
            id_user,
        )
    return difference

def get_active_cash_session(id_user: int) -> dict | None:
    r = execute_query(
        "SELECT idSession, opened_at, opening_amount FROM cash_sessions "
        "WHERE idUser=%s AND status='abierta' ORDER BY idSession DESC LIMIT 1",
        (id_user,), fetch="one")
    return {"id": r[0], "opened_at": r[1], "opening_amount": float(r[2])} if r else None

def get_cash_session_summary(id_session: int) -> dict:
    rows = execute_query(
        "SELECT COALESCE(payment_type,'Otro'), "
        "       COUNT(*), SUM(total_amount), SUM(tax_amount) "
        "FROM sells "
        "WHERE created_at >= (SELECT opened_at FROM cash_sessions WHERE idSession=%s) "
        "GROUP BY payment_type ORDER BY 3 DESC",
        (id_session,), fetch="all") or []
    total_all  = sum(float(r[2] or 0) for r in rows)
    cash_total = sum(float(r[2] or 0) for r in rows if r[0] == "Efectivo")
    return {
        "rows": rows,
        "total": total_all,
        "cash_total": cash_total,
        "ticket_count": sum(int(r[1]) for r in rows),
    }

def get_cash_sessions_history(id_user: int, limit: int = 20) -> list:
    return execute_query(
        "SELECT cs.idSession, cs.opened_at, cs.closed_at, "
        "       cs.opening_amount, cs.closing_amount, cs.difference, "
        "       cs.status, u.username "
        "FROM cash_sessions cs JOIN users u ON u.idUser=cs.idUser "
        "WHERE cs.idUser=%s ORDER BY cs.idSession DESC LIMIT %s",
        (id_user, limit), fetch="all") or []

# ── MercadoPago Point ──────────────────────────────────────────

def create_mp_intent(id_sell: int | None, amount: float, device_id: str) -> int:
    return execute_query(
        "INSERT INTO mp_payment_intents (idSell, amount, device_id) VALUES (%s, %s, %s)",
        (id_sell, amount, device_id))

def update_mp_intent(id_intent: int, status: str, intent_id: str = ""):
    execute_query(
        "UPDATE mp_payment_intents SET status=%s, intent_id=%s WHERE idIntent=%s",
        (status, intent_id, id_intent))

def get_mp_intent(id_intent: int) -> dict | None:
    r = execute_query(
        "SELECT idIntent, idSell, intent_id, amount, status, device_id, created_at "
        "FROM mp_payment_intents WHERE idIntent=%s", (id_intent,), fetch="one")
    if not r:
        return None
    return {"id": r[0], "id_sell": r[1], "intent_id": r[2],
            "amount": float(r[3]), "status": r[4],
            "device_id": r[5], "created_at": r[6]}

# ── AFIP ───────────────────────────────────────────────────────

def afip_esta_habilitado() -> bool:
    return get_setting("afip_habilitado", "0") == "1"

def autorizar_venta_afip(id_sell: int, total: float,
                          neto: float, iva: float) -> dict:
    result = {"ok": False, "cae": "", "cae_vto": "", "nro": 0, "error": ""}
    try:
        from afip import WSFEClient
        client   = WSFEClient.from_settings()
        tipo     = int(get_setting("afip_tipo_cbte", "11"))
        concepto = int(get_setting("afip_concepto", "1"))
        nro, cae, vto = client.autorizar(
            tipo_cbte=tipo, concepto=concepto,
            total=total, neto=neto, iva=iva)
        result.update({"ok": True, "cae": cae, "cae_vto": str(vto), "nro": nro})
    except Exception as e:
        result["error"] = str(e)
    return result

# ── Verificación de plan (Neon) ────────────────────────────────

def check_plan_feature(feature: str) -> bool:
    """
    Comprueba si el plan activo del tenant incluye una feature.
    Uso: if not api.check_plan_feature('afip'): mostrar_upgrade()
    """
    try:
        from plans import has_feature
        return has_feature(feature)
    except Exception:
        return True  # si falla la verificación, no bloquear