"""
mercadolibre.py - Modulo MercadoLibre para CoreStack Pro v0.9
Incluye: Catalogo, Ordenes, Envios/Packaging, Mensajeria completa,
         Reviews, Editor de publicaciones, Configuracion OAuth.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading
import webbrowser
import urllib.parse as _uparse

import ml_api
import theme
import widgets as W

# Color de marca MeLi
C_MELI  = "#ffe600"
C_MELIA = "#3483fa"

STATUS_LABELS = {
    "active":             "Activa",
    "paused":             "Pausada",
    "closed":             "Cerrada",
    "under_review":       "En revision",
    "paid":               "Pagada",
    "payment_in_process": "Pago en proceso",
    "pending":            "Pendiente",
    "shipped":            "Enviada",
    "delivered":          "Entregada",
    "cancelled":          "Cancelada",
    "payment_required":   "Requiere pago",
    "ready_to_ship":      "Listo para enviar",
    "handling":           "Preparando",
    "in_transit":         "En camino",
}

SHIPPING_STATUS_LABELS = {
    "pending":        "Pendiente",
    "handling":       "Preparando",
    "ready_to_ship":  "Listo p/ enviar",
    "shipped":        "Despachado",
    "in_transit":     "En camino",
    "delivered":      "Entregado",
    "not_delivered":  "No entregado",
    "cancelled":      "Cancelado",
}

LEVEL_COLORS = {
    "1_red":         theme.C_RED,
    "2_orange":      theme.C_ORANGE,
    "3_yellow":      "#f5c518",
    "4_light_green": "#86efac",
    "5_green":       theme.C_GREEN,
}

# Plantillas predeterminadas de mensajes (editables en UI)
DEFAULT_TEMPLATES = [
    ("Factura adjuntada",
     "Hola! Te informamos que tu factura electrónica fue adjuntada al pedido. Ante cualquier consulta, quedamos a tu disposición. ¡Gracias por tu compra!"),
    ("Número de seguimiento",
     "Hola! El número de seguimiento de tu envío es: [NÚMERO]. Podés rastrearlo en el sitio del correo. ¡Cualquier consulta avisanos!"),
    ("Gracias por comprar",
     "Hola! Muchas gracias por tu compra. Ya estamos preparando tu pedido para despacharlo a la brevedad. Ante cualquier consulta, estamos a tu disposición. ¡Saludos!"),
    ("Pedido despachado",
     "Hola! Tu pedido ya fue despachado y está en camino. En los próximos días lo vas a recibir. ¡Gracias por elegirnos!"),
    ("Demora en el envío",
     "Hola! Te queremos avisar que tu pedido sufrió una pequeña demora. Estamos trabajando para resolverlo lo antes posible. Te pedimos disculpas por los inconvenientes. ¡Gracias por tu paciencia!"),
    ("Consulta recibida",
     "Hola! Recibimos tu consulta y te vamos a responder a la brevedad. Muchas gracias por comunicarte con nosotros."),
    ("Producto listo para despacho",
     "Hola! Tu producto ya está listo para ser despachado. En las próximas horas lo entregamos al correo. ¡Muchas gracias!"),
    ("Problema con el envío",
     "Hola! Detectamos un inconveniente con el envío de tu pedido. Por favor comunicate con nosotros para resolverlo a la brevedad. Disculpá los inconvenientes."),
]

# Redirect URI — debe estar configurada en tu app ML Developer
# Usa https://www.mercadolibre.com.ar/ (no necesita servidor local ni ngrok)
ML_REDIRECT_URI = "https://coresstack.onrender.com/oauth/callback"
ML_APP_ID_CORRECTO = "1122439897772462"
ML_CLIENT_SECRET_CORRECTO = "ehpreKOTMLZhYquI3feZRGXkNvzSHZJ"

def _force_ml_credentials():
    """Fuerza las credenciales correctas en ambas DBs al iniciar, pisando valores viejos."""
    try:
        from api import set_setting
        set_setting("ml_app_id",        ML_APP_ID_CORRECTO)
        set_setting("ml_client_secret", ML_CLIENT_SECRET_CORRECTO)
        set_setting("ml_redirect_uri",  ML_REDIRECT_URI)
    except Exception:
        pass
    # Sincronizar también a Neon, que es donde ml_api realmente lee
    try:
        ml_api._set_ml_setting("ml_app_id",        ML_APP_ID_CORRECTO)
        ml_api._set_ml_setting("ml_client_secret", ML_CLIENT_SECRET_CORRECTO)
        ml_api._set_ml_setting("ml_redirect_uri",  ML_REDIRECT_URI)
    except Exception:
        pass

_force_ml_credentials()


def _fmt_dt(raw: str) -> str:
    if not raw:
        return "-"
    try:
        return str(raw)[:16].replace("T", " ")
    except Exception:
        return str(raw)[:16]


# ══════════════════════════════════════════════════════════════
#  Helper OAuth: servidor HTTPS local con cert autofirmado
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  Helper OAuth: abre el navegador y espera código manual
#  (sin servidor local, sin ngrok, sin SSL)
# ══════════════════════════════════════════════════════════════

def _oauth_https_flow(app_id: str, on_code, on_error, on_waiting):
    """
    Abre la URL de autorización ML en el navegador.
    ML redirige a ML_REDIRECT_URI con ?code=TG-xxx en la barra de direcciones.
    El usuario copia ese código y lo pega en el campo 'Vincular manual'.
    on_waiting se llama para actualizar el status; on_code no se llama automáticamente
    (el código lo ingresa el usuario manualmente).
    """
    def _run():
        params_str = _uparse.urlencode({
            "response_type": "code",
            "client_id":     app_id,
            "redirect_uri":  ML_REDIRECT_URI,
        })
        url = f"https://auth.mercadolibre.com.ar/authorization?{params_str}"
        webbrowser.open(url)
        on_waiting()

    threading.Thread(target=_run, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  FRAME PRINCIPAL
# ══════════════════════════════════════════════════════════════

class MercadolibreFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._ml_user_id: str     = ""
        self._accounts: list      = []
        self._sel_listing_id: str = ""
        self._sel_ml_item_id: str = ""
        self._sel_order_id: int   = 0
        self._current_pack_id: int = 0
        self._templates: list     = list(DEFAULT_TEMPLATES)
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  Layout
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_header()

        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=24, pady=(0, 8))

        self._tabs = ctk.CTkTabview(self, anchor="w")
        self._tabs.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._build_catalog_tab(self._tabs.add("Catalogo"))
        self._build_orders_tab(self._tabs.add("Ordenes"))
        self._build_shipping_tab(self._tabs.add("Envios"))
        self._build_messages_tab(self._tabs.add("Mensajeria"))
        self._build_reviews_tab(self._tabs.add("Reviews"))
        self._build_editor_tab(self._tabs.add("Editor"))
        self._build_config_tab(self._tabs.add("Configuracion"))

    # ── Header ─────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))

        brand = ctk.CTkFrame(hdr, fg_color=C_MELIA, corner_radius=8,
                             width=36, height=36)
        brand.pack(side="left"); brand.pack_propagate(False)
        ctk.CTkLabel(brand, text="ML", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#ffffff").pack(expand=True)

        ctk.CTkLabel(hdr, text="MercadoLibre",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=theme.TEXT).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(hdr, text="Cuenta:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(20, 6))
        self._account_var = ctk.StringVar(value="—")
        self._account_menu = ctk.CTkOptionMenu(
            hdr, variable=self._account_var,
            values=["—"], width=180, height=30,
            command=self._on_account_change)
        self._account_menu.pack(side="left")

        ctk.CTkButton(hdr, text="Actualizar", width=90, height=30,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12),
                      command=self.on_show).pack(side="right", padx=(4, 0))

        self._status_lbl = ctk.CTkLabel(hdr, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=theme.TEXT_DIM)
        self._status_lbl.pack(side="right", padx=(0, 12))

    # ── KPIs ───────────────────────────────────────────────
    def _refresh_kpis(self):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        if not self._ml_user_id:
            return
        for i in range(6):
            self._kpi_row.columnconfigure(i, weight=1)
        try:
            s = ml_api.get_ml_dashboard_stats(self._ml_user_id)
        except Exception:
            return

        sla_color = theme.C_RED if s["sla_alerts"] > 0 else theme.C_GREEN

        for col, (lbl, val, sub, color) in enumerate([
            ("Publicaciones activas", str(s["active_listings"]),         "en MeLi",        C_MELIA),
            ("Unidades vendidas",     str(s["total_sold"]),               "historial total", theme.C_GREEN),
            ("Precio promedio",       f"${s['avg_price']:,.0f}",          "publicaciones",   theme.C_BLUE),
            ("Ordenes pendientes",    str(s["pending_orders"]),           "sin despachar",   theme.C_ORANGE),
            ("Alertas SLA",           str(s["sla_alerts"]),               "a vencer <12hs",  sla_color),
            ("Ingresos este mes",     f"${s['month_revenue']:,.0f}",      "MeLi",            theme.C_GREEN),
        ]):
            W.kpi_card(self._kpi_row, "", lbl, val, sub, color, col)

    # ══════════════════════════════════════════════════════
    #  TAB 1 — CATÁLOGO (mapeo ID interno ↔ ML)
    #  El precio y stock se controlan desde Inventario.
    #  Esta pantalla solo gestiona vínculos y sincronización.
    # ══════════════════════════════════════════════════════
    def _build_catalog_tab(self, parent):
        # Info banner
        info = ctk.CTkFrame(parent, fg_color=("#dbeafe","#1e3a5f"),
                            corner_radius=10)
        info.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(info,
                     text="El precio y stock se gestionan desde Inventario → ML Mapear.\n"
                          "Esta pantalla muestra los vínculos activos y permite importar el catálogo.",
                     text_color=("#1d4ed8","#93c5fd"),
                     font=ctk.CTkFont(size=11), justify="left").pack(
            anchor="w", padx=14, pady=10)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Vínculos Inventario ↔ MercadoLibre",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        ctk.CTkButton(top, text="Importar catálogo ML", width=170, height=32,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=12),
                      command=self._import_catalog).pack(side="right")
        ctk.CTkButton(top, text="Sync stock", width=110, height=32,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._sync_all_stocks).pack(side="right", padx=(0, 6))

        self._cat_progress = ctk.CTkProgressBar(parent, height=5, corner_radius=3)
        self._cat_progress.pack(fill="x", pady=(0, 4))
        self._cat_progress.set(0)
        self._cat_progress_lbl = ctk.CTkLabel(parent, text="",
                                               font=ctk.CTkFont(size=10),
                                               text_color=theme.TEXT_DIM)
        self._cat_progress_lbl.pack(anchor="w", pady=(0, 6))

        # Filtros — solo búsqueda y estado
        bar = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=8,
                           border_width=1, border_color=theme.SEP)
        bar.pack(fill="x", pady=(0, 8))
        self._cat_search_var = ctk.StringVar()
        self._cat_search_var.trace_add("write", lambda *_: self._load_catalog())
        ctk.CTkEntry(bar, textvariable=self._cat_search_var,
                     placeholder_text="Buscar publicación...",
                     width=260, height=32, border_width=0,
                     fg_color="transparent").pack(side="left", padx=12, pady=8)
        self._cat_status_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(bar, variable=self._cat_status_var,
                          values=["Todos", "active", "paused", "closed"],
                          width=120, height=30,
                          command=lambda _: self._load_catalog()).pack(side="left")

        # Solo mostrar ítems vinculados
        self._only_linked_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar, text="Solo vinculados",
                        variable=self._only_linked_var,
                        command=self._load_catalog,
                        font=ctk.CTkFont(size=11)).pack(side="left", padx=12)

        self._cat_count_lbl = ctk.CTkLabel(bar, text="",
                                            text_color=theme.TEXT_DIM,
                                            font=ctk.CTkFont(size=11))
        self._cat_count_lbl.pack(side="right", padx=14)

        # Tabla simplificada: solo datos de vínculo
        cols    = ("ML Item ID", "Título ML", "Estado", "Producto CS", "Sync stock", "Última sync")
        widths  = [120, 300, 90, 200, 90, 130]
        anchors = ["center", "w", "center", "w", "center", "center"]
        self._cat_tf, self._cat_tree = W.make_tree(
            parent, cols, widths, anchors, height=16)
        self._cat_tree.tag_configure("active",    foreground=theme.C_GREEN)
        self._cat_tree.tag_configure("paused",    foreground=theme.C_ORANGE)
        self._cat_tree.tag_configure("closed",    foreground=theme.TEXT_DIM[1])
        self._cat_tree.tag_configure("unlinked",  foreground=theme.TEXT_DIM[1])
        self._cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)
        self._cat_tree.bind("<Double-1>", lambda _: self._open_editor_for_selected())
        self._cat_tf.pack(fill="both", expand=True)

        ctk.CTkLabel(parent,
                     text="Doble clic → editar publicación  |  "
                          "Para vincular a un producto: Inventario → seleccionar producto → ML Mapear",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).pack(
            anchor="w", pady=(4, 0))

    def _load_catalog(self):
        self._cat_tree.delete(*self._cat_tree.get_children())
        if not self._ml_user_id:
            return
        status = "" if self._cat_status_var.get() == "Todos" else self._cat_status_var.get()
        rows = ml_api.get_listings_local(
            ml_user_id=self._ml_user_id,
            status=status,
            search=self._cat_search_var.get().strip())

        only_linked = getattr(self, "_only_linked_var", None)
        only_linked = only_linked.get() if only_linked else False

        shown = 0
        for row in rows:
            (id_l, ml_item_id, title, price, avail_qty, sold_qty, st,
             listing_type, thumbnail, last_sync, sync_stock,
             product_name, id_prod, permalink) = row

            # Filtro "solo vinculados"
            if only_linked and not id_prod:
                continue

            tag = st if st in ("active", "paused", "closed") else ""
            if not id_prod:
                tag = "unlinked"

            prod_display = (product_name or "—")[:35] if id_prod else "⚠ Sin vincular"
            sync_display = "✅ Activo" if sync_stock else "—"

            self._cat_tree.insert("", "end", iid=str(id_l), values=(
                ml_item_id,
                (title or "—")[:55],
                STATUS_LABELS.get(st, st),
                prod_display,
                sync_display,
                _fmt_dt(str(last_sync)),
            ), tags=(tag,) if tag else ())
            shown += 1

        vinculados = sum(1 for r in rows if r[12])
        self._cat_count_lbl.configure(
            text=f"{shown} publicaciones | {vinculados} vinculadas a Inventario")

    def _on_cat_select(self, _=None):
        sel = self._cat_tree.selection()
        if sel:
            self._sel_listing_id = sel[0]
            vals = self._cat_tree.item(sel[0])["values"]
            self._sel_ml_item_id = vals[0] if vals else ""

    def _import_catalog(self):
        if not self._ml_user_id:
            messagebox.showwarning("Sin cuenta", "Vinculá una cuenta ML primero.")
            return
        self._cat_progress.set(0)
        self._cat_progress_lbl.configure(text="Iniciando importación...")

        def _run():
            def _cb(current, total):
                pct = current / total if total > 0 else 0
                self.after(0, lambda p=pct, c=current, t=total: (
                    self._cat_progress.set(p),
                    self._cat_progress_lbl.configure(text=f"Importando {c}/{t}...")
                ))
            try:
                result = ml_api.import_catalog(self._ml_user_id, progress_cb=_cb)
                self.after(0, lambda r=result: (
                    self._cat_progress.set(1),
                    self._cat_progress_lbl.configure(
                        text=f"Completado: {r['imported']} publicaciones importadas, {r['errors']} errores"),
                    self._load_catalog(),
                    self._refresh_kpis(),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): (
                    self._cat_progress_lbl.configure(
                        text=f"Error: {err}", text_color=theme.C_RED),
                    messagebox.showerror("Error importación", err)
                ))

        threading.Thread(target=_run, daemon=True).start()

    def _sync_all_stocks(self):
        if not self._ml_user_id:
            messagebox.showwarning("Sin cuenta", "Vinculá una cuenta ML primero.")
            return
        self._status_lbl.configure(text="Sincronizando stock...")
        def _run():
            try:
                r = ml_api.sync_all_stocks(self._ml_user_id)
                self.after(0, lambda: (
                    self._status_lbl.configure(
                        text=f"Stock sync: {r['synced']} OK, {r['errors']} errores"),
                    self._load_catalog()
                ))
            except Exception as e:
                self.after(0, lambda err=str(e):
                    self._status_lbl.configure(text=f"Error sync: {err}"))
        threading.Thread(target=_run, daemon=True).start()

    def _open_editor_for_selected(self):
        if self._sel_ml_item_id:
            self._editor_item_e.delete(0, "end")
            self._editor_item_e.insert(0, self._sel_ml_item_id)
            self._tabs.set("Editor")
            self._load_editor_item()

    # ══════════════════════════════════════════════════════
    #  TAB 2 — ÓRDENES
    #  Vista compacta: descarga + acciones de mensajería/AFIP.
    #  La gestión de despacho se hace desde el módulo Despacho.
    # ══════════════════════════════════════════════════════
    def _build_orders_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Órdenes ML",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Descargar órdenes", width=160, height=32,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      command=self._fetch_orders_bg).pack(side="right")

        # Banner de redirección a Despacho
        redir = ctk.CTkFrame(parent, fg_color=("#dbeafe","#1e3a5f"), corner_radius=10)
        redir.pack(fill="x", pady=(0, 10))
        ri = ctk.CTkFrame(redir, fg_color="transparent")
        ri.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(ri,
                     text="📦  Para empaquetar y despachar, usá el módulo Despacho del menú lateral.\n"
                          "    Ahí encontrás la cola unificada con SLA, etiquetas y acciones rápidas.",
                     text_color=("#1d4ed8","#93c5fd"),
                     font=ctk.CTkFont(size=11), justify="left").pack(side="left")
        ctk.CTkButton(ri, text="Ir a Despacho →", width=130, height=30,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      command=self._go_to_dispatch).pack(side="right")

        # SLA banner
        self._sla_banner = ctk.CTkFrame(parent, fg_color=theme.BTN_RED, corner_radius=8)
        self._sla_lbl = ctk.CTkLabel(self._sla_banner, text="",
                                      text_color="#ffffff",
                                      font=ctk.CTkFont(size=12, weight="bold"))
        self._sla_lbl.pack(padx=14, pady=8)

        # Filtros
        bar = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=8,
                           border_width=1, border_color=theme.SEP)
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(bar, text="Estado:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=12, pady=8)
        self._ord_status_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(
            bar, variable=self._ord_status_var,
            values=["Todos", "paid", "payment_in_process",
                    "shipped", "delivered", "cancelled"],
            width=160, height=30,
            command=lambda _: self._load_orders()).pack(side="left")
        self._ord_count_lbl = ctk.CTkLabel(bar, text="",
                                            text_color=theme.TEXT_DIM,
                                            font=ctk.CTkFont(size=11))
        self._ord_count_lbl.pack(side="right", padx=14)

        cols    = ("Orden #", "Comprador", "Publicacion",
                   "Cant.", "Total", "Estado", "Límite SLA", "AFIP", "Fecha")
        widths  = [110, 130, 240, 50, 100, 110, 130, 50, 130]
        anchors = ["center","w","w","center","e","center","center","center","center"]
        self._ord_tf, self._ord_tree = W.make_tree(
            parent, cols, widths, anchors, height=11)
        self._ord_tree.tag_configure("paid",      foreground=theme.C_GREEN)
        self._ord_tree.tag_configure("shipped",   foreground=theme.C_BLUE)
        self._ord_tree.tag_configure("cancelled", foreground=theme.C_RED)
        self._ord_tree.tag_configure("sla_warn",  foreground=theme.C_ORANGE)
        self._ord_tree.tag_configure("sla_crit",  foreground=theme.C_RED)
        self._ord_tree.bind("<<TreeviewSelect>>", self._on_order_select)
        self._ord_tf.pack(fill="both", expand=True)

        act = ctk.CTkFrame(parent, fg_color="transparent")
        act.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(act, text="Mensajería", width=110, height=30,
                      fg_color=theme.BTN_PURPLE, hover_color=theme.BTN_PURPLEH,
                      command=self._go_to_messages_for_order).pack(side="left", padx=(0, 6))
        ctk.CTkButton(act, text="Enviar factura AFIP", width=170, height=30,
                      fg_color=theme.BTN_ORANGE, hover_color=theme.BTN_ORANGEH,
                      command=self._send_afip_msg).pack(side="left")

    def _load_orders(self):
        self._ord_tree.delete(*self._ord_tree.get_children())
        if not self._ml_user_id:
            return
        status = "" if self._ord_status_var.get() == "Todos" else self._ord_status_var.get()
        rows = ml_api.get_orders_local(ml_user_id=self._ml_user_id, status=status)
        now  = datetime.now()

        sla_alerts = ml_api.get_sla_alerts(self._ml_user_id)
        if sla_alerts:
            self._sla_banner.pack(fill="x", pady=(0, 8), before=self._ord_tf)
            self._sla_lbl.configure(
                text=f"ALERTA SLA: {len(sla_alerts)} orden(es) a vencer — despachar YA")
        else:
            self._sla_banner.pack_forget()

        self._ord_data = rows
        for row in rows:
            (id_ml_ord, ml_order_id, buyer, qty, unit_price, total,
             st, ship_st, date_cr, sla_limit, afip_sent, afip_cae, title) = row

            tag = st
            if sla_limit and st in ("paid", "payment_in_process"):
                try:
                    sla_dt = datetime.strptime(str(sla_limit)[:16], "%Y-%m-%d %H:%M")
                    hours_left = (sla_dt - now).total_seconds() / 3600
                    if hours_left < 0:
                        tag = "sla_crit"
                    elif hours_left < 12:
                        tag = "sla_warn"
                except Exception:
                    pass

            self._ord_tree.insert("", "end", iid=str(id_ml_ord), values=(
                ml_order_id,
                (buyer or "—")[:20],
                (title or "—")[:40],
                qty,
                f"${float(total):,.0f}",
                STATUS_LABELS.get(st, st),
                _fmt_dt(str(sla_limit)) if sla_limit else "—",
                "✅" if afip_sent else "—",
                _fmt_dt(str(date_cr)),
            ), tags=(tag,) if tag else ())

        self._ord_count_lbl.configure(text=f"{len(rows)} órdenes")

    def _go_to_dispatch(self):
        """Navega al módulo Despacho en la app principal."""
        try:
            # Buscar la app principal subiendo por los padres
            w = self
            while w is not None:
                if hasattr(w, "_navigate"):
                    w._navigate("dispatch")
                    return
                w = getattr(w, "master", None)
        except Exception:
            pass
        messagebox.showinfo("Despacho",
                            "Abrí el módulo Despacho desde el menú lateral.")

    def _on_order_select(self, _=None):
        sel = self._ord_tree.selection()
        self._sel_order_id = int(sel[0]) if sel else 0

    def _fetch_orders_bg(self):
        if not self._ml_user_id:
            messagebox.showwarning("Sin cuenta", "Vinculá una cuenta ML primero.")
            return
        self._status_lbl.configure(text="Descargando órdenes...")
        def _run():
            try:
                ml_api.fetch_recent_orders(self._ml_user_id, limit=100)
                self.after(0, lambda: (
                    self._load_orders(),
                    self._refresh_kpis(),
                    self._status_lbl.configure(text="Órdenes actualizadas"),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): (
                    self._status_lbl.configure(text=f"Error: {err}"),
                    messagebox.showerror("Error órdenes", err)
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _get_selected_order_row(self):
        if not self._sel_order_id or not hasattr(self, "_ord_data"):
            return None
        return next((r for r in self._ord_data if r[0] == self._sel_order_id), None)

    def _view_shipping(self):
        """Redirige al módulo Despacho."""
        self._go_to_dispatch()

    def _go_to_shipping_tab(self):
        """Redirige al módulo Despacho."""
        self._go_to_dispatch()

    def _go_to_messages_for_order(self):
        row = self._get_selected_order_row()
        if not row:
            messagebox.showwarning("Sin selección", "Seleccioná una orden.")
            return
        self._msg_pack_e.delete(0, "end")
        self._msg_pack_e.insert(0, str(row[1]))
        self._tabs.set("Mensajeria")
        self._load_messages()

    def _send_afip_msg(self):
        row = self._get_selected_order_row()
        if not row:
            messagebox.showwarning("Sin selección", "Seleccioná una orden.")
            return
        if not row[11]:
            messagebox.showinfo("Sin CAE", "Esta orden no tiene CAE registrado.")
            return
        AfipMsgDialog(self, ml_user_id=self._ml_user_id,
                      ml_pack_id=row[1], cae=row[11])

    # ══════════════════════════════════════════════════════
    #  TAB 3 — ENVÍOS  →  redirige a módulo Despacho
    # ══════════════════════════════════════════════════════
    def _build_shipping_tab(self, parent):
        """
        Esta pestaña ya no gestiona envíos directamente.
        Toda la logística de despacho se centraliza en el módulo
        'Despacho' del menú lateral, que unifica todos los canales.
        Aquí dejamos un panel informativo con acceso directo y
        un buscador de detalle de envío por ID (para uso rápido).
        """
        # Banner principal
        hero = ctk.CTkFrame(parent, fg_color="#1e3a5f", corner_radius=14)
        hero.pack(fill="x", pady=(0, 16))
        hi = ctk.CTkFrame(hero, fg_color="transparent")
        hi.pack(fill="x", padx=24, pady=20)

        ctk.CTkLabel(hi, text="📦",
                     font=ctk.CTkFont(size=40)).pack(side="left", padx=(0, 20))
        txt = ctk.CTkFrame(hi, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text="Gestión de Despacho Centralizada",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#e2e8f0").pack(anchor="w")
        ctk.CTkLabel(txt,
                     text="Los envíos de MercadoLibre ahora se gestionan desde el módulo\n"
                          "Despacho, junto con otros canales futuros (e-commerce, etc.).\n"
                          "Desde ahí podés empaquetar, imprimir etiquetas y marcar despachos.",
                     text_color="#94a3b8",
                     font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(hi, text="Ir a Despacho →",
                      width=160, height=42,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._go_to_dispatch).pack(side="right")

        # Separador
        ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=(0, 16))

        # Buscador rápido de detalle de envío (funcionalidad que sí es útil aquí)
        ctk.CTkLabel(parent, text="Consulta rápida de envío por ID de orden",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(0, 8))

        bar = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=8,
                           border_width=1, border_color=theme.SEP)
        bar.pack(fill="x", pady=(0, 12))
        bi = ctk.CTkFrame(bar, fg_color="transparent")
        bi.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(bi, text="Orden ML ID:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self._ship_order_e = ctk.CTkEntry(bi, width=160, height=32,
                                           placeholder_text="ej: 123456789")
        self._ship_order_e.pack(side="left", padx=(8, 6))
        ctk.CTkButton(bi, text="Buscar envío", width=110, height=32,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._load_shipping_detail).pack(side="left")

        # Panel de resultado
        self._ship_detail_frame = ctk.CTkFrame(parent, fg_color=theme.CARD2,
                                                corner_radius=10)
        self._ship_detail_lbl = ctk.CTkLabel(
            self._ship_detail_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT, justify="left")
        self._ship_detail_lbl.pack(padx=16, pady=12)

        # Stubs requeridos por métodos existentes que referencian estos atributos
        self._ship_filter_var = ctk.StringVar(value="Todos")
        self._ship_kpi = {}
        self._ship_data = []

    def _load_shipping_list(self):
        """Stub — funcionalidad movida al módulo Despacho."""
        pass

    def _on_ship_select(self, _=None):
        """Stub — funcionalidad movida al módulo Despacho."""
        pass

    def _view_selected_shipping(self):
        self._go_to_dispatch()

    def _print_label(self):
        self._go_to_dispatch()

    def _mark_shipped(self):
        self._go_to_dispatch()

    def _load_shipping_detail(self):
        """Carga el detalle de envío por orden ID ingresado."""
        order_id_str = self._ship_order_e.get().strip()
        if not order_id_str:
            return
        self._status_lbl.configure(text="Buscando envío...")
        def _run():
            try:
                from db import execute_query
                row = execute_query(
                    "SELECT shipping_id, status, buyer_nickname, total_amount "
                    "FROM ml_orders WHERE ml_order_id=%s",
                    (order_id_str,), fetch="one")
                if not row or not row[0]:
                    self.after(0, lambda: self._status_lbl.configure(text="Sin info de envío."))
                    return
                detail = ml_api.get_shipping_detail(self._ml_user_id, int(row[0]))
                self.after(0, lambda d=detail, r=row: self._show_ship_detail_inline(d, r))
            except Exception as e:
                self.after(0, lambda err=str(e):
                    self._status_lbl.configure(text=f"Error: {err}"))
        threading.Thread(target=_run, daemon=True).start()

    def _show_ship_detail_inline(self, detail: dict, order_row):
        self._ship_detail_frame.pack(fill="x", pady=(8, 0))
        tracking = detail.get("tracking_number", "—")
        status   = detail.get("status", "—")
        carrier  = detail.get("shipping_option", {}).get("name", "—")
        eta      = (detail.get("estimated_delivery_final") or {}).get("date", "—")
        addr     = detail.get("receiver_address", {})
        address  = f"{addr.get('street_name','')}, {addr.get('city',{}).get('name','')}"

        text = (
            f"  Comprador: {order_row[2]}  |  Total: ${float(order_row[3]):,.0f}\n"
            f"  Estado envio: {SHIPPING_STATUS_LABELS.get(status, status)}  |  "
            f"Transportista: {carrier}  |  Tracking: {tracking}\n"
            f"  Entrega estimada: {_fmt_dt(str(eta))}  |  "
            f"Direccion: {address.strip(', ')}"
        )
        self._ship_detail_lbl.configure(text=text)
        self._status_lbl.configure(text="Detalle cargado")

    def _view_selected_shipping(self):
        sel = self._ship_tree.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Seleccioná una orden.")
            return
        row_id = int(sel[0])
        if not hasattr(self, "_ship_data"):
            return
        row = next((r for r in self._ship_data if r[0] == row_id), None)
        if row:
            ShippingDialog(self, ml_user_id=self._ml_user_id, ml_order_id=row[1])

    # ══════════════════════════════════════════════════════
    #  TAB 4 — MENSAJERÍA
    # ══════════════════════════════════════════════════════
    def _build_messages_tab(self, parent):
        # --- Header con lista de conversaciones ---
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Mensajeria post-venta",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        ctk.CTkLabel(top, text="Pack / Orden ID:",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(20, 6))
        self._msg_pack_e = ctk.CTkEntry(top, width=150, height=30,
                                         placeholder_text="Ej: 123456789")
        self._msg_pack_e.pack(side="left")
        ctk.CTkButton(top, text="Cargar", width=80, height=30,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._load_messages).pack(side="left", padx=(6, 0))
        ctk.CTkButton(top, text="Actualizar", width=90, height=30,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self._load_messages).pack(side="left", padx=(6, 0))

        # Split: hilo de chat (izq) + panel de envío (der)
        split = ctk.CTkFrame(parent, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # ── Hilo de mensajes ──────────────────────────────
        left = ctk.CTkFrame(split, fg_color=theme.CARD, corner_radius=12,
                            border_width=1, border_color=theme.SEP)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)

        hdr_chat = ctk.CTkFrame(left, fg_color="transparent")
        hdr_chat.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(hdr_chat, text="Hilo de conversacion",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(side="left")
        self._msg_buyer_lbl = ctk.CTkLabel(hdr_chat, text="",
                                            font=ctk.CTkFont(size=11),
                                            text_color=C_MELIA)
        self._msg_buyer_lbl.pack(side="left", padx=(12, 0))

        self._msg_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._msg_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # ── Panel de envío de mensaje ──────────────────────
        right = ctk.CTkFrame(split, fg_color=theme.CARD, corner_radius=12,
                             border_width=1, border_color=theme.SEP)
        right.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right, text="Enviar mensaje",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=14, pady=(12, 4))

        # Plantillas rápidas (scrollable, con más opciones)
        ctk.CTkLabel(right, text="Plantillas rapidas:",
                     font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM).pack(
            anchor="w", padx=14)
        tpl_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent", height=160)
        tpl_scroll.pack(fill="x", padx=14, pady=(4, 6))
        self._tpl_frame = tpl_scroll
        self._rebuild_template_buttons()

        # Separador
        ctk.CTkFrame(right, height=1, fg_color=theme.SEP).pack(fill="x", padx=14, pady=(0, 6))

        # Adjuntar imagen
        attach_row = ctk.CTkFrame(right, fg_color="transparent")
        attach_row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(attach_row, text="Imagen (opcional):",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM).pack(side="left")
        ctk.CTkButton(attach_row, text="Adjuntar", width=80, height=26,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10),
                      command=self._attach_image).pack(side="left", padx=(8, 0))
        self._attach_lbl = ctk.CTkLabel(attach_row, text="Ninguna",
                                         font=ctk.CTkFont(size=10),
                                         text_color=theme.TEXT_DIM)
        self._attach_lbl.pack(side="left", padx=(6, 0))
        self._attached_image_path = ""

        # Mensaje libre
        ctk.CTkLabel(right, text="Mensaje:",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=14)
        self._msg_text = ctk.CTkTextbox(right, height=130, corner_radius=8,
                                         border_color=theme.SEP, border_width=1,
                                         font=ctk.CTkFont(size=12))
        self._msg_text.pack(fill="x", padx=14, pady=(2, 6))

        self._msg_status = ctk.CTkLabel(right, text="",
                                         font=ctk.CTkFont(size=11))
        self._msg_status.pack(anchor="w", padx=14)

        btn_row_msg = ctk.CTkFrame(right, fg_color="transparent")
        btn_row_msg.pack(fill="x", padx=14, pady=(4, 8))
        ctk.CTkButton(btn_row_msg, text="Enviar", height=38,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._send_message).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row_msg, text="Limpiar", width=70, height=38,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self._clear_msg_form).pack(side="left")

        # Editar plantillas
        ctk.CTkFrame(right, height=1, fg_color=theme.SEP).pack(fill="x", padx=14, pady=(2, 4))
        ctk.CTkButton(right, text="Editar plantillas", height=28,
                      fg_color="transparent", hover_color=theme.CARD2,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10),
                      command=self._open_template_editor).pack(anchor="w", padx=14, pady=(0, 8))

    def _rebuild_template_buttons(self):
        for w in self._tpl_frame.winfo_children():
            w.destroy()
        for tpl_name, tpl_text in self._templates:
            ctk.CTkButton(
                self._tpl_frame, text=tpl_name, height=28, corner_radius=6,
                fg_color=theme.CARD2, hover_color=C_MELIA,
                text_color=theme.TEXT, font=ctk.CTkFont(size=10),
                command=lambda t=tpl_text: self._set_msg_template(t)
            ).pack(fill="x", pady=2)

    def _load_messages(self):
        for w in self._msg_scroll.winfo_children():
            w.destroy()
        pack_id_str = self._msg_pack_e.get().strip()
        if not pack_id_str or not pack_id_str.isdigit():
            ctk.CTkLabel(self._msg_scroll,
                         text="Ingresá un Pack/Orden ID y hacé clic en Cargar.",
                         text_color=theme.TEXT_DIM).pack(pady=20)
            return

        pack_id = int(pack_id_str)
        self._current_pack_id = pack_id

        # Buscar nombre del comprador
        def _run():
            try:
                ml_api.get_order_messages(self._ml_user_id, pack_id)
            except Exception:
                pass
            msgs = ml_api.get_messages_local(self._ml_user_id, pack_id)
            # Buscar nickname del comprador
            try:
                from db import execute_query
                buyer_row = execute_query(
                    "SELECT buyer_nickname FROM ml_orders WHERE ml_order_id=%s",
                    (pack_id,), fetch="one")
                buyer_name = buyer_row[0] if buyer_row else ""
            except Exception:
                buyer_name = ""
            self.after(0, lambda m=msgs, b=buyer_name: self._render_messages(m, b))

        threading.Thread(target=_run, daemon=True).start()

    def _render_messages(self, msgs: list, buyer_name: str = ""):
        for w in self._msg_scroll.winfo_children():
            w.destroy()
        if buyer_name:
            self._msg_buyer_lbl.configure(text=f"Comprador: {buyer_name}")
        else:
            self._msg_buyer_lbl.configure(text="")

        if not msgs:
            ctk.CTkLabel(self._msg_scroll,
                         text="Sin mensajes en este hilo.",
                         text_color=theme.TEXT_DIM).pack(pady=20)
            return

        for (from_role, text, sent_at, attachments) in msgs:
            is_seller = from_role == "seller"
            bubble = ctk.CTkFrame(
                self._msg_scroll,
                fg_color=C_MELIA if is_seller else theme.CARD2,
                corner_radius=10)
            bubble.pack(
                anchor="e" if is_seller else "w",
                padx=(60 if is_seller else 0, 0 if is_seller else 60),
                pady=4, fill="none")

            ctk.CTkLabel(bubble, text=text or "—",
                         text_color="#ffffff" if is_seller else theme.TEXT,
                         font=ctk.CTkFont(size=11), wraplength=320,
                         justify="left").pack(padx=10, pady=(6, 2))

            # Mostrar indicador de adjunto si hay
            if attachments and attachments != "[]":
                ctk.CTkLabel(bubble, text="📎 Adjunto",
                             text_color="#e0e0e0" if is_seller else theme.TEXT_DIM,
                             font=ctk.CTkFont(size=9)).pack(padx=10, pady=(0, 2), anchor="w")

            ctk.CTkLabel(bubble,
                         text=f"{'Vos' if is_seller else buyer_name or 'Comprador'} • {_fmt_dt(str(sent_at))}",
                         text_color="#e0e0e0" if is_seller else theme.TEXT_DIM,
                         font=ctk.CTkFont(size=9)).pack(padx=10, pady=(0, 6), anchor="e")

    def _set_msg_template(self, text: str):
        self._msg_text.delete("1.0", "end")
        self._msg_text.insert("1.0", text)

    def _clear_msg_form(self):
        self._msg_text.delete("1.0", "end")
        self._attached_image_path = ""
        self._attach_lbl.configure(text="Ninguna")

    def _attach_image(self):
        path = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.gif *.webp"), ("Todos", "*.*")]
        )
        if path:
            self._attached_image_path = path
            filename = os.path.basename(path)
            self._attach_lbl.configure(text=filename[:30])

    def _send_message(self):
        text = self._msg_text.get("1.0", "end").strip()
        if not text:
            self._msg_status.configure(text="El mensaje no puede estar vacío.",
                                        text_color=theme.C_RED)
            return
        if not self._current_pack_id:
            self._msg_status.configure(text="Cargá un hilo primero.",
                                        text_color=theme.C_RED)
            return
        if not self._ml_user_id:
            self._msg_status.configure(text="Sin cuenta ML vinculada.",
                                        text_color=theme.C_RED)
            return

        self._msg_status.configure(text="Enviando...", text_color=theme.TEXT_DIM)

        # Preparar attachments si hay imagen seleccionada
        attachments = None
        if self._attached_image_path and os.path.isfile(self._attached_image_path):
            # La API de ML requiere subir la imagen primero; simplificamos avisando
            attachments = None
            messagebox.showinfo(
                "Imagen adjunta",
                "Nota: La API de MercadoLibre requiere subir la imagen primero.\n"
                "El mensaje se enviará sin la imagen en esta versión.\n"
                "Podés adjuntarla directamente desde la app de MercadoLibre."
            )

        def _run():
            ok = ml_api.send_message(self._ml_user_id, self._current_pack_id,
                                      text, attachments)
            if ok:
                self.after(0, lambda: (
                    self._msg_status.configure(text="Enviado correctamente.",
                                                text_color=theme.C_GREEN),
                    self._msg_text.delete("1.0", "end"),
                    self._attach_lbl.configure(text="Ninguna"),
                    self.__setattr__("_attached_image_path", ""),
                    self._load_messages()
                ))
            else:
                self.after(0, lambda: self._msg_status.configure(
                    text="Error al enviar.", text_color=theme.C_RED))

        threading.Thread(target=_run, daemon=True).start()

    def _open_template_editor(self):
        TemplateEditorDialog(self, self._templates, self._on_templates_updated)

    def _on_templates_updated(self, new_templates: list):
        self._templates = new_templates
        self._rebuild_template_buttons()

    # ══════════════════════════════════════════════════════
    #  TAB 5 — REVIEWS
    # ══════════════════════════════════════════════════════
    def _build_reviews_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Reviews y reputacion",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        # Reputación del vendedor
        self._rep_frame = ctk.CTkFrame(parent, fg_color=theme.CARD2, corner_radius=12)
        self._rep_frame.pack(fill="x", pady=(0, 10))
        self._rep_inner = ctk.CTkFrame(self._rep_frame, fg_color="transparent")
        self._rep_inner.pack(fill="x", padx=16, pady=14)

        bar = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=8,
                           border_width=1, border_color=theme.SEP)
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(bar, text="ML Item ID:",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(
            side="left", padx=12, pady=8)
        self._rev_item_e = ctk.CTkEntry(bar, width=160, height=30,
                                         placeholder_text="Ej: MLA1234567890")
        self._rev_item_e.pack(side="left")
        ctk.CTkButton(bar, text="Cargar reviews", width=130, height=30,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      command=self._load_reviews).pack(side="left", padx=6)

        self._rev_summary_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._rev_summary_frame.pack(fill="x", pady=(0, 8))

        cols    = ("Estrellas", "Título", "Comentario", "Autor", "Estado", "Fecha")
        widths  = [80, 180, 280, 120, 90, 120]
        anchors = ["center", "w", "w", "center", "center", "center"]
        self._rev_tf, self._rev_tree = W.make_tree(
            parent, cols, widths, anchors, height=10)
        self._rev_tree.tag_configure("5", foreground=theme.C_GREEN)
        self._rev_tree.tag_configure("4", foreground=theme.C_GREEN)
        self._rev_tree.tag_configure("3", foreground=theme.C_ORANGE)
        self._rev_tree.tag_configure("2", foreground=theme.C_RED)
        self._rev_tree.tag_configure("1", foreground=theme.C_RED)
        self._rev_tf.pack(fill="both", expand=True)

    def _load_reviews(self):
        ml_item_id = self._rev_item_e.get().strip()
        if not ml_item_id:
            messagebox.showwarning("Sin item", "Ingresá un ML Item ID.")
            return
        def _run():
            try:
                ml_api.fetch_item_reviews(self._ml_user_id, ml_item_id)
            except Exception:
                pass
            reviews = ml_api.get_reviews_local(ml_item_id)
            summary = ml_api.get_reviews_summary(ml_item_id)
            self.after(0, lambda r=reviews, s=summary: self._render_reviews(r, s))
        threading.Thread(target=_run, daemon=True).start()

    def _render_reviews(self, reviews: list, summary: dict):
        for w in self._rev_summary_frame.winfo_children():
            w.destroy()
        self._rev_summary_frame.columnconfigure((0,1,2,3,4,5), weight=1)
        prom  = summary.get("average", 0)
        total = summary.get("total", 0)
        dist  = summary.get("distribution", {})
        stars_txt = "★" * round(prom) + "☆" * (5 - round(prom))

        c = ctk.CTkFrame(self._rev_summary_frame, fg_color=theme.CARD2, corner_radius=10)
        c.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=(0, 8), pady=2)
        ctk.CTkLabel(c, text=f"{prom:.1f}",
                     font=ctk.CTkFont(size=32, weight="bold"),
                     text_color="#f5c518").pack(pady=(12, 2))
        ctk.CTkLabel(c, text=f"{stars_txt}  ({total} reseñas)",
                     font=ctk.CTkFont(size=12), text_color=theme.TEXT_DIM).pack(pady=(0, 12))

        for col, stars in enumerate([5, 4, 3, 2, 1], start=2):
            count = dist.get(stars, 0)
            color = theme.C_GREEN if stars >= 4 else (theme.C_ORANGE if stars == 3 else theme.C_RED)
            c2 = ctk.CTkFrame(self._rev_summary_frame, fg_color=theme.CARD2, corner_radius=10)
            c2.grid(row=0, column=col, sticky="nsew",
                    padx=(0 if col == 2 else 4, 0), pady=2)
            ctk.CTkLabel(c2, text="★"*stars, text_color="#f5c518",
                         font=ctk.CTkFont(size=14)).pack(pady=(10, 2))
            ctk.CTkLabel(c2, text=str(count), text_color=color,
                         font=ctk.CTkFont(size=18, weight="bold")).pack()
            ctk.CTkLabel(c2, text="reseñas", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=9)).pack(pady=(0, 10))

        self._rev_tree.delete(*self._rev_tree.get_children())
        for (id_r, rating, title, content, reviewer, status, date_cr) in reviews:
            r_str = ("★" * (rating or 0)) if rating else "—"
            self._rev_tree.insert("", "end", values=(
                r_str,
                (title or "—")[:30],
                (content or "—")[:50],
                reviewer or "—",
                status or "—",
                _fmt_dt(str(date_cr)),
            ), tags=(str(rating),) if rating else ())

    # ══════════════════════════════════════════════════════
    #  TAB 6 — EDITOR DE PUBLICACIONES
    # ══════════════════════════════════════════════════════
    def _build_editor_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="Editor de publicaciones",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        bar = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=8,
                           border_width=1, border_color=theme.SEP)
        bar.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(bar, text="ML Item ID:",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(
            side="left", padx=12, pady=8)
        self._editor_item_e = ctk.CTkEntry(bar, width=180, height=30,
                                            placeholder_text="Ej: MLA1234567890")
        self._editor_item_e.pack(side="left")
        ctk.CTkButton(bar, text="Cargar", width=80, height=30,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._load_editor_item).pack(side="left", padx=6)

        self._editor_link_btn = ctk.CTkButton(
            bar, text="Ver en MeLi", width=110, height=30,
            fg_color="transparent", hover_color=theme.CARD2,
            text_color=C_MELIA, font=ctk.CTkFont(size=11),
            command=self._open_in_meli)
        self._editor_link_btn.pack(side="left")
        self._editor_permalink = ""

        self._editor_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._editor_scroll.pack(fill="both", expand=True)

        def lbl(t):
            ctk.CTkLabel(self._editor_scroll, text=t, anchor="w",
                         text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", pady=(8, 0))

        lbl("Título *")
        self._ed_title = ctk.CTkEntry(self._editor_scroll,
                                       placeholder_text="Título de la publicación",
                                       height=36)
        self._ed_title.pack(fill="x", pady=(2, 0))

        # Fila precio + stock + sugerencia de precio
        row_pr = ctk.CTkFrame(self._editor_scroll, fg_color="transparent")
        row_pr.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row_pr, text="Precio ($)", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11), width=120).pack(side="left")
        ctk.CTkLabel(row_pr, text="Stock disponible", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11), width=130).pack(side="left", padx=(20, 0))

        row_pr2 = ctk.CTkFrame(self._editor_scroll, fg_color="transparent")
        row_pr2.pack(fill="x", pady=(2, 0))
        self._ed_price = ctk.CTkEntry(row_pr2, width=140,
                                       placeholder_text="0.00", height=36, justify="center")
        self._ed_price.pack(side="left")
        self._ed_qty = ctk.CTkEntry(row_pr2, width=120,
                                     placeholder_text="0", height=36, justify="center")
        self._ed_qty.pack(side="left", padx=(20, 0))

        # Sugerencia de precio
        suggest_frame = ctk.CTkFrame(self._editor_scroll, fg_color=theme.CARD2,
                                      corner_radius=8)
        suggest_frame.pack(fill="x", pady=(10, 0))
        suggest_hdr = ctk.CTkFrame(suggest_frame, fg_color="transparent")
        suggest_hdr.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(suggest_hdr, text="Sugerencia de precio",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")
        ctk.CTkButton(suggest_hdr, text="Calcular sugerencia", width=160, height=28,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=11),
                      command=self._suggest_price).pack(side="right")

        self._suggest_lbl = ctk.CTkLabel(suggest_frame,
                                          text="Ingresá un costo y el margen deseado para ver la sugerencia.",
                                          text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11))
        self._suggest_lbl.pack(anchor="w", padx=14, pady=(0, 4))

        suggest_row = ctk.CTkFrame(suggest_frame, fg_color="transparent")
        suggest_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(suggest_row, text="Costo ($):", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._ed_cost = ctk.CTkEntry(suggest_row, width=100,
                                      placeholder_text="0.00", height=30)
        self._ed_cost.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(suggest_row, text="Margen (%):", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._ed_margin = ctk.CTkEntry(suggest_row, width=80,
                                        placeholder_text="30", height=30)
        self._ed_margin.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(suggest_row, text="IVA (%):", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._ed_tax = ctk.CTkEntry(suggest_row, width=60,
                                     placeholder_text="21", height=30)
        self._ed_tax.pack(side="left", padx=(6, 0))

        lbl("Descripción (texto plano)")
        self._ed_desc = ctk.CTkTextbox(self._editor_scroll, height=160,
                                        corner_radius=8, border_width=1,
                                        border_color=theme.SEP,
                                        font=ctk.CTkFont(size=12))
        self._ed_desc.pack(fill="x", pady=(2, 0))

        # Estado
        lbl("Estado de la publicacion")
        st_row = ctk.CTkFrame(self._editor_scroll, fg_color="transparent")
        st_row.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(st_row, text="Pausar publicacion", width=180, height=34,
                      fg_color=theme.BTN_ORANGE, hover_color=theme.BTN_ORANGEH,
                      command=self._pause_listing).pack(side="left", padx=(0, 8))
        ctk.CTkButton(st_row, text="Activar publicacion", width=180, height=34,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._activate_listing).pack(side="left")

        self._ed_status_lbl = ctk.CTkLabel(self._editor_scroll, text="",
                                            font=ctk.CTkFont(size=11))
        self._ed_status_lbl.pack(anchor="w", pady=(8, 0))

        ctk.CTkButton(self._editor_scroll, text="Guardar cambios", height=42,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save_listing).pack(fill="x", pady=(16, 4))

    def _suggest_price(self):
        """Calcula precio sugerido = costo * (1 + margen/100) * (1 + iva/100)."""
        try:
            cost   = float(self._ed_cost.get().replace(",", "."))
            margin = float(self._ed_margin.get().replace(",", ".") or "30")
            tax    = float(self._ed_tax.get().replace(",", ".") or "0")
        except ValueError:
            self._suggest_lbl.configure(
                text="Ingresá valores numéricos válidos.",
                text_color=theme.C_RED)
            return

        price_sin_iva = cost * (1 + margin / 100)
        price_con_iva = price_sin_iva * (1 + tax / 100)

        # Comision MeLi estimada (14% classico)
        comision    = price_con_iva * 0.14
        price_final = price_con_iva + comision

        self._suggest_lbl.configure(
            text=(
                f"  Sin IVA: ${price_sin_iva:,.2f}  |  "
                f"Con IVA ({tax:.0f}%): ${price_con_iva:,.2f}  |  "
                f"+ Comisión MeLi (~14%): ${comision:,.2f}  |  "
                f"  PRECIO SUGERIDO: ${price_final:,.2f}"
            ),
            text_color=theme.C_GREEN
        )
        # Aplicar al campo de precio
        self._ed_price.delete(0, "end")
        self._ed_price.insert(0, f"{price_final:.2f}")

    def _load_editor_item(self):
        ml_item_id = self._editor_item_e.get().strip()
        if not ml_item_id or not self._ml_user_id:
            return
        self._ed_status_lbl.configure(text="Cargando...", text_color=theme.TEXT_DIM)
        def _run():
            try:
                item = ml_api.get_item_full_detail(self._ml_user_id, ml_item_id)
                self.after(0, lambda i=item: self._populate_editor(i))
            except Exception as e:
                self.after(0, lambda err=str(e): self._ed_status_lbl.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))
        threading.Thread(target=_run, daemon=True).start()

    def _populate_editor(self, item: dict):
        self._ed_title.delete(0, "end")
        self._ed_title.insert(0, item.get("title", ""))
        self._ed_price.delete(0, "end")
        self._ed_price.insert(0, str(item.get("price", "")))
        self._ed_qty.delete(0, "end")
        self._ed_qty.insert(0, str(item.get("available_quantity", "")))
        desc = item.get("plain_text") or (
            item.get("description", {}).get("plain_text", "")
            if isinstance(item.get("description"), dict) else "")
        self._ed_desc.delete("1.0", "end")
        self._ed_desc.insert("1.0", desc)
        self._editor_permalink = item.get("permalink", "")
        st = STATUS_LABELS.get(item.get("status", ""), item.get("status", ""))
        self._ed_status_lbl.configure(
            text=f"Estado actual: {st} | ID: {item.get('id')}",
            text_color=theme.TEXT_DIM)

    def _open_in_meli(self):
        if self._editor_permalink:
            webbrowser.open(self._editor_permalink)

    def _save_listing(self):
        ml_item_id = self._editor_item_e.get().strip()
        if not ml_item_id:
            messagebox.showwarning("Sin item", "Cargá una publicación primero.")
            return
        try:
            price = float(self._ed_price.get())
        except Exception:
            messagebox.showerror("Error", "Precio inválido.")
            return
        try:
            qty = int(self._ed_qty.get())
        except Exception:
            qty = None

        title = self._ed_title.get().strip() or None
        desc  = self._ed_desc.get("1.0", "end").strip() or None

        self._ed_status_lbl.configure(text="Guardando...", text_color=theme.TEXT_DIM)
        def _run():
            ok = ml_api.update_listing(
                self._ml_user_id, ml_item_id,
                title=title, price=price,
                available_qty=qty, description=desc)
            self.after(0, lambda: self._ed_status_lbl.configure(
                text="Guardado correctamente." if ok else "Error al guardar.",
                text_color=theme.C_GREEN if ok else theme.C_RED))
            if ok:
                self.after(500, self._load_catalog)
        threading.Thread(target=_run, daemon=True).start()

    def _pause_listing(self):
        ml_item_id = self._editor_item_e.get().strip()
        if not ml_item_id:
            return
        def _run():
            ok = ml_api.pause_listing(self._ml_user_id, ml_item_id)
            self.after(0, lambda: self._ed_status_lbl.configure(
                text="Publicación pausada." if ok else "Error al pausar.",
                text_color=theme.C_ORANGE if ok else theme.C_RED))
            if ok:
                self.after(300, self._load_catalog)
        threading.Thread(target=_run, daemon=True).start()

    def _activate_listing(self):
        ml_item_id = self._editor_item_e.get().strip()
        if not ml_item_id:
            return
        def _run():
            ok = ml_api.activate_listing(self._ml_user_id, ml_item_id)
            self.after(0, lambda: self._ed_status_lbl.configure(
                text="Publicación activada." if ok else "Error al activar.",
                text_color=theme.C_GREEN if ok else theme.C_RED))
            if ok:
                self.after(300, self._load_catalog)
        threading.Thread(target=_run, daemon=True).start()

    # ══════════════════════════════════════════════════════
    #  TAB 7 — CONFIGURACIÓN / OAUTH
    # ══════════════════════════════════════════════════════
    def _build_config_tab(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        ctk.CTkLabel(sc, text="Credenciales de la App MercadoLibre",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 4))

        info_box = ctk.CTkFrame(sc, fg_color=("#dbeafe", "#1e3a5f"), corner_radius=8)
        info_box.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(info_box,
                     text=(
                         "En tu app de MercadoLibre Developers, la Redirect URI debe ser:\n"
                         f"  {ML_REDIRECT_URI}\n"
                         "  (Aplicaciones → tu app → Editar → Redirect URIs)"
                     ),
                     text_color=("#1d4ed8", "#93c5fd"),
                     font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", padx=14, pady=10)

        grid = ctk.CTkFrame(sc, fg_color="transparent")
        grid.pack(fill="x"); grid.columnconfigure(1, weight=1)
        self._cfg_entries: dict = {}
        for i, (lbl, key, ph, secret) in enumerate([
            ("App ID *",          "ml_app_id",        "1122439897772462", False),
            ("Client Secret *",   "ml_client_secret", "ehpreKOTMLZtiYquI3feZRGXkNvzSHZJ",   True),
            ("SLA alerta (hs)",   "ml_sla_warn_hours","12",               False),
        ]):
            ctk.CTkLabel(grid, text=lbl, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 14), pady=8)
            e = ctk.CTkEntry(grid, placeholder_text=ph,
                             show="*" if secret else "", height=34)
            e.grid(row=i, column=1, sticky="ew", pady=8)
            self._cfg_entries[key] = e

        ctk.CTkLabel(grid, text="Redirect URI (fija)", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(0, 14), pady=8)
        ctk.CTkLabel(grid, text=ML_REDIRECT_URI,
                     text_color=theme.C_BLUE,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=3, column=1, sticky="w", pady=8)

        ctk.CTkButton(sc, text="Guardar credenciales", height=38, width=200,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._save_ml_config).pack(anchor="w", pady=(8, 16))

        ctk.CTkFrame(sc, height=1, fg_color=theme.SEP).pack(fill="x", pady=8)
        ctk.CTkLabel(sc, text="Vincular cuenta MercadoLibre",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(sc,
                     text=(
                         "1. Hace clic en 'Vincular cuenta'\n"
                         "2. Se abre el navegador con la página de autorización de ML\n"
                         "3. Iniciá sesión y hacé clic en 'Permitir'\n"
                         "4. ML te redirige a mercadolibre.com.ar — mirá la barra de direcciones\n"
                         "5. Copiá el valor de '?code=TG-xxxxx' y pegalo en 'Vincular manual' abajo"
                     ),
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11), justify="left",
                     wraplength=700).pack(anchor="w", pady=(0, 10))

        btn_row = ctk.CTkFrame(sc, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))
        self._vincular_btn = ctk.CTkButton(
            btn_row, text="Vincular cuenta MercadoLibre",
            width=280, height=40,
            fg_color=C_MELIA, hover_color="#2563eb",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_oauth_flow)
        self._vincular_btn.pack(side="left")

        ctk.CTkButton(btn_row, text="Abrir pagina manual",
                      width=170, height=40,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self._open_oauth_url).pack(side="left", padx=(10, 0))

        self._oauth_status = ctk.CTkLabel(sc, text="",
                                           font=ctk.CTkFont(size=12),
                                           wraplength=700, justify="left")
        self._oauth_status.pack(anchor="w", pady=(4, 4))

        self._oauth_progress = ctk.CTkProgressBar(sc, height=4, corner_radius=2)
        self._oauth_progress.set(0)
        self._oauth_progress.pack_forget()

        ctk.CTkFrame(sc, height=1, fg_color=theme.SEP).pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(sc, text="Vincular manual (pegar codigo de la URL):",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        code_row = ctk.CTkFrame(sc, fg_color="transparent")
        code_row.pack(fill="x", pady=(4, 12))
        self._oauth_code_e = ctk.CTkEntry(code_row, width=320,
                                           placeholder_text="TG-xxxxx...", height=34)
        self._oauth_code_e.pack(side="left")
        ctk.CTkButton(code_row, text="Vincular", width=110, height=34,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._exchange_oauth_code).pack(side="left", padx=8)

        ctk.CTkFrame(sc, height=1, fg_color=theme.SEP).pack(fill="x", pady=8)
        ctk.CTkLabel(sc, text="Cuentas vinculadas",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 6))
        cols    = ("ML User ID", "Nickname", "Vence token", "Activa", "Actualizado")
        widths  = [120, 180, 160, 70, 160]
        anchors = ["center", "w", "center", "center", "center"]
        self._acc_tf, self._acc_tree = W.make_tree(sc, cols, widths, anchors, height=4)
        self._acc_tree.tag_configure("active",   foreground=theme.C_GREEN)
        self._acc_tree.tag_configure("inactive", foreground=theme.TEXT_DIM[1])
        self._acc_tf.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(sc, text="Desactivar cuenta seleccionada",
                      width=240, height=34,
                      fg_color=theme.BTN_RED, hover_color=theme.BTN_REDH,
                      command=self._deactivate_account).pack(anchor="w", pady=(0, 12))

        ctk.CTkFrame(sc, height=1, fg_color=theme.SEP).pack(fill="x", pady=8)
        ctk.CTkLabel(sc, text="Log de sincronizaciones recientes",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(0, 4))
        log_cols    = ("Accion", "User ML", "Entidad", "Estado", "Detalle", "Fecha")
        log_widths  = [140, 100, 120, 70, 200, 130]
        log_anchors = ["center", "center", "center", "center", "w", "center"]
        self._log_tf, self._log_tree = W.make_tree(
            sc, log_cols, log_widths, log_anchors, height=6)
        self._log_tree.tag_configure("error", foreground=theme.C_RED)
        self._log_tree.tag_configure("ok",    foreground=theme.C_GREEN)
        self._log_tf.pack(fill="x", pady=(0, 12))

    # ── Config helpers ─────────────────────────────────────
    def _save_ml_config(self):
        from api import set_setting
        for key, entry in self._cfg_entries.items():
            val = entry.get().strip()
            if val:
                # Guardar en MariaDB (sistema general)
                set_setting(key, val)
                # Guardar también en Neon (donde ml_api lee las credenciales)
                ml_api._set_ml_setting(key, val)
        # Redirect URI fija en ambos stores
        set_setting("ml_redirect_uri", ML_REDIRECT_URI)
        ml_api._set_ml_setting("ml_redirect_uri", ML_REDIRECT_URI)
        messagebox.showinfo("Guardado", "Credenciales ML guardadas.")

    def _start_oauth_flow(self):
        from api import get_setting, set_setting
        app_id = self._cfg_entries.get("ml_app_id")
        app_id = app_id.get().strip() if app_id else ""
        if not app_id:
            app_id = get_setting("ml_app_id", "")
        if not app_id:
            messagebox.showerror("Error", "Ingresa y guarda el App ID primero.")
            return

        set_setting("ml_redirect_uri", ML_REDIRECT_URI)

        def _on_waiting():
            self.after(0, lambda: self._oauth_status.configure(
                text=(
                    "Navegador abierto. Iniciá sesión y hacé clic en 'Permitir'.\n"
                    "ML va a redirigirte a mercadolibre.com.ar — copiá el valor de\n"
                    "'?code=TG-xxxx' de la barra de direcciones y pegalo abajo en 'Vincular manual'."
                ),
                text_color=theme.C_BLUE))

        _oauth_https_flow(app_id, None, None, _on_waiting)

    def _open_oauth_url(self):
        from api import get_setting, set_setting
        set_setting("ml_redirect_uri", ML_REDIRECT_URI)
        app_id = get_setting("ml_app_id", "")
        if not app_id:
            messagebox.showerror("Error", "Guarda el App ID primero.")
            return
        params = _uparse.urlencode({
            "response_type": "code",
            "client_id":     app_id,
            "redirect_uri":  ML_REDIRECT_URI,
        })
        webbrowser.open(f"https://auth.mercadolibre.com.ar/authorization?{params}")
        self._oauth_status.configure(
            text="Navegador abierto. Iniciá sesión, hacé clic en 'Permitir' y copiá el código TG-xxx "
                 "de la barra de direcciones (después de ?code=). Pegalo en 'Vincular manual'.",
            text_color=theme.TEXT_DIM)

    def _exchange_oauth_code(self):
        code = self._oauth_code_e.get().strip()
        if not code:
            self._oauth_status.configure(text="Pega el codigo primero.",
                                          text_color=theme.C_RED)
            return
        self._oauth_status.configure(text="Vinculando...", text_color=theme.TEXT_DIM)
        def _run():
            try:
                resp     = ml_api.exchange_code_for_token(code)
                nickname = resp.get("nickname", str(resp.get("user_id", "")))
                self.after(0, lambda: (
                    self._oauth_status.configure(
                        text=f"Vinculado correctamente: {nickname}",
                        text_color=theme.C_GREEN),
                    self._load_accounts(),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._oauth_status.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))
        threading.Thread(target=_run, daemon=True).start()

    def _load_accounts(self):
        self._acc_tree.delete(*self._acc_tree.get_children())
        accounts       = ml_api.get_all_ml_accounts()
        self._accounts = accounts
        names = []
        for (ml_user_id, nickname, expires_at, active, updated_at) in accounts:
            tag     = "active" if active else "inactive"
            display = nickname or ml_user_id
            self._acc_tree.insert("", "end", iid=ml_user_id, values=(
                ml_user_id, nickname or "-",
                _fmt_dt(str(expires_at)),
                "Si" if active else "No",
                _fmt_dt(str(updated_at)),
            ), tags=(tag,))
            if active:
                names.append(display)
        if names:
            self._account_menu.configure(values=names)
            first_active = next((a for a in accounts if a[3]), None)
            if first_active:
                uid     = first_active[0]
                display = first_active[1] or first_active[0]
                # Siempre actualizar el ml_user_id y el menú para garantizar consistencia
                self._ml_user_id = uid
                self._account_var.set(display)
        else:
            self._account_menu.configure(values=["—"])

    def _load_sync_log(self):
        self._log_tree.delete(*self._log_tree.get_children())
        for (action, ml_uid, entity, status, detail, created_at) in ml_api.get_sync_log(50):
            self._log_tree.insert("", "end", values=(
                action, ml_uid or "-", entity or "-",
                status, (detail or "")[:50],
                _fmt_dt(str(created_at)),
            ), tags=(status,))

    def _deactivate_account(self):
        sel = self._acc_tree.selection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona una cuenta.")
            return
        ml_user_id = sel[0]
        if messagebox.askyesno("Desactivar", f"Desactivar cuenta {ml_user_id}?"):
            ml_api.deactivate_ml_account(ml_user_id)
            self._load_accounts()

    def _on_account_change(self, val: str):
        for (ml_user_id, nickname, *_) in self._accounts:
            if (nickname or ml_user_id) == val:
                self._ml_user_id = ml_user_id
                self._refresh_kpis()
                self._load_catalog()
                self._load_orders()
                break

    def _refresh_treeview_style(self):
        for attr in ("_cat_tree", "_ord_tree", "_rev_tree", "_acc_tree", "_log_tree"):
            t = getattr(self, attr, None)
            if t:
                try:
                    t.configure(style="Cs.Treeview")
                except Exception:
                    pass

    def on_show(self):
        self._load_accounts()
        self._load_sync_log()
        if self._ml_user_id:
            self._refresh_kpis()
            self._load_catalog()
            self._load_orders()
        # Precargar campos de configuración desde Neon (fuente principal de ml_api)
        if hasattr(self, "_cfg_entries"):
            for key in ("ml_app_id", "ml_sla_warn_hours"):
                entry = self._cfg_entries.get(key)
                if entry and not entry.get().strip():
                    val = ml_api._get_ml_setting(key, "")
                    if not val:  # fallback a MariaDB
                        from api import get_setting
                        val = get_setting(key, "")
                    if val:
                        entry.insert(0, val)
            # El secret se carga desde Neon (no se muestra por show="*", pero queda listo)
            # Se pone un placeholder que confirma que ya está guardado si existe en Neon
            secret_entry = self._cfg_entries.get("ml_client_secret")
            if secret_entry and not secret_entry.get().strip():
                existing = ml_api._get_ml_setting("ml_client_secret", "")
                if existing:
                    secret_entry.configure(placeholder_text="[guardado en Neon — reescribir para cambiar]")

    def on_hide(self):
        pass


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: Editor de plantillas de mensajes
# ══════════════════════════════════════════════════════════════

class TemplateEditorDialog(ctk.CTkToplevel):
    """Permite editar, agregar y eliminar plantillas de mensajes."""
    def __init__(self, parent, templates: list, on_save):
        super().__init__(parent)
        self.title("Editar plantillas de mensajes")
        self.geometry("700x560")
        self.resizable(True, True)
        self.grab_set()
        self.focus()
        self._templates = [list(t) for t in templates]  # copia mutable
        self._on_save   = on_save
        self._sel_idx   = -1
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Plantillas de mensajes predeterminados",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 4), padx=20, anchor="w")
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x", padx=20, pady=(0, 12))

        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        split.columnconfigure(0, weight=1)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # Lista de plantillas
        left = ctk.CTkFrame(split, fg_color=theme.CARD, corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(left, text="Plantillas", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=12, pady=(10, 4))
        self._list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._rebuild_list()

        tpl_act = ctk.CTkFrame(left, fg_color="transparent")
        tpl_act.pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkButton(tpl_act, text="+ Nueva", width=80, height=28,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._new_template).pack(side="left", padx=(0, 4))
        ctk.CTkButton(tpl_act, text="Eliminar", width=80, height=28,
                      fg_color=theme.BTN_RED, hover_color=theme.BTN_REDH,
                      command=self._delete_template).pack(side="left")

        # Editor
        right = ctk.CTkFrame(split, fg_color=theme.CARD, corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(right, text="Editar plantilla",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=14, pady=(10, 4))

        ctk.CTkLabel(right, text="Nombre:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14)
        self._tpl_name_e = ctk.CTkEntry(right, height=34)
        self._tpl_name_e.pack(fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(right, text="Texto:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14)
        self._tpl_text_e = ctk.CTkTextbox(right, height=220,
                                           corner_radius=8, border_width=1,
                                           border_color=theme.SEP)
        self._tpl_text_e.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        ctk.CTkButton(right, text="Guardar esta plantilla", height=36,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      command=self._save_current).pack(fill="x", padx=14, pady=(0, 10))

        # Botones finales
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(foot, text="Guardar y cerrar", height=38,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._confirm_save).pack(side="right")
        ctk.CTkButton(foot, text="Cancelar", height=38,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self.destroy).pack(side="right", padx=(0, 8))

    def _rebuild_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        for i, (name, _) in enumerate(self._templates):
            btn = ctk.CTkButton(
                self._list_frame, text=name, anchor="w",
                height=30, corner_radius=6,
                fg_color=C_MELIA if i == self._sel_idx else "transparent",
                hover_color=C_MELIA,
                text_color="#ffffff" if i == self._sel_idx else theme.TEXT,
                font=ctk.CTkFont(size=11),
                command=lambda idx=i: self._select(idx))
            btn.pack(fill="x", pady=1)

    def _select(self, idx: int):
        self._sel_idx = idx
        self._rebuild_list()
        name, text = self._templates[idx]
        self._tpl_name_e.delete(0, "end")
        self._tpl_name_e.insert(0, name)
        self._tpl_text_e.delete("1.0", "end")
        self._tpl_text_e.insert("1.0", text)

    def _save_current(self):
        if self._sel_idx < 0:
            return
        name = self._tpl_name_e.get().strip()
        text = self._tpl_text_e.get("1.0", "end").strip()
        if not name or not text:
            return
        self._templates[self._sel_idx] = [name, text]
        self._rebuild_list()

    def _new_template(self):
        self._templates.append(["Nueva plantilla", "Texto del mensaje..."])
        self._sel_idx = len(self._templates) - 1
        self._rebuild_list()
        self._select(self._sel_idx)

    def _delete_template(self):
        if self._sel_idx < 0 or not self._templates:
            return
        del self._templates[self._sel_idx]
        self._sel_idx = max(0, self._sel_idx - 1)
        self._rebuild_list()
        if self._templates:
            self._select(self._sel_idx)
        else:
            self._tpl_name_e.delete(0, "end")
            self._tpl_text_e.delete("1.0", "end")

    def _confirm_save(self):
        self._on_save([tuple(t) for t in self._templates])
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: Detalle de envío
# ══════════════════════════════════════════════════════════════

class ShippingDialog(ctk.CTkToplevel):
    """Muestra el detalle completo de envío de una orden."""
    def __init__(self, parent, ml_user_id: str, ml_order_id: int):
        super().__init__(parent)
        self.title(f"Detalle de envio — Orden {ml_order_id}")
        self.geometry("520x440")
        self.resizable(False, True)
        self.grab_set(); self.focus()
        self._ml_user_id  = ml_user_id
        self._ml_order_id = ml_order_id

        ctk.CTkLabel(self, text=f"Envio — Orden #{ml_order_id}",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 4))
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=20, pady=(0, 12))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=16)
        self._loading = ctk.CTkLabel(self._scroll, text="Cargando...",
                                      text_color=theme.TEXT_DIM)
        self._loading.pack(pady=30)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(foot, text="Cerrar", height=34,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT,
                      command=self.destroy).pack(side="right")
        ctk.CTkButton(foot, text="Imprimir etiqueta (navegador)", height=34,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      text_color="#000000",
                      command=self._open_label).pack(side="right", padx=(0, 8))

        self._shipping_id = None
        self._token       = ""
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            from db import execute_query
            row = execute_query(
                "SELECT shipping_id FROM ml_orders WHERE ml_order_id=%s",
                (self._ml_order_id,), fetch="one")
            if not row or not row[0]:
                self.after(0, lambda: self._loading.configure(
                    text="Sin información de envio."))
                return
            self._shipping_id = row[0]
            self._token       = ml_api.get_valid_token(self._ml_user_id)
            detail = ml_api.get_shipping_detail(self._ml_user_id, int(row[0]))
            self.after(0, lambda d=detail: self._render(d))
        except Exception as e:
            self.after(0, lambda err=str(e): self._loading.configure(
                text=f"Error: {err}", text_color=theme.C_RED))

    def _render(self, detail: dict):
        self._loading.destroy()
        addr = detail.get("receiver_address", {})
        fields = [
            ("ID Envio",          detail.get("id")),
            ("Estado",            SHIPPING_STATUS_LABELS.get(detail.get("status",""), detail.get("status"))),
            ("Substatus",         detail.get("substatus")),
            ("Modo logística",    detail.get("logistic_type")),
            ("Transportista",     detail.get("shipping_option", {}).get("name")),
            ("Tracking #",        detail.get("tracking_number")),
            ("Fecha estimada",    _fmt_dt(str(
                (detail.get("estimated_delivery_final") or {}).get("date","")))),
            ("Calle",             addr.get("street_name")),
            ("Número",            addr.get("street_number")),
            ("Ciudad",            (addr.get("city") or {}).get("name")),
            ("Provincia",         (addr.get("state") or {}).get("name")),
            ("Código postal",     addr.get("zip_code")),
        ]
        for lbl, val in fields:
            if val:
                r = ctk.CTkFrame(self._scroll, fg_color="transparent")
                r.pack(fill="x", pady=3)
                ctk.CTkLabel(r, text=f"{lbl}:", width=150, anchor="w",
                             text_color=theme.TEXT_DIM,
                             font=ctk.CTkFont(size=11)).pack(side="left")
                ctk.CTkLabel(r, text=str(val), anchor="w",
                             font=ctk.CTkFont(size=12),
                             text_color=theme.TEXT).pack(side="left")

    def _open_label(self):
        if self._shipping_id and self._token:
            url = (
                f"https://api.mercadolibre.com/shipment_labels"
                f"?shipment_ids={self._shipping_id}"
                f"&response_type=pdf"
                f"&access_token={self._token}"
            )
            webbrowser.open(url)
        else:
            messagebox.showwarning("Sin datos", "Esperá a que cargue el detalle.")


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: Notificación AFIP
# ══════════════════════════════════════════════════════════════

class AfipMsgDialog(ctk.CTkToplevel):
    """Envía notificación AFIP por ML."""
    def __init__(self, parent, ml_user_id: str, ml_pack_id: int, cae: str):
        super().__init__(parent)
        self.title("Enviar notificacion AFIP")
        self.geometry("420x300")
        self.resizable(False, False)
        self.grab_set(); self.focus()
        self._ml_user_id = ml_user_id
        self._pack_id    = ml_pack_id

        ctk.CTkLabel(self, text="Notificacion de factura AFIP",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 4))
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=20, pady=(0, 12))
        frm = ctk.CTkFrame(self, fg_color="transparent"); frm.pack(fill="x", padx=24)

        def lbl(t):
            ctk.CTkLabel(frm, text=t, anchor="w", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(6, 0))

        lbl("CAE")
        self._cae_e = ctk.CTkEntry(frm, height=34); self._cae_e.insert(0, cae)
        self._cae_e.pack(fill="x", pady=(2, 0))
        lbl("Vencimiento CAE (AAAA-MM-DD)")
        self._vto_e = ctk.CTkEntry(frm, placeholder_text="2026-01-01", height=34)
        self._vto_e.pack(fill="x", pady=(2, 0))
        lbl("Nro. comprobante")
        self._nro_e = ctk.CTkEntry(frm, placeholder_text="1", width=120, height=34)
        self._nro_e.pack(anchor="w", pady=(2, 0))

        self._st = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self._st.pack(pady=(10, 0))
        ctk.CTkButton(self, text="Enviar al comprador", height=40,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      command=self._send).pack(fill="x", padx=24, pady=(8, 20))

    def _send(self):
        try:
            nro = int(self._nro_e.get())
        except Exception:
            self._st.configure(text="Nro. inválido.", text_color=theme.C_RED)
            return
        self._st.configure(text="Enviando...", text_color=theme.TEXT_DIM)
        def _run():
            ok = ml_api.send_afip_notification(
                self._ml_user_id, self._pack_id,
                self._cae_e.get().strip(),
                self._vto_e.get().strip(), nro)
            self.after(0, lambda: self._st.configure(
                text="Enviado correctamente." if ok else "Error al enviar.",
                text_color=theme.C_GREEN if ok else theme.C_RED))
        threading.Thread(target=_run, daemon=True).start()