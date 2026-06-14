"""
ml_api.py – Capa de datos MercadoLibre para CoreStack Pro v0.9
Backend: Neon Tech (PostgreSQL 18) via neon_db.py
Sin dependencia de XAMPP para tablas ML.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import threading
from datetime import datetime, timedelta
from neon_db import execute_query_pg as _eq

ML_BASE = "https://api.mercadolibre.com"
ML_SITE = "MLA"


# ══════════════════════════════════════════════════════════════
#  HTTP helpers
# ══════════════════════════════════════════════════════════════

def _request(method, url, token="", payload=None, timeout=15):
    data    = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            err = json.loads(body)
            msg = err.get("message") or err.get("error") or str(err)
        except Exception:
            msg = body.decode(errors="replace")
        raise RuntimeError(f"ML API {e.code}: {msg}")


def _get(url, token="", timeout=15):
    return _request("GET", url, token=token, timeout=timeout)

def _post(url, token, payload, timeout=15):
    return _request("POST", url, token=token, payload=payload, timeout=timeout)

def _put(url, token, payload, timeout=15):
    return _request("PUT", url, token=token, payload=payload, timeout=timeout)


# ══════════════════════════════════════════════════════════════
#  Settings en Neon (tabla ml_settings)
# ══════════════════════════════════════════════════════════════

def _get_ml_setting(key: str, default: str = "") -> str:
    try:
        r = _eq(
            "SELECT setting_value FROM ml_settings WHERE setting_key=%s",
            (key,), fetch="one")
        return r[0] if (r and r[0] is not None) else default
    except Exception:
        return default


def _set_ml_setting(key: str, value: str):
    _eq(
        "INSERT INTO ml_settings (setting_key, setting_value) VALUES (%s, %s) "
        "ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value",
        (key, value))


# ══════════════════════════════════════════════════════════════
#  Log helper
# ══════════════════════════════════════════════════════════════

def _log(action, ml_user_id="", entity_id="", status="ok", detail=""):
    try:
        _eq(
            "INSERT INTO ml_sync_log (action, ml_user_id, entity_id, status, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            (action, ml_user_id or None, entity_id or None, status, detail or None))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  OAuth 2.0
# ══════════════════════════════════════════════════════════════

def get_ml_credentials():
    """Devuelve (app_id, client_secret, redirect_uri) de forma segura limpiando nulos de Neon."""
    _APP_ID_DEFAULT     = "1122439897772462"
    _SECRET_DEFAULT     = "ehpreKOTMLZhYquI3feZRGXkNvzSHZJ"   # corregido: sin la 'ti' extra
    _REDIRECT_DEFAULT   = "https://coresstack.onrender.com/oauth/callback"

    # Buscamos lo que hay en Neon
    app_id   = _get_ml_setting("ml_app_id")
    secret   = _get_ml_setting("ml_client_secret")
    redirect = _get_ml_setting("ml_redirect_uri")

    # Limpiamos espacios en blanco de los extremos si es que son strings
    app_id   = app_id.strip() if isinstance(app_id, str) else ""
    secret   = secret.strip() if isinstance(secret, str) else ""
    redirect = redirect.strip() if isinstance(redirect, str) else ""

    # Si después de limpiar quedaron vacíos, usamos obligatoriamente los hardcodeados corregidos
    final_app_id   = app_id if app_id else _APP_ID_DEFAULT
    final_secret   = secret if secret else _SECRET_DEFAULT
    final_redirect = redirect if redirect else _REDIRECT_DEFAULT

    return (final_app_id, final_secret, final_redirect)


def get_auth_url() -> str:
    app_id, _, redirect = get_ml_credentials()
    if not app_id:
        raise RuntimeError("Configurá el App ID de MercadoLibre.")
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id":     app_id,
        "redirect_uri":  redirect,
    })
    return f"https://auth.mercadolibre.com.ar/authorization?{params}"


def exchange_code_for_token(code: str) -> dict:
    app_id, secret, redirect = get_ml_credentials()
    payload = {
        "grant_type":    "authorization_code",
        "client_id":     app_id,
        "client_secret": secret,
        "code":          code,
        "redirect_uri":  redirect,
    }
    resp = _post(f"{ML_BASE}/oauth/token", token="", payload=payload)
    _save_token(resp)
    _log("oauth_exchange", resp.get("user_id", ""), status="ok",
         detail="Token inicial obtenido")
    return resp


def refresh_access_token(ml_user_id: str) -> str:
    row = _eq(
        "SELECT refresh_token FROM ml_tokens WHERE ml_user_id=%s AND active=1",
        (ml_user_id,), fetch="one")
    if not row:
        raise RuntimeError(f"Sin token guardado para user_id={ml_user_id}")
    app_id, secret, _ = get_ml_credentials()
    payload = {
        "grant_type":    "refresh_token",
        "client_id":     app_id,
        "client_secret": secret,
        "refresh_token": row[0],
    }
    resp = _post(f"{ML_BASE}/oauth/token", token="", payload=payload)
    _save_token(resp)
    return resp["access_token"]


def _save_token(resp: dict):
    ml_user_id    = str(resp.get("user_id", ""))
    access_token  = resp.get("access_token", "")
    refresh_token = resp.get("refresh_token", "")
    expires_in    = int(resp.get("expires_in", 21600))
    expires_at    = datetime.now() + timedelta(seconds=expires_in - 300)

    try:
        info     = _get(f"{ML_BASE}/users/{ml_user_id}", token=access_token)
        nickname = info.get("nickname", "")
    except Exception:
        nickname = ""

    _eq(
        "INSERT INTO ml_tokens (ml_user_id, nickname, access_token, refresh_token, expires_at) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (ml_user_id) DO UPDATE SET "
        "  access_token  = EXCLUDED.access_token, "
        "  refresh_token = EXCLUDED.refresh_token, "
        "  expires_at    = EXCLUDED.expires_at, "
        "  nickname      = EXCLUDED.nickname, "
        "  updated_at    = NOW()",
        (ml_user_id, nickname, access_token, refresh_token,
         expires_at.strftime("%Y-%m-%d %H:%M:%S")))

    # También guardar en ml_settings como fallback
    _set_ml_setting("meli_access_token",  access_token)
    _set_ml_setting("meli_refresh_token", refresh_token)


def get_valid_token(ml_user_id: str) -> str:
    row = _eq(
        "SELECT access_token, expires_at FROM ml_tokens "
        "WHERE ml_user_id=%s AND active=1",
        (ml_user_id,), fetch="one")

    if not row:
        token = _get_ml_setting("meli_access_token", "")
        if token:
            return token
        raise RuntimeError(
            "No hay cuenta MercadoLibre vinculada. "
            "Ir a Configuracion → MercadoLibre → Configuracion y vincular la cuenta.")

    access_token, expires_at = row

    needs_refresh = not access_token
    if expires_at:
        now = datetime.now()
        # Si expires_at viene con tzinfo (timestamptz) y now es naive,
        # la comparacion directa lanzaria TypeError — normalizamos.
        if getattr(expires_at, "tzinfo", None) is not None:
            now = now.replace(tzinfo=expires_at.tzinfo)
        if now >= expires_at:
            needs_refresh = True

    if needs_refresh:
        try:
            access_token = refresh_access_token(ml_user_id)
        except Exception as e:
            raise RuntimeError(
                "El token de MercadoLibre venció y no se pudo renovar "
                f"automáticamente ({e}). Volvé a vincular la cuenta en "
                "Configuración → MercadoLibre → Configuración → "
                "'Vincular cuenta MercadoLibre'."
            ) from e

    return access_token


def get_all_ml_accounts() -> list:
    rows = _eq(
        "SELECT ml_user_id, nickname, expires_at, active, updated_at "
        "FROM ml_tokens ORDER BY updated_at DESC",
        fetch="all") or []

    if not rows:
        token = _get_ml_setting("meli_access_token", "")
        if token:
            try:
                info       = _get(f"{ML_BASE}/users/me", token=token)
                ml_user_id = str(info.get("id", ""))
                nickname   = info.get("nickname", "")
                if ml_user_id:
                    _eq(
                        "INSERT INTO ml_tokens "
                        "(ml_user_id, nickname, access_token, refresh_token, expires_at) "
                        "VALUES (%s, %s, %s, %s, NOW() + INTERVAL '6 hours') "
                        "ON CONFLICT (ml_user_id) DO UPDATE SET "
                        "  access_token = EXCLUDED.access_token, "
                        "  nickname     = EXCLUDED.nickname, "
                        "  updated_at   = NOW()",
                        (ml_user_id, nickname, token,
                         _get_ml_setting("meli_refresh_token", "")))
                    rows = _eq(
                        "SELECT ml_user_id, nickname, expires_at, active, updated_at "
                        "FROM ml_tokens ORDER BY updated_at DESC",
                        fetch="all") or []
            except Exception:
                pass

    return rows


def deactivate_ml_account(ml_user_id: str):
    _eq("UPDATE ml_tokens SET active=0 WHERE ml_user_id=%s", (ml_user_id,))


# ══════════════════════════════════════════════════════════════
#  Catálogo
# ══════════════════════════════════════════════════════════════

def fetch_my_listings(ml_user_id, status="active", offset=0, limit=50):
    token  = get_valid_token(ml_user_id)
    url    = (f"{ML_BASE}/users/{ml_user_id}/items/search"
              f"?status={status}&offset={offset}&limit={limit}")
    search = _get(url, token=token)
    item_ids = search.get("results", [])
    if not item_ids:
        return {"items": [], "total": search.get("paging", {}).get("total", 0)}

    items = []
    for i in range(0, len(item_ids), 20):
        chunk     = item_ids[i:i+20]
        ids_param = ",".join(chunk)
        detail_url = (
            f"{ML_BASE}/items?ids={ids_param}"
            f"&attributes=id,title,price,available_quantity,sold_quantity,"
            f"status,listing_type_id,permalink,thumbnail,category_id,condition"
        )
        resp = _get(detail_url, token=token)
        for entry in resp:
            if entry.get("code") == 200:
                items.append(entry.get("body", {}))

    return {"items": items, "total": search.get("paging", {}).get("total", 0)}


def import_catalog(ml_user_id, progress_cb=None):
    imported = updated = errors = 0
    offset   = 0
    limit    = 50
    first    = fetch_my_listings(ml_user_id, status="active", offset=0, limit=limit)
    total    = first.get("total", 0)
    all_items = list(first.get("items", []))

    while len(all_items) < total:
        offset += limit
        page = fetch_my_listings(ml_user_id, status="active", offset=offset, limit=limit)
        all_items.extend(page.get("items", []))
        if not page.get("items"):
            break

    for idx, item in enumerate(all_items):
        if progress_cb:
            progress_cb(idx + 1, len(all_items))
        try:
            _upsert_listing(item, ml_user_id)
            _try_map_to_product(item.get("id"), item.get("title", ""))
            imported += 1
        except Exception as e:
            errors += 1
            _log("import_catalog", ml_user_id, item.get("id", ""),
                 status="error", detail=str(e))

    _log("import_catalog", ml_user_id, status="ok",
         detail=f"imported={imported} errors={errors}")
    return {"imported": imported, "updated": updated,
            "errors": errors, "total": len(all_items)}


def _upsert_listing(item: dict, ml_user_id: str):
    _eq(
        "INSERT INTO ml_listings "
        "(ml_item_id, ml_user_id, title, price, available_qty, sold_qty, "
        " status, listing_type, permalink, thumbnail, category_id, condition_ml, last_sync_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) "
        "ON CONFLICT (ml_item_id) DO UPDATE SET "
        "  title=EXCLUDED.title, price=EXCLUDED.price, "
        "  available_qty=EXCLUDED.available_qty, sold_qty=EXCLUDED.sold_qty, "
        "  status=EXCLUDED.status, listing_type=EXCLUDED.listing_type, "
        "  permalink=EXCLUDED.permalink, thumbnail=EXCLUDED.thumbnail, "
        "  last_sync_at=NOW(), updated_at=NOW()",
        (item.get("id"), ml_user_id, item.get("title"),
         item.get("price"), item.get("available_quantity", 0),
         item.get("sold_quantity", 0), item.get("status"),
         item.get("listing_type_id"), item.get("permalink"),
         item.get("thumbnail"), item.get("category_id"),
         item.get("condition")))


def _try_map_to_product(ml_item_id: str, title: str):
    """
    Intenta mapear con producto en XAMPP (MariaDB local).
    Si falla silenciosamente (no crítico).
    """
    if not title:
        return
    try:
        from db import execute_query
        row = execute_query(
            "SELECT idProduct FROM products WHERE product=%s AND active=1 LIMIT 1",
            (title,), fetch="one")
        if not row:
            row = execute_query(
                "SELECT idProduct FROM products WHERE product LIKE %s AND active=1 LIMIT 1",
                (f"%{title[:30]}%",), fetch="one")
        if row:
            _eq(
                "UPDATE ml_listings SET id_product=%s WHERE ml_item_id=%s",
                (row[0], ml_item_id))
    except Exception:
        pass


def get_listings_local(ml_user_id="", status="", search="") -> list:
    sql = (
        "SELECT l.id_listing, l.ml_item_id, l.title, l.price, "
        "       l.available_qty, l.sold_qty, l.status, l.listing_type, "
        "       l.thumbnail, l.last_sync_at, l.sync_stock, "
        "       '—' AS product_name, "
        "       l.id_product, l.permalink "
        "FROM ml_listings l "
        "WHERE 1=1"
    )
    params: list = []
    if ml_user_id:
        sql += " AND l.ml_user_id=%s"; params.append(ml_user_id)
    if status:
        sql += " AND l.status=%s"; params.append(status)
    if search:
        sql += " AND l.title ILIKE %s"; params.append(f"%{search}%")
    sql += " ORDER BY l.sold_qty DESC, l.updated_at DESC"
    return _eq(sql, params, fetch="all") or []


# ══════════════════════════════════════════════════════════════
#  Stock
# ══════════════════════════════════════════════════════════════

def sync_stock_to_ml(ml_item_id, ml_user_id, new_qty) -> bool:
    token = get_valid_token(ml_user_id)
    try:
        _put(f"{ML_BASE}/items/{ml_item_id}",
             token=token, payload={"available_quantity": new_qty})
        _eq("UPDATE ml_listings SET available_qty=%s, last_sync_at=NOW() "
            "WHERE ml_item_id=%s", (new_qty, ml_item_id))
        _log("sync_stock", ml_user_id, ml_item_id, detail=f"qty={new_qty}")
        return True
    except Exception as e:
        _log("sync_stock", ml_user_id, ml_item_id, status="error", detail=str(e))
        return False


def sync_all_stocks(ml_user_id) -> dict:
    """
    Lee stock desde XAMPP (products) y sincroniza a MeLi.
    El JOIN entre Neon y MariaDB se hace en Python.
    """
    # Traer listings con id_product asignado desde Neon
    rows_neon = _eq(
        "SELECT ml_item_id, id_product FROM ml_listings "
        "WHERE ml_user_id=%s AND sync_stock=1 AND status='active' "
        "AND id_product IS NOT NULL",
        (ml_user_id,), fetch="all") or []

    ok = errors = 0
    for ml_item_id, id_product in rows_neon:
        try:
            # Leer stock de MariaDB local
            from db import execute_query
            r = execute_query(
                "SELECT stock FROM products WHERE idProduct=%s", (id_product,), fetch="one")
            stock = int(r[0]) if r else 0
        except Exception:
            errors += 1
            continue
        if sync_stock_to_ml(ml_item_id, ml_user_id, stock):
            ok += 1
        else:
            errors += 1
    return {"synced": ok, "errors": errors}


def toggle_listing_sync_stock(id_listing, enabled):
    _eq("UPDATE ml_listings SET sync_stock=%s WHERE id_listing=%s",
        (int(bool(enabled)), id_listing))


def map_listing_to_product(id_listing, id_product):
    _eq("UPDATE ml_listings SET id_product=%s WHERE id_listing=%s",
        (id_product, id_listing))


def push_stock_after_sale(id_product: int, new_qty: int) -> dict:
    """
    Hook llamado automáticamente por api.deduct_stock / api.adjust_stock
    cada vez que cambia el stock de un producto local.

    Busca todos los ml_listings mapeados a ese id_product con sync_stock=True
    y empuja el nuevo stock a la API de MercadoLibre.

    Retorna {"synced": N, "errors": N, "skipped": N}
    """
    try:
        rows = _eq(
            "SELECT l.ml_item_id, l.ml_user_id "
            "FROM ml_listings l "
            "WHERE l.id_product=%s AND l.sync_stock=1 AND l.status='active'",
            (id_product,), fetch="all") or []
    except Exception:
        return {"synced": 0, "errors": 0, "skipped": 0}

    synced = errors = skipped = 0
    for ml_item_id, ml_user_id in rows:
        if not ml_user_id:
            skipped += 1
            continue
        try:
            ok = sync_stock_to_ml(ml_item_id, ml_user_id, new_qty)
            if ok:
                synced += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    return {"synced": synced, "errors": errors, "skipped": skipped}


def get_ml_status_for_products(id_products: list) -> dict:
    """
    Dado una lista de idProduct locales, retorna un dict:
      {id_product: {"ml_item_id": str, "available_qty": int,
                    "status": str, "sync_stock": bool, "id_listing": int}}
    Solo incluye productos que tienen al menos un listing mapeado.
    Si hay múltiples listings para el mismo producto, devuelve el más reciente.
    """
    if not id_products:
        return {}
    placeholders = ",".join(["%s"] * len(id_products))
    try:
        rows = _eq(
            f"SELECT DISTINCT ON (id_product) "
            f"  id_product, ml_item_id, available_qty, status, sync_stock, id_listing "
            f"FROM ml_listings "
            f"WHERE id_product IN ({placeholders}) "
            f"ORDER BY id_product, updated_at DESC NULLS LAST",
            id_products, fetch="all") or []
    except Exception:
        return {}

    return {
        r[0]: {
            "ml_item_id":    r[1],
            "available_qty": r[2],
            "status":        r[3],
            "sync_stock":    bool(r[4]),
            "id_listing":    r[5],
        }
        for r in rows if r[0] is not None
    }


# ══════════════════════════════════════════════════════════════
#  Órdenes
# ══════════════════════════════════════════════════════════════

def fetch_recent_orders(ml_user_id, limit=50, status="") -> list:
    token  = get_valid_token(ml_user_id)
    params = f"seller={ml_user_id}&sort=date_desc&limit={limit}"
    if status:
        params += f"&order.status={status}"
    resp    = _get(f"{ML_BASE}/orders/search?{params}", token=token)
    results = resp.get("results", [])
    saved   = 0
    for order in results:
        try:
            _upsert_order(order, ml_user_id)
            saved += 1
        except Exception as e:
            _log("sync_order", ml_user_id, str(order.get("id", "")),
                 status="error", detail=str(e))
    _log("sync_order", ml_user_id, status="ok",
         detail=f"fetched={len(results)} saved={saved}")
    return results


def _upsert_order(order: dict, ml_user_id: str):
    oi          = order.get("order_items", [{}])[0]
    item        = oi.get("item", {})
    ml_item_id  = item.get("id", "")
    buyer       = order.get("buyer", {})
    shipping    = order.get("shipping", {})
    shipping_id = shipping.get("id") if shipping else None

    listing_row = _eq(
        "SELECT id_listing FROM ml_listings WHERE ml_item_id=%s",
        (ml_item_id,), fetch="one")
    id_listing = listing_row[0] if listing_row else None

    sla_hours = 24
    try:
        sla_hours = int(_get_ml_setting("ml_sla_warn_hours", "12"))
    except Exception:
        pass

    sla_limit = None
    if order.get("status") in ("paid", "payment_in_process"):
        paid_date = order.get("date_closed") or order.get("date_created")
        if paid_date:
            try:
                dt        = datetime.fromisoformat(paid_date.replace("Z", "+00:00"))
                sla_limit = (dt + timedelta(hours=sla_hours)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    def _dt(val):
        if not val:
            return None
        return val[:19].replace("T", " ")

    order_status = order.get("status", "")
    ml_order_id  = order.get("id")
    qty          = int(oi.get("quantity", 1))

    # Verificar si esta orden ya existe (para saber si es nueva)
    existing = _eq(
        "SELECT status FROM ml_orders WHERE ml_order_id=%s",
        (ml_order_id,), fetch="one")
    is_new_paid_order = (
        existing is None
        and order_status in ("paid", "payment_in_process")
    )

    _eq(
        "INSERT INTO ml_orders "
        "(ml_order_id, ml_user_id, ml_item_id, id_listing, buyer_nickname, buyer_id, "
        " quantity, unit_price, total_amount, currency, status, "
        " shipping_id, date_created, date_closed, sla_limit) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (ml_order_id) DO UPDATE SET "
        "  status=EXCLUDED.status, "
        "  shipping_id=EXCLUDED.shipping_id, "
        "  date_closed=EXCLUDED.date_closed, "
        "  sla_limit=EXCLUDED.sla_limit, "
        "  updated_at=NOW()",
        (ml_order_id, ml_user_id, ml_item_id, id_listing,
         buyer.get("nickname"), buyer.get("id"),
         qty,
         float(oi.get("unit_price", 0)),
         float(order.get("total_amount", 0)),
         order.get("currency_id", "ARS"),
         order_status,
         shipping_id,
         _dt(order.get("date_created")),
         _dt(order.get("date_closed")),
         sla_limit))

    # ── Auto-descuento de stock local para órdenes ML nuevas y pagadas ──
    if is_new_paid_order and id_listing:
        try:
            listing_row = _eq(
                "SELECT id_product FROM ml_listings WHERE id_listing=%s",
                (id_listing,), fetch="one")
            if listing_row and listing_row[0]:
                id_product = listing_row[0]
                from db import execute_query as _lq
                current = _lq(
                    "SELECT stock FROM products WHERE idProduct=%s",
                    (id_product,), fetch="one")
                if current:
                    new_stock = max(0, int(current[0]) - qty)
                    _lq(
                        "UPDATE products SET stock=%s WHERE idProduct=%s",
                        (new_stock, id_product))
                    _log("ml_stock_deduct", ml_user_id, str(ml_item_id),
                         detail=f"order={ml_order_id} qty={qty} new_stock={new_stock}")
        except Exception as e:
            _log("ml_stock_deduct", ml_user_id, str(ml_item_id),
                 status="error", detail=str(e))


def get_orders_local(ml_user_id="", status="", limit=200) -> list:
    sql = (
        "SELECT o.id_ml_order, o.ml_order_id, o.buyer_nickname, o.quantity, "
        "       o.unit_price, o.total_amount, o.status, o.shipping_status, "
        "       o.date_created, o.sla_limit, o.afip_sent, o.afip_cae, "
        "       COALESCE(l.title,'—') AS title "
        "FROM ml_orders o "
        "LEFT JOIN ml_listings l ON l.id_listing = o.id_listing "
        "WHERE 1=1"
    )
    params: list = []
    if ml_user_id:
        sql += " AND o.ml_user_id=%s"; params.append(ml_user_id)
    if status:
        sql += " AND o.status=%s"; params.append(status)
    sql += " ORDER BY o.date_created DESC NULLS LAST LIMIT %s"; params.append(limit)
    return _eq(sql, params, fetch="all") or []


def get_sla_alerts(ml_user_id) -> list:
    return _eq(
        "SELECT o.ml_order_id, o.buyer_nickname, o.status, "
        "       o.sla_limit, COALESCE(l.title,'—') "
        "FROM ml_orders o "
        "LEFT JOIN ml_listings l ON l.id_listing = o.id_listing "
        "WHERE o.ml_user_id=%s "
        "  AND o.status IN ('paid','payment_in_process') "
        "  AND o.sla_limit IS NOT NULL "
        "  AND o.sla_limit <= NOW() + INTERVAL '24 hours' "
        "ORDER BY o.sla_limit ASC",
        (ml_user_id,), fetch="all") or []


def get_shipping_detail(ml_user_id, shipping_id) -> dict:
    token = get_valid_token(ml_user_id)
    return _get(f"{ML_BASE}/shipments/{shipping_id}", token=token)


# ══════════════════════════════════════════════════════════════
#  Mensajería
# ══════════════════════════════════════════════════════════════

def get_order_messages(ml_user_id, ml_pack_id) -> list:
    token = get_valid_token(ml_user_id)
    url   = (f"{ML_BASE}/messages/packs/{ml_pack_id}"
             f"/sellers/{ml_user_id}?mark_as_read=false")
    try:
        resp = _get(url, token=token)
    except Exception:
        url  = f"{ML_BASE}/messages/orders/{ml_pack_id}?tag=post_sale"
        resp = _get(url, token=token)

    messages = resp.get("messages", [])
    for msg in messages:
        _save_message(msg, ml_user_id, ml_pack_id)
    return messages


def _save_message(msg: dict, ml_user_id: str, ml_pack_id: int):
    from_role = ("seller"
                 if str(msg.get("from", {}).get("user_id", "")) == ml_user_id
                 else "buyer")
    sent_raw  = (msg.get("message_date", {}).get("received")
                 or msg.get("date_created", ""))
    sent_at   = sent_raw[:19].replace("T", " ") if sent_raw else None
    text      = msg.get("text", "") or ""
    attaches  = json.dumps(msg.get("attachments", [])) if msg.get("attachments") else None

    _eq(
        "INSERT INTO ml_messages "
        "(ml_pack_id, ml_user_id, from_role, text, attachments, sent_at) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT DO NOTHING",
        (ml_pack_id, ml_user_id, from_role, text, attaches, sent_at))


def send_message(ml_user_id, ml_pack_id, text, attachments=None) -> bool:
    token     = get_valid_token(ml_user_id)
    buyer_row = _eq(
        "SELECT buyer_id FROM ml_orders WHERE ml_order_id=%s",
        (ml_pack_id,), fetch="one")
    buyer_id  = int(buyer_row[0]) if buyer_row and buyer_row[0] else 0

    payload = {
        "from": {"user_id": int(ml_user_id)},
        "to":   [{"user_id": buyer_id, "resource_id": ml_pack_id,
                  "resource": "packs"}],
        "text": text,
    }
    if attachments:
        payload["attachments"] = attachments

    url = f"{ML_BASE}/messages/packs/{ml_pack_id}/sellers/{ml_user_id}"
    try:
        _post(url, token=token, payload=payload)
        _eq(
            "INSERT INTO ml_messages (ml_pack_id, ml_user_id, from_role, text, sent_at) "
            "VALUES (%s,%s,'seller',%s,NOW())",
            (ml_pack_id, ml_user_id, text))
        _log("send_message", ml_user_id, str(ml_pack_id))
        return True
    except Exception as e:
        _log("send_message", ml_user_id, str(ml_pack_id), status="error", detail=str(e))
        return False


def send_afip_notification(ml_user_id, ml_pack_id, cae, vto, nro) -> bool:
    text = (
        f"Hola, te informamos que tu factura electrónica fue emitida correctamente.\n"
        f"CAE: {cae}\n"
        f"Nro. Comprobante: {nro}\n"
        f"Vencimiento CAE: {vto}\n"
        f"Ante cualquier consulta, quedamos a tu disposición."
    )
    return send_message(ml_user_id, ml_pack_id, text)


def get_messages_local(ml_user_id, ml_pack_id=None) -> list:
    sql    = ("SELECT from_role, text, sent_at, attachments "
              "FROM ml_messages WHERE ml_user_id=%s")
    params = [ml_user_id]
    if ml_pack_id:
        sql += " AND ml_pack_id=%s"; params.append(ml_pack_id)
    sql += " ORDER BY sent_at ASC NULLS LAST"
    return _eq(sql, params, fetch="all") or []


# ══════════════════════════════════════════════════════════════
#  Reviews
# ══════════════════════════════════════════════════════════════

def fetch_item_reviews(ml_user_id, ml_item_id, offset=0, limit=20) -> list:
    token   = get_valid_token(ml_user_id)
    url     = f"{ML_BASE}/reviews/item/{ml_item_id}?offset={offset}&limit={limit}"
    resp    = _get(url, token=token)
    reviews = resp.get("reviews", [])

    for rev in reviews:
        date_cr = rev.get("date_created", "")
        _eq(
            "INSERT INTO ml_reviews "
            "(ml_item_id, ml_review_id, rating, title, content, "
            " reviewer_name, status, date_created) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (ml_review_id) DO NOTHING",
            (ml_item_id, rev.get("id"), rev.get("rate"),
             rev.get("title"), rev.get("content"),
             rev.get("reviewer_name"), rev.get("status"),
             date_cr[:19].replace("T", " ") if date_cr else None))

    _log("fetch_reviews", ml_user_id, ml_item_id, detail=f"count={len(reviews)}")
    return reviews


def get_reviews_local(ml_item_id) -> list:
    return _eq(
        "SELECT id_review, rating, title, content, reviewer_name, "
        "       status, date_created "
        "FROM ml_reviews WHERE ml_item_id=%s "
        "ORDER BY date_created DESC NULLS LAST",
        (ml_item_id,), fetch="all") or []


def get_reviews_summary(ml_item_id) -> dict:
    rows  = _eq(
        "SELECT rating, COUNT(*) FROM ml_reviews "
        "WHERE ml_item_id=%s AND rating IS NOT NULL "
        "GROUP BY rating ORDER BY rating DESC",
        (ml_item_id,), fetch="all") or []
    total = sum(r[1] for r in rows)
    prom  = round(sum(r[0]*r[1] for r in rows) / total, 2) if total else 0
    return {"average": prom, "total": total,
            "distribution": {r[0]: r[1] for r in rows}}


def get_seller_reputation(ml_user_id) -> dict:
    token = get_valid_token(ml_user_id)
    try:
        info = _get(f"{ML_BASE}/users/{ml_user_id}", token=token)
        rep  = info.get("seller_reputation", {})
        return {
            "level":         rep.get("level_id", "—"),
            "power_seller":  rep.get("power_seller_status", "—"),
            "transactions":  rep.get("transactions", {}).get("total", 0),
            "ratings_pos":   rep.get("transactions", {}).get("ratings", {}).get("positive", 0),
            "ratings_neg":   rep.get("transactions", {}).get("ratings", {}).get("negative", 0),
            "cancellations": rep.get("metrics", {}).get("cancellations", {}).get("rate", 0),
            "delayed":       rep.get("metrics", {}).get("delayed_handling_time", {}).get("rate", 0),
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════
#  Editor
# ══════════════════════════════════════════════════════════════

def get_item_full_detail(ml_user_id, ml_item_id) -> dict:
    token = get_valid_token(ml_user_id)
    return _get(f"{ML_BASE}/items/{ml_item_id}", token=token)


def update_listing(ml_user_id, ml_item_id,
                   title=None, price=None,
                   available_qty=None, description=None) -> bool:
    token   = get_valid_token(ml_user_id)
    payload = {}
    if title        is not None: payload["title"]              = title
    if price        is not None: payload["price"]              = float(price)
    if available_qty is not None: payload["available_quantity"] = int(available_qty)
    try:
        if payload:
            _put(f"{ML_BASE}/items/{ml_item_id}", token=token, payload=payload)
        if description is not None:
            _put(f"{ML_BASE}/items/{ml_item_id}/description",
                 token=token, payload={"plain_text": description})

        updates, vals = [], []
        if title        is not None: updates.append("title=%s");         vals.append(title)
        if price        is not None: updates.append("price=%s");         vals.append(price)
        if available_qty is not None: updates.append("available_qty=%s"); vals.append(available_qty)
        if updates:
            updates.append("last_sync_at=NOW()")
            vals.append(ml_item_id)
            _eq(f"UPDATE ml_listings SET {','.join(updates)} WHERE ml_item_id=%s", vals)

        _log("update_listing", ml_user_id, ml_item_id, detail=f"fields={list(payload.keys())}")
        return True
    except Exception as e:
        _log("update_listing", ml_user_id, ml_item_id, status="error", detail=str(e))
        return False


def pause_listing(ml_user_id, ml_item_id) -> bool:
    token = get_valid_token(ml_user_id)
    try:
        _put(f"{ML_BASE}/items/{ml_item_id}", token=token, payload={"status": "paused"})
        _eq("UPDATE ml_listings SET status='paused' WHERE ml_item_id=%s", (ml_item_id,))
        _log("update_listing", ml_user_id, ml_item_id, detail="paused")
        return True
    except Exception as e:
        _log("update_listing", ml_user_id, ml_item_id, status="error", detail=str(e))
        return False


def activate_listing(ml_user_id, ml_item_id) -> bool:
    token = get_valid_token(ml_user_id)
    try:
        _put(f"{ML_BASE}/items/{ml_item_id}", token=token, payload={"status": "active"})
        _eq("UPDATE ml_listings SET status='active' WHERE ml_item_id=%s", (ml_item_id,))
        _log("update_listing", ml_user_id, ml_item_id, detail="activated")
        return True
    except Exception as e:
        _log("update_listing", ml_user_id, ml_item_id, status="error", detail=str(e))
        return False


# ══════════════════════════════════════════════════════════════
#  Dashboard stats
# ══════════════════════════════════════════════════════════════

def get_ml_dashboard_stats(ml_user_id) -> dict:
    r_l = _eq(
        "SELECT COUNT(*), SUM(sold_qty), AVG(price) "
        "FROM ml_listings WHERE ml_user_id=%s AND status='active'",
        (ml_user_id,), fetch="one")
    r_op = _eq(
        "SELECT COUNT(*) FROM ml_orders "
        "WHERE ml_user_id=%s AND status IN ('paid','payment_in_process')",
        (ml_user_id,), fetch="one")
    r_sla = _eq(
        "SELECT COUNT(*) FROM ml_orders "
        "WHERE ml_user_id=%s AND status IN ('paid','payment_in_process') "
        "  AND sla_limit <= NOW() + INTERVAL '12 hours'",
        (ml_user_id,), fetch="one")
    r_rev = _eq(
        "SELECT COALESCE(SUM(total_amount),0) FROM ml_orders "
        "WHERE ml_user_id=%s AND status NOT IN ('cancelled') "
        "  AND EXTRACT(MONTH FROM date_created)=EXTRACT(MONTH FROM CURRENT_DATE) "
        "  AND EXTRACT(YEAR  FROM date_created)=EXTRACT(YEAR  FROM CURRENT_DATE)",
        (ml_user_id,), fetch="one")
    return {
        "active_listings": int(r_l[0]  or 0) if r_l  else 0,
        "total_sold":      int(r_l[1]  or 0) if r_l  else 0,
        "avg_price":       float(r_l[2] or 0) if r_l  else 0.0,
        "pending_orders":  int(r_op[0] or 0) if r_op  else 0,
        "sla_alerts":      int(r_sla[0] or 0) if r_sla else 0,
        "month_revenue":   float(r_rev[0] or 0) if r_rev else 0.0,
    }


def get_sync_log(limit=50) -> list:
    return _eq(
        "SELECT action, ml_user_id, entity_id, status, detail, created_at "
        "FROM ml_sync_log ORDER BY created_at DESC LIMIT %s",
        (limit,), fetch="all") or []


# ══════════════════════════════════════════════════════════════
#  Sincronización catálogo ML → Inventario local
# ══════════════════════════════════════════════════════════════

def sync_catalog_to_inventory(ml_user_id: str) -> dict:
    """
    Importa listings de MercadoLibre al inventario local (SQLite/XAMPP).

    Para cada listing en Neon (ml_listings) que no tenga id_product asignado:
    - Busca por nombre exacto en products.
    - Si no existe, crea el producto en la BD local con los datos del listing.
    - Luego mapea id_product en ml_listings para el sync de stock futuro.

    Retorna {"created": N, "skipped": N, "errors": N}
    """
    created = skipped = errors = 0

    # Traer todos los listings sin producto mapeado
    rows = _eq(
        "SELECT id_listing, ml_item_id, title, price, available_qty "
        "FROM ml_listings "
        "WHERE ml_user_id=%s AND id_product IS NULL",
        (ml_user_id,), fetch="all") or []

    for (id_listing, ml_item_id, title, price, avail_qty) in rows:
        if not title:
            skipped += 1
            continue
        try:
            from db import execute_query as _lq

            # 1. ¿Ya existe el producto por nombre exacto?
            existing = _lq(
                "SELECT idProduct FROM products WHERE product=%s AND active=1 LIMIT 1",
                (title,), fetch="one")

            if existing:
                id_product = existing[0]
                skipped += 1
            else:
                # 2. ¿Existe por nombre parcial (primeros 40 chars)?
                existing_partial = _lq(
                    "SELECT idProduct FROM products WHERE product LIKE %s AND active=1 LIMIT 1",
                    (f"%{title[:40]}%",), fetch="one")

                if existing_partial:
                    id_product = existing_partial[0]
                    skipped += 1
                else:
                    # 3. Crear producto nuevo en la BD local.
                    #    Precio de costo = precio ML * 0.6 (estimación conservadora).
                    #    El usuario puede editarlo después desde Inventario → Editar.
                    price_val = float(price or 0)
                    cost_est  = round(price_val * 0.6, 2) if price_val > 0 else 0.0

                    # Obtener o crear proveedor "MercadoLibre"
                    sup_row = _lq(
                        "SELECT idSupplier FROM suppliers WHERE supplier='MercadoLibre' LIMIT 1",
                        fetch="one")
                    if sup_row:
                        id_supplier = sup_row[0]
                    else:
                        id_supplier = _lq(
                            "INSERT INTO suppliers (supplier, city) VALUES (%s, %s)",
                            ("MercadoLibre", "Online"))

                    # Insertar producto
                    id_product = _lq(
                        "INSERT INTO products "
                        "(product, category, cost_price, price, custom_margin, stock, idSupplier) "
                        "VALUES (%s, %s, %s, %s, NULL, %s, %s)",
                        (title[:200],
                         "MercadoLibre",
                         cost_est,
                         price_val,
                         int(avail_qty or 0),
                         id_supplier))
                    created += 1

            # 4. Mapear id_product en Neon
            _eq(
                "UPDATE ml_listings SET id_product=%s WHERE id_listing=%s",
                (id_product, id_listing))

        except Exception as e:
            errors += 1
            _log("sync_catalog_to_inventory", ml_user_id, ml_item_id or "",
                 status="error", detail=str(e))

    _log("sync_catalog_to_inventory", ml_user_id,
         detail=f"created={created} skipped={skipped} errors={errors}")
    return {"created": created, "skipped": skipped, "errors": errors}


# ══════════════════════════════════════════════════════════════
#  Crear publicación en MercadoLibre desde producto local
# ══════════════════════════════════════════════════════════════

def create_listing_from_product(
    ml_user_id: str,
    id_product: int,
    title: str,
    price: float,
    available_qty: int,
    category_id: str,
    description: str = "",
    listing_type: str = "gold_special",
    condition: str = "new",
    sync_stock: bool = True,
) -> dict:
    """
    Crea una publicación nueva en MercadoLibre para un producto local.

    Llama a POST /items con los datos básicos.
    Si tiene éxito:
      - Guarda el listing en Neon (ml_listings).
      - Mapea id_product en el listing para sync futuro.
      - Si sync_stock=True, activa la sincronización automática de stock.

    Retorna {"ok": True, "ml_item_id": str, "permalink": str}
             o {"ok": False, "error": str}
    """
    try:
        token = get_valid_token(ml_user_id)

        # Payload mínimo requerido por ML
        payload: dict = {
            "title":              title,
            "category_id":        category_id,
            "price":              float(price),
            "currency_id":        "ARS",
            "available_quantity": int(available_qty),
            "buying_mode":        "buy_it_now",
            "listing_type_id":    listing_type,
            "condition":          condition,
            "sale_terms": [
                {"id": "WARRANTY_TYPE", "value_name": "Garantía del vendedor"},
                {"id": "WARRANTY_TIME", "value_name": "90 días"},
            ],
        }

        # Crear la publicación
        resp       = _post(f"{ML_BASE}/items", token=token, payload=payload)
        ml_item_id = resp.get("id", "")
        permalink  = resp.get("permalink", "")

        if not ml_item_id:
            return {"ok": False,
                    "error": f"ML no devolvió ID. Respuesta: {str(resp)[:200]}"}

        # Agregar descripción (endpoint separado en la API de ML)
        if description:
            try:
                _post(f"{ML_BASE}/items/{ml_item_id}/description",
                      token=token,
                      payload={"plain_text": description})
            except Exception:
                pass  # descripción no crítica, no aborta el flujo

        # Guardar listing en Neon
        _eq(
            "INSERT INTO ml_listings "
            "(ml_item_id, ml_user_id, title, price, available_qty, "
            " status, listing_type, permalink, id_product, sync_stock, last_sync_at) "
            "VALUES (%s,%s,%s,%s,%s,'active',%s,%s,%s,%s,NOW()) "
            "ON CONFLICT (ml_item_id) DO UPDATE SET "
            "  price=EXCLUDED.price, available_qty=EXCLUDED.available_qty, "
            "  id_product=EXCLUDED.id_product, sync_stock=EXCLUDED.sync_stock, "
            "  last_sync_at=NOW()",
            (ml_item_id, ml_user_id, title, float(price),
             int(available_qty), listing_type, permalink,
             id_product, int(bool(sync_stock))))

        _log("create_listing", ml_user_id, ml_item_id,
             detail=f"id_product={id_product} price={price} qty={available_qty}")

        return {"ok": True, "ml_item_id": ml_item_id, "permalink": permalink}

    except Exception as e:
        _log("create_listing", ml_user_id, status="error", detail=str(e))
        return {"ok": False, "error": str(e)}