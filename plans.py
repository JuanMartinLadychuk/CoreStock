"""
plans.py – Módulo de Planes y Suscripciones — CoreStack Pro v0.9

Gestiona el plan activo del tenant desde Neon.
Cada plan desbloquea distintas funcionalidades del sistema.
"""
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timedelta
import threading

import theme
import widgets as W

# ══════════════════════════════════════════════════════════════
#  Definición de planes
# ══════════════════════════════════════════════════════════════

PLANS = {
    "free": {
        "name":        "Free",
        "price":       0,
        "period":      "Gratis para siempre",
        "color":       "#64748b",
        "icon":        "🆓",
        "description": "Para empezar a conocer CoreStack Pro sin costo.",
        "features": {
            # POS / Ventas
            "pos":                   True,
            "ventas_diarias":        50,      # máximo tickets/día
            "exportar_excel":        False,
            "exportar_pdf":          False,
            # Inventario
            "inventario":            True,
            "productos_max":         100,
            "categorias":            True,
            # MercadoLibre
            "mercadolibre":          False,
            "ml_listings_sync":      False,
            "ml_ordenes":            False,
            "ml_mensajeria":         False,
            # AFIP
            "afip":                  False,
            # Analytics
            "analytics_basico":      True,
            "analytics_avanzado":    False,
            "analytics_usd":         False,
            # Usuarios
            "usuarios_max":          2,
            "roles_custom":          False,
            # Proveedores / Emails
            "proveedores":           True,
            "emails":                False,
            # Despacho
            "despacho":              False,
            # Soporte
            "soporte":               "comunidad",
        },
    },

    "starter": {
        "name":        "Starter",
        "price":       8999,
        "period":      "/ mes",
        "color":       "#3b82f6",
        "icon":        "🚀",
        "description": "Para comercios en crecimiento que necesitan más alcance.",
        "features": {
            "pos":                   True,
            "ventas_diarias":        500,
            "exportar_excel":        True,
            "exportar_pdf":          True,
            "inventario":            True,
            "productos_max":         1000,
            "categorias":            True,
            "mercadolibre":          True,
            "ml_listings_sync":      True,
            "ml_ordenes":            True,
            "ml_mensajeria":         False,
            "afip":                  False,
            "analytics_basico":      True,
            "analytics_avanzado":    True,
            "analytics_usd":         False,
            "usuarios_max":          5,
            "roles_custom":          False,
            "proveedores":           True,
            "emails":                True,
            "despacho":              True,
            "soporte":               "email",
        },
    },

    "pro": {
        "name":        "Pro",
        "price":       19999,
        "period":      "/ mes",
        "color":       "#8b5cf6",
        "icon":        "⭐",
        "description": "Todo lo que necesita un negocio serio. Incluye AFIP y ML completo.",
        "badge":       "MÁS POPULAR",
        "features": {
            "pos":                   True,
            "ventas_diarias":        -1,       # ilimitado
            "exportar_excel":        True,
            "exportar_pdf":          True,
            "inventario":            True,
            "productos_max":         -1,
            "categorias":            True,
            "mercadolibre":          True,
            "ml_listings_sync":      True,
            "ml_ordenes":            True,
            "ml_mensajeria":         True,
            "afip":                  True,
            "analytics_basico":      True,
            "analytics_avanzado":    True,
            "analytics_usd":         True,
            "usuarios_max":          15,
            "roles_custom":          True,
            "proveedores":           True,
            "emails":                True,
            "despacho":              True,
            "soporte":               "prioritario",
        },
    },

    "enterprise": {
        "name":        "Enterprise",
        "price":       49999,
        "period":      "/ mes",
        "color":       "#f59e0b",
        "icon":        "👑",
        "description": "Para grandes operaciones. Usuarios y productos ilimitados, soporte dedicado.",
        "features": {
            "pos":                   True,
            "ventas_diarias":        -1,
            "exportar_excel":        True,
            "exportar_pdf":          True,
            "inventario":            True,
            "productos_max":         -1,
            "categorias":            True,
            "mercadolibre":          True,
            "ml_listings_sync":      True,
            "ml_ordenes":            True,
            "ml_mensajeria":         True,
            "afip":                  True,
            "analytics_basico":      True,
            "analytics_avanzado":    True,
            "analytics_usd":         True,
            "usuarios_max":          -1,
            "roles_custom":          True,
            "proveedores":           True,
            "emails":                True,
            "despacho":              True,
            "soporte":               "dedicado",
        },
    },
}

# Descripción amigable de cada feature para mostrar en la UI
FEATURE_LABELS = {
    "pos":                "Terminal POS",
    "ventas_diarias":     "Ventas por día",
    "exportar_excel":     "Exportar a Excel",
    "exportar_pdf":       "Exportar a PDF",
    "inventario":         "Gestión de inventario",
    "productos_max":      "Productos en inventario",
    "categorias":         "Categorías ilimitadas",
    "mercadolibre":       "Módulo MercadoLibre",
    "ml_listings_sync":   "Sync de stock ML",
    "ml_ordenes":         "Órdenes ML",
    "ml_mensajeria":      "Mensajería ML",
    "afip":               "Factura electrónica AFIP",
    "analytics_basico":   "Análisis de rendimiento",
    "analytics_avanzado": "Proyecciones y salud financiera",
    "analytics_usd":      "Equivalente en USD",
    "usuarios_max":       "Usuarios del sistema",
    "roles_custom":       "Roles y permisos personalizados",
    "proveedores":        "Gestión de proveedores",
    "emails":             "Envío de emails a proveedores",
    "despacho":           "Módulo de despacho/logística",
    "soporte":            "Soporte técnico",
}

SOPORTE_LABELS = {
    "comunidad": "Comunidad (foro)",
    "email":     "Email (48 hs)",
    "prioritario": "Email prioritario (24 hs)",
    "dedicado":  "Soporte dedicado + WhatsApp",
}


# ══════════════════════════════════════════════════════════════
#  Capa de datos — Neon
# ══════════════════════════════════════════════════════════════

def _get_active_subscription(tenant_id: str = "default") -> dict | None:
    """Devuelve la suscripción activa del tenant desde Neon."""
    try:
        from neon_db import execute_query_pg as _eq
        row = _eq(
            "SELECT plan_key, status, started_at, expires_at, payment_ref "
            "FROM cs_subscriptions "
            "WHERE tenant_id=%s AND status='active' "
            "ORDER BY id_subscription DESC LIMIT 1",
            (tenant_id,), fetch="one")
        if not row:
            return None
        return {
            "plan_key":   row[0],
            "status":     row[1],
            "started_at": row[2],
            "expires_at": row[3],
            "payment_ref": row[4],
        }
    except Exception:
        return None


def _activate_plan(plan_key: str, payment_ref: str = "",
                   activated_by: str = "", duration_days: int = 30,
                   tenant_id: str = "default"):
    """Activa un plan nuevo, desactivando el anterior."""
    try:
        from neon_db import execute_query_pg as _eq

        # Obtener plan viejo para historial
        old = _get_active_subscription(tenant_id)
        old_plan = old["plan_key"] if old else None

        # Desactivar suscripciones activas previas
        _eq(
            "UPDATE cs_subscriptions SET status='cancelled', updated_at=NOW() "
            "WHERE tenant_id=%s AND status='active'",
            (tenant_id,))

        # Calcular vencimiento (Free = sin vencimiento)
        if plan_key == "free":
            expires_at = None
        else:
            expires_at = (datetime.now() + timedelta(days=duration_days)).strftime(
                "%Y-%m-%d %H:%M:%S")

        # Insertar nueva suscripción
        _eq(
            "INSERT INTO cs_subscriptions "
            "(tenant_id, plan_key, status, expires_at, payment_ref, activated_by) "
            "VALUES (%s, %s, 'active', %s, %s, %s)",
            (tenant_id, plan_key, expires_at, payment_ref or None, activated_by or None))

        # Historial
        _eq(
            "INSERT INTO cs_plan_history (tenant_id, old_plan, new_plan, changed_by) "
            "VALUES (%s, %s, %s, %s)",
            (tenant_id, old_plan, plan_key, activated_by or None))

        return True
    except Exception as e:
        raise RuntimeError(f"Error al activar plan: {e}") from e


def _get_plan_history(tenant_id: str = "default", limit: int = 20) -> list:
    try:
        from neon_db import execute_query_pg as _eq
        return _eq(
            "SELECT old_plan, new_plan, changed_at, changed_by, reason "
            "FROM cs_plan_history WHERE tenant_id=%s "
            "ORDER BY changed_at DESC LIMIT %s",
            (tenant_id, limit), fetch="all") or []
    except Exception:
        return []


def get_current_plan_key(tenant_id: str = "default") -> str:
    """Función pública para que otros módulos consulten el plan activo."""
    try:
        sub = _get_active_subscription(tenant_id)
        if not sub:
            return "free"
        # Verificar vencimiento
        if sub["expires_at"]:
            exp = sub["expires_at"]
            if hasattr(exp, "replace"):
                # ya es datetime
                if datetime.now().replace(tzinfo=exp.tzinfo if hasattr(exp, 'tzinfo') else None) > exp:
                    return "free"
            elif isinstance(exp, str) and exp < datetime.now().strftime("%Y-%m-%d"):
                return "free"
        return sub["plan_key"]
    except Exception:
        return "free"


def has_feature(feature: str, tenant_id: str = "default") -> bool:
    """
    Comprueba si el plan activo incluye una feature.
    Ejemplo: has_feature('afip') -> True/False
    """
    plan_key = get_current_plan_key(tenant_id)
    plan = PLANS.get(plan_key, PLANS["free"])
    val = plan["features"].get(feature, False)
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0   # -1 = ilimitado, 0 = no disponible
    return bool(val)


def get_feature_value(feature: str, tenant_id: str = "default"):
    """Devuelve el valor numérico de un feature (ej: productos_max -> 100)."""
    plan_key = get_current_plan_key(tenant_id)
    plan = PLANS.get(plan_key, PLANS["free"])
    return plan["features"].get(feature)


# ══════════════════════════════════════════════════════════════
#  Frame principal
# ══════════════════════════════════════════════════════════════

class PlansFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user         = user
        self._app         = app
        self._current_key = "free"
        self._sub_info    = None
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  Layout
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        W.page_header(self, "Planes y Suscripción", refresh_cmd=self.on_show)

        # Banner del plan activo
        self._active_banner = ctk.CTkFrame(self, fg_color=theme.CARD,
                                            corner_radius=14,
                                            border_width=2,
                                            border_color=theme.SEP)
        self._active_banner.pack(fill="x", padx=24, pady=(0, 16))
        self._banner_inner = ctk.CTkFrame(self._active_banner, fg_color="transparent")
        self._banner_inner.pack(fill="x", padx=20, pady=16)

        # Tabs
        self._tabs = ctk.CTkTabview(self, anchor="w")
        self._tabs.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._build_plans_tab(self._tabs.add("Planes disponibles"))
        self._build_activate_tab(self._tabs.add("Activar plan"))
        self._build_compare_tab(self._tabs.add("Comparar planes"))
        self._build_history_tab(self._tabs.add("Historial"))

    # ══════════════════════════════════════════════════════
    #  Banner plan activo
    # ══════════════════════════════════════════════════════
    def _refresh_banner(self):
        for w in self._banner_inner.winfo_children():
            w.destroy()

        plan_data = PLANS.get(self._current_key, PLANS["free"])
        color     = plan_data["color"]
        icon      = plan_data["icon"]
        name      = plan_data["name"]
        price     = plan_data["price"]
        period    = plan_data["period"]
        sub       = self._sub_info

        # Barra de color izquierda
        bar = ctk.CTkFrame(self._banner_inner, width=5,
                           fg_color=color, corner_radius=3)
        bar.pack(side="left", fill="y", padx=(0, 16))

        # Info principal
        info = ctk.CTkFrame(self._banner_inner, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(info,
                     text=f"{icon}  Plan activo: {name}",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=color).pack(anchor="w")

        price_txt = (f"${price:,.0f} {period}" if price > 0
                     else "Gratis para siempre")
        ctk.CTkLabel(info, text=price_txt,
                     font=ctk.CTkFont(size=13),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(2, 0))

        if sub and sub.get("expires_at"):
            exp = sub["expires_at"]
            exp_str = str(exp)[:10]
            ctk.CTkLabel(info,
                         text=f"Vence: {exp_str}",
                         font=ctk.CTkFont(size=11),
                         text_color=theme.C_ORANGE).pack(anchor="w")
        elif sub and sub.get("started_at"):
            ctk.CTkLabel(info,
                         text=f"Activo desde: {str(sub['started_at'])[:10]}",
                         font=ctk.CTkFont(size=11),
                         text_color=theme.TEXT_DIM).pack(anchor="w")

        # Chips de features clave
        chips = ctk.CTkFrame(self._banner_inner, fg_color="transparent")
        chips.pack(side="right", padx=(16, 0))

        key_feats = [
            ("afip",       "AFIP",     "#f59e0b"),
            ("mercadolibre", "ML",     "#3483fa"),
            ("usuarios_max", "Usuarios", theme.C_BLUE),
        ]
        for feat, label, chip_color in key_feats:
            val = plan_data["features"].get(feat)
            if isinstance(val, bool):
                text = f"✓ {label}" if val else f"✗ {label}"
                tc   = "#4ade80" if val else "#64748b"
            elif isinstance(val, int):
                text = f"{label}: {'∞' if val == -1 else val}"
                tc   = "#4ade80"
            else:
                continue
            chip = ctk.CTkFrame(chips, fg_color=theme.CARD2, corner_radius=8)
            chip.pack(side="top", pady=2, anchor="e")
            ctk.CTkLabel(chip, text=text,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=tc).pack(padx=10, pady=4)

    # ══════════════════════════════════════════════════════
    #  Tab 1 — Planes disponibles (cards)
    # ══════════════════════════════════════════════════════
    def _build_plans_tab(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        ctk.CTkLabel(sc,
                     text="Elegí el plan que mejor se adapte a tu negocio",
                     font=ctk.CTkFont(size=13),
                     text_color=theme.TEXT_DIM).pack(pady=(0, 16))

        # Grid 2x2 de cards
        grid = ctk.CTkFrame(sc, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        plan_keys = list(PLANS.keys())
        for idx, plan_key in enumerate(plan_keys):
            row = idx // 2
            col = idx % 2
            self._build_plan_card(grid, plan_key, row, col)

        # Nota de pago
        note = ctk.CTkFrame(sc, fg_color=("#fef3c7", "#422006"),
                             corner_radius=10, border_width=1,
                             border_color=("#fde68a", "#92400e"))
        note.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(note,
                     text="💳  Los pagos se procesan manualmente por ahora. "
                          "Comunicate con soporte para activar un plan de pago.\n"
                          "Para demostración, podés activar cualquier plan desde la pestaña "
                          "'Activar plan' ingresando un código de activación.",
                     text_color=("#92400e", "#fde68a"),
                     font=ctk.CTkFont(size=11),
                     justify="left",
                     wraplength=800).pack(padx=16, pady=12)

    def _build_plan_card(self, parent, plan_key: str, row: int, col: int):
        plan  = PLANS[plan_key]
        color = plan["color"]
        is_current = plan_key == self._current_key
        badge = plan.get("badge", "")

        pad_left = 0 if col == 0 else 8
        pad_top  = 0 if row == 0 else 8

        outer = ctk.CTkFrame(parent, corner_radius=16,
                              border_width=3 if is_current else 1,
                              border_color=color if is_current else theme.SEP,
                              fg_color=theme.CARD)
        outer.grid(row=row, column=col, sticky="nsew",
                   padx=(pad_left, 0), pady=(pad_top, 0))

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)

        # Badge "MÁS POPULAR" si aplica
        if badge:
            b = ctk.CTkFrame(inner, fg_color=color, corner_radius=6)
            b.pack(anchor="e")
            ctk.CTkLabel(b, text=badge,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color="#ffffff").pack(padx=8, pady=3)

        # Header
        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(hdr, text=plan["icon"],
                     font=ctk.CTkFont(size=28)).pack(side="left")
        name_f = ctk.CTkFrame(hdr, fg_color="transparent")
        name_f.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(name_f, text=plan["name"],
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=color).pack(anchor="w")

        if is_current:
            ctk.CTkLabel(name_f, text="✓ Plan actual",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#4ade80").pack(anchor="w")

        # Precio
        price_txt = (f"${plan['price']:,.0f}" if plan["price"] > 0
                     else "Gratis")
        period_txt = plan["period"] if plan["price"] > 0 else "para siempre"

        pr_row = ctk.CTkFrame(inner, fg_color="transparent")
        pr_row.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(pr_row, text=price_txt,
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=color).pack(side="left")
        ctk.CTkLabel(pr_row, text=f" {period_txt}",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM).pack(side="left", anchor="s", pady=(0, 4))

        ctk.CTkLabel(inner, text=plan["description"],
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM,
                     wraplength=280, justify="left").pack(anchor="w", pady=(0, 10))

        # Divisor
        ctk.CTkFrame(inner, height=1, fg_color=theme.SEP).pack(fill="x", pady=(0, 8))

        # Features principales (las más importantes)
        highlight_feats = [
            "ventas_diarias", "productos_max", "usuarios_max",
            "mercadolibre", "afip", "ml_mensajeria",
            "exportar_pdf", "analytics_avanzado", "soporte"
        ]
        for feat in highlight_feats:
            val = plan["features"].get(feat)
            label_txt = FEATURE_LABELS.get(feat, feat)
            if isinstance(val, bool):
                icon  = "✓" if val else "✗"
                tcolor = theme.C_GREEN if val else "#64748b"
                display = label_txt
            elif isinstance(val, int):
                icon    = "✓"
                tcolor  = theme.C_GREEN
                display = f"{label_txt}: {'Ilimitados' if val == -1 else val}"
            elif isinstance(val, str):
                icon    = "✓"
                tcolor  = theme.C_GREEN
                display = f"{label_txt}: {SOPORTE_LABELS.get(val, val)}"
            else:
                continue

            row_f = ctk.CTkFrame(inner, fg_color="transparent")
            row_f.pack(fill="x", pady=1)
            ctk.CTkLabel(row_f, text=icon, width=18,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=tcolor).pack(side="left")
            ctk.CTkLabel(row_f, text=display,
                         font=ctk.CTkFont(size=11),
                         text_color=theme.TEXT if val else "#64748b",
                         anchor="w").pack(side="left")

        # Botón
        ctk.CTkFrame(inner, height=1, fg_color=theme.SEP).pack(fill="x", pady=(10, 8))

        if is_current:
            ctk.CTkButton(inner, text="Plan actual activo ✓",
                          height=36, corner_radius=8,
                          fg_color=color, hover_color=color,
                          state="disabled",
                          font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x")
        else:
            direction = "↑ Mejorar" if list(PLANS.keys()).index(plan_key) > list(PLANS.keys()).index(self._current_key) else "↓ Bajar"
            ctk.CTkButton(inner,
                          text=f"{direction} a {plan['name']}",
                          height=36, corner_radius=8,
                          fg_color=color, hover_color=color,
                          font=ctk.CTkFont(size=12, weight="bold"),
                          command=lambda k=plan_key: self._go_to_activate(k)
                          ).pack(fill="x")

    def _go_to_activate(self, plan_key: str):
        self._tabs.set("Activar plan")
        if hasattr(self, "_activate_plan_var"):
            self._activate_plan_var.set(plan_key)
            self._on_plan_select(plan_key)

    # ══════════════════════════════════════════════════════
    #  Tab 2 — Activar plan
    # ══════════════════════════════════════════════════════
    def _build_activate_tab(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        # Selector de plan
        ctk.CTkLabel(sc, text="Seleccioná el plan a activar:",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(0, 8))

        plan_sel = ctk.CTkFrame(sc, fg_color=theme.CARD,
                                corner_radius=10, border_width=1,
                                border_color=theme.SEP)
        plan_sel.pack(fill="x", pady=(0, 16))
        ps_inner = ctk.CTkFrame(plan_sel, fg_color="transparent")
        ps_inner.pack(fill="x", padx=16, pady=14)

        self._activate_plan_var = ctk.StringVar(value="pro")

        for plan_key, plan_data in PLANS.items():
            rb_f = ctk.CTkFrame(ps_inner, fg_color="transparent")
            rb_f.pack(fill="x", pady=4)
            rb = ctk.CTkRadioButton(
                rb_f,
                text="",
                variable=self._activate_plan_var,
                value=plan_key,
                fg_color=plan_data["color"],
                command=lambda k=plan_key: self._on_plan_select(k))
            rb.pack(side="left")
            ctk.CTkLabel(rb_f,
                         text=f"{plan_data['icon']}  {plan_data['name']}",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=plan_data["color"]).pack(side="left", padx=(8, 16))
            price_txt = (f"${plan_data['price']:,.0f} {plan_data['period']}"
                         if plan_data["price"] > 0 else "Gratis")
            ctk.CTkLabel(rb_f, text=price_txt,
                         font=ctk.CTkFont(size=12),
                         text_color=theme.TEXT_DIM).pack(side="left")

        # Preview del plan seleccionado
        self._preview_card = ctk.CTkFrame(sc, fg_color=theme.CARD2,
                                           corner_radius=10)
        self._preview_card.pack(fill="x", pady=(0, 16))
        self._preview_inner = ctk.CTkFrame(self._preview_card, fg_color="transparent")
        self._preview_inner.pack(fill="x", padx=16, pady=14)

        # Código de activación
        code_card = ctk.CTkFrame(sc, fg_color=theme.CARD, corner_radius=10,
                                  border_width=1, border_color=theme.SEP)
        code_card.pack(fill="x", pady=(0, 16))
        code_inner = ctk.CTkFrame(code_card, fg_color="transparent")
        code_inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(code_inner, text="Código de activación",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(code_inner,
                     text="Ingresá el código que recibiste al realizar el pago, "
                          "o usá DEMO-PRO / DEMO-STARTER para pruebas.",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM,
                     wraplength=700, justify="left").pack(anchor="w", pady=(4, 10))

        code_row = ctk.CTkFrame(code_inner, fg_color="transparent")
        code_row.pack(fill="x")
        self._code_entry = ctk.CTkEntry(code_row,
                                         placeholder_text="Ej: DEMO-PRO  o  CS-2024-XXXXXX",
                                         height=38, font=ctk.CTkFont(size=12))
        self._code_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(code_row, text="Validar código", width=140, height=38,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._validate_code).pack(side="left")

        self._code_status = ctk.CTkLabel(code_inner, text="",
                                          font=ctk.CTkFont(size=11))
        self._code_status.pack(anchor="w", pady=(8, 0))

        # Duración
        dur_row = ctk.CTkFrame(sc, fg_color="transparent")
        dur_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(dur_row, text="Duración:",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self._duration_var = ctk.StringVar(value="30")
        ctk.CTkOptionMenu(dur_row, variable=self._duration_var,
                          values=["30", "60", "90", "365"],
                          width=90, height=32).pack(side="left", padx=(8, 4))
        ctk.CTkLabel(dur_row, text="días",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")

        # Botón principal
        self._activate_btn = ctk.CTkButton(
            sc, text="✅  Activar plan",
            height=46, corner_radius=10,
            fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._activate_plan_action)
        self._activate_btn.pack(fill="x", pady=(4, 0))

        self._activate_status = ctk.CTkLabel(sc, text="",
                                              font=ctk.CTkFont(size=12),
                                              wraplength=700, justify="center")
        self._activate_status.pack(pady=(8, 0))

        # Render inicial del preview
        self._on_plan_select("pro")

    def _on_plan_select(self, plan_key: str):
        for w in self._preview_inner.winfo_children():
            w.destroy()
        plan  = PLANS.get(plan_key, PLANS["free"])
        color = plan["color"]

        ctk.CTkLabel(self._preview_inner,
                     text=f"{plan['icon']}  {plan['name']} — {plan['description']}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=color).pack(anchor="w", pady=(0, 8))

        feats_f = ctk.CTkFrame(self._preview_inner, fg_color="transparent")
        feats_f.pack(fill="x")
        feats_f.columnconfigure((0, 1), weight=1)

        feat_items = list(plan["features"].items())
        for idx, (feat, val) in enumerate(feat_items):
            label_txt = FEATURE_LABELS.get(feat, feat)
            if isinstance(val, bool):
                icon_t  = "✓" if val else "✗"
                tc      = theme.C_GREEN if val else "#64748b"
                display = label_txt
            elif isinstance(val, int):
                icon_t  = "✓"
                tc      = theme.C_GREEN
                display = f"{label_txt}: {'Ilimitados' if val == -1 else val}"
            elif isinstance(val, str):
                icon_t  = "✓"
                tc      = theme.C_GREEN
                display = f"{label_txt}: {SOPORTE_LABELS.get(val, val)}"
            else:
                continue

            row_f = ctk.CTkFrame(feats_f, fg_color="transparent")
            row_f.grid(row=idx // 2, column=idx % 2, sticky="w", padx=4, pady=1)
            ctk.CTkLabel(row_f, text=icon_t, width=16,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=tc).pack(side="left")
            ctk.CTkLabel(row_f, text=display,
                         font=ctk.CTkFont(size=10),
                         text_color=theme.TEXT if val else "#64748b").pack(side="left")

    def _validate_code(self):
        code = self._code_entry.get().strip().upper()
        if not code:
            self._code_status.configure(text="Ingresá un código.",
                                         text_color=theme.C_RED)
            return
        # Códigos demo válidos
        valid = {
            "DEMO-FREE":       "free",
            "DEMO-STARTER":    "starter",
            "DEMO-PRO":        "pro",
            "DEMO-ENTERPRISE": "enterprise",
            "CS-BETA-2024":    "pro",
            "CORESTACK-GRATIS":"starter",
        }
        if code in valid:
            matched_plan = valid[code]
            self._activate_plan_var.set(matched_plan)
            self._on_plan_select(matched_plan)
            self._code_status.configure(
                text=f"✓ Código válido — Plan {PLANS[matched_plan]['name']} desbloqueado.",
                text_color=theme.C_GREEN)
        else:
            self._code_status.configure(
                text="✗ Código inválido. Verificá que esté escrito correctamente.",
                text_color=theme.C_RED)

    def _activate_plan_action(self):
        plan_key = self._activate_plan_var.get()
        code     = self._code_entry.get().strip().upper()

        # Verificar código para planes de pago
        if plan_key != "free" and not code:
            self._activate_status.configure(
                text="Para activar un plan de pago necesitás un código de activación.",
                text_color=theme.C_ORANGE)
            return

        plan_name = PLANS[plan_key]["name"]
        if not messagebox.askyesno(
            "Confirmar activación",
            f"¿Activar el plan {plan_name}?\n\n"
            f"El plan actual ({PLANS[self._current_key]['name']}) será reemplazado."
        ):
            return

        self._activate_btn.configure(state="disabled", text="Activando...")
        self._activate_status.configure(text="Procesando...", text_color=theme.TEXT_DIM)

        def _run():
            try:
                duration = int(self._duration_var.get())
                _activate_plan(
                    plan_key=plan_key,
                    payment_ref=code,
                    activated_by=self.user.get("username", ""),
                    duration_days=duration,
                )
                self.after(0, lambda: self._on_activate_success(plan_key))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_activate_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_activate_success(self, plan_key: str):
        plan_name = PLANS[plan_key]["name"]
        self._activate_btn.configure(state="normal", text="✅  Activar plan")
        self._activate_status.configure(
            text=f"¡Plan {plan_name} activado correctamente!",
            text_color=theme.C_GREEN)
        messagebox.showinfo(
            "Plan activado",
            f"✅ ¡Bienvenido al plan {plan_name}!\n\n"
            "Las nuevas funcionalidades ya están disponibles.\n"
            "Reiniciá la sesión si algún módulo no aparece aún.")
        self.on_show()

    def _on_activate_error(self, error: str):
        self._activate_btn.configure(state="normal", text="✅  Activar plan")
        self._activate_status.configure(
            text=f"Error al activar: {error}", text_color=theme.C_RED)

    # ══════════════════════════════════════════════════════
    #  Tab 3 — Comparar planes (tabla)
    # ══════════════════════════════════════════════════════
    def _build_compare_tab(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        ctk.CTkLabel(sc, text="Comparación detallada de planes",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 12))

        plan_keys   = list(PLANS.keys())
        plan_colors = [PLANS[k]["color"] for k in plan_keys]

        # Encabezado
        hdr_f = ctk.CTkFrame(sc, fg_color=theme.CARD, corner_radius=10)
        hdr_f.pack(fill="x", pady=(0, 2))
        hdr_inner = ctk.CTkFrame(hdr_f, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=8, pady=10)
        hdr_inner.columnconfigure(0, weight=2)
        for i in range(len(plan_keys)):
            hdr_inner.columnconfigure(i + 1, weight=1)

        ctk.CTkLabel(hdr_inner, text="Característica",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_DIM, anchor="w").grid(
            row=0, column=0, sticky="w", padx=8)

        for col, (pk, color) in enumerate(zip(plan_keys, plan_colors)):
            is_cur = pk == self._current_key
            ctk.CTkLabel(hdr_inner,
                         text=f"{PLANS[pk]['icon']} {PLANS[pk]['name']}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=color).grid(row=0, column=col + 1, padx=4)
            if is_cur:
                ctk.CTkLabel(hdr_inner, text="◀ actual",
                             font=ctk.CTkFont(size=8),
                             text_color=color).grid(row=1, column=col + 1)

        # Filas de features
        all_feats = list(FEATURE_LABELS.keys())
        for ridx, feat in enumerate(all_feats):
            bg = theme.CARD if ridx % 2 == 0 else theme.CARD2
            row_f = ctk.CTkFrame(sc, fg_color=bg, corner_radius=6)
            row_f.pack(fill="x", pady=1)
            row_inner = ctk.CTkFrame(row_f, fg_color="transparent")
            row_inner.pack(fill="x", padx=8, pady=6)
            row_inner.columnconfigure(0, weight=2)
            for i in range(len(plan_keys)):
                row_inner.columnconfigure(i + 1, weight=1)

            ctk.CTkLabel(row_inner, text=FEATURE_LABELS[feat],
                         font=ctk.CTkFont(size=11), text_color=theme.TEXT,
                         anchor="w").grid(row=0, column=0, sticky="w", padx=8)

            for col, pk in enumerate(plan_keys):
                val = PLANS[pk]["features"].get(feat)
                if isinstance(val, bool):
                    txt   = "✓" if val else "—"
                    color = theme.C_GREEN if val else "#64748b"
                elif isinstance(val, int):
                    txt   = "∞" if val == -1 else str(val)
                    color = theme.C_GREEN
                elif isinstance(val, str):
                    txt   = SOPORTE_LABELS.get(val, val)[:20]
                    color = theme.C_GREEN
                else:
                    txt   = "—"
                    color = "#64748b"
                ctk.CTkLabel(row_inner, text=txt,
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=color).grid(row=0, column=col + 1, padx=4)

    # ══════════════════════════════════════════════════════
    #  Tab 4 — Historial
    # ══════════════════════════════════════════════════════
    def _build_history_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Historial de cambios de plan",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="↻ Actualizar", width=110, height=30,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self._load_history).pack(side="right")

        cols    = ("Plan anterior", "Plan nuevo", "Fecha", "Activado por", "Referencia")
        widths  = [140, 140, 160, 130, 160]
        anchors = ["center", "center", "center", "center", "center"]
        self._hist_tf, self._hist_tree = W.make_tree(parent, cols, widths, anchors, height=14)
        self._hist_tf.pack(fill="both", expand=True)

        for pk, plan in PLANS.items():
            self._hist_tree.tag_configure(pk, foreground=plan["color"])

    def _load_history(self):
        self._hist_tree.delete(*self._hist_tree.get_children())
        rows = _get_plan_history()
        for (old_plan, new_plan, changed_at, changed_by, reason) in rows:
            old_name = PLANS.get(old_plan or "", {}).get("name", old_plan or "—")
            new_name = PLANS.get(new_plan,     {}).get("name", new_plan)
            self._hist_tree.insert("", "end", values=(
                old_name,
                new_name,
                str(changed_at)[:16] if changed_at else "—",
                changed_by or "sistema",
                reason or "—",
            ), tags=(new_plan,) if new_plan in PLANS else ())

    def _refresh_treeview_style(self):
        if hasattr(self, "_hist_tree"):
            self._hist_tree.configure(style="Cs.Treeview")

    # ══════════════════════════════════════════════════════
    #  Ciclo de vida
    # ══════════════════════════════════════════════════════
    def on_show(self):
        def _load():
            sub = _get_active_subscription()
            key = get_current_plan_key()
            self.after(0, lambda s=sub, k=key: self._apply_data(s, k))

        threading.Thread(target=_load, daemon=True).start()

    def _apply_data(self, sub, key):
        self._sub_info    = sub
        self._current_key = key
        self._refresh_banner()

        # Rebuildar la tab de planes para reflejar el plan activo
        plans_tab = self._tabs.tab("Planes disponibles")
        for w in plans_tab.winfo_children():
            w.destroy()
        self._build_plans_tab(plans_tab)

        # Rebuildar comparativa
        compare_tab = self._tabs.tab("Comparar planes")
        for w in compare_tab.winfo_children():
            w.destroy()
        self._build_compare_tab(compare_tab)

        # Historial
        self._load_history()