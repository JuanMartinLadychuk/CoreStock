"""
dispatch.py – Módulo global de Despacho / Logística — CoreStack Pro v0.9

Unifica en una sola pantalla todos los pedidos pendientes de despacho
de cualquier canal (MercadoLibre, futuro e-commerce, etc.).

Columnas:
  Canal | Orden | Comprador | Productos | Cant. | Total | Estado envío | SLA | Fecha

Acciones rápidas:
  · Ver detalle de envío  (abre ShippingDialog de mercadolibre.py)
  · Marcar despachado     (actualiza estado local)
  · Imprimir etiqueta     (abre URL de ML en navegador)
  · Copiar orden ID       (al portapapeles)
"""

import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import webbrowser

import api
import theme
import widgets as W

# Colores por canal
_CANAL_COLOR = {
    "MercadoLibre": "#3483fa",
    "POS":          theme.C_BLUE,
}
_CANAL_ICON = {
    "MercadoLibre": "🛍",
    "POS":          "🖥",
}

# SLA threshold para resaltar urgencia
_URGENTE_HORAS  = 4
_ADVERTIR_HORAS = 24


class DispatchFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self._app  = app
        self._rows: list = []
        self._sel_row: tuple | None = None
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  UI
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        W.page_header(self, "Despacho / Logística", refresh_cmd=self.on_show)

        # KPI cards
        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=24, pady=(0, 10))
        for i in range(4):
            self._kpi_row.columnconfigure(i, weight=1)
        self._kpi_labels: dict = {}

        for col, (key, label, color) in enumerate([
            ("urgente",   "Urgentes (< 4hs)", theme.C_RED),
            ("hoy",       "Despachar hoy",    theme.C_ORANGE),
            ("pendiente", "Pendientes",        theme.C_BLUE),
            ("total",     "Total en cola",     theme.C_GREEN),
        ]):
            card = ctk.CTkFrame(self._kpi_row, fg_color=theme.CARD,
                                corner_radius=10, border_width=1,
                                border_color=theme.SEP)
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 8, 0), pady=2)
            ctk.CTkFrame(card, width=3, corner_radius=2,
                         fg_color=color).pack(side="left", fill="y", padx=(12, 0), pady=14)
            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(side="left", fill="both", expand=True, padx=12, pady=14)
            val_lbl = ctk.CTkLabel(body, text="—",
                                   font=ctk.CTkFont(size=22, weight="bold"),
                                   text_color=color, anchor="w")
            val_lbl.pack(anchor="w")
            ctk.CTkLabel(body, text=label,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=theme.TEXT, anchor="w").pack(anchor="w")
            self._kpi_labels[key] = val_lbl

        # Filtro de canal
        bar = W.filter_bar(self)
        ctk.CTkLabel(bar, text="Canal:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(14, 4), pady=8)
        self._canal_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(bar, variable=self._canal_var,
                          values=["Todos", "MercadoLibre"],
                          width=160, height=32,
                          command=lambda _: self._render()).pack(side="left")

        self._count_lbl = ctk.CTkLabel(bar, text="",
                                        text_color=theme.TEXT_DIM,
                                        font=ctk.CTkFont(size=11))
        self._count_lbl.pack(side="right", padx=16)

        # Tabla
        cols    = ("Canal", "Orden", "Comprador", "Producto",
                   "Cant.", "Total", "Estado envío", "SLA", "Fecha orden")
        widths  = [105, 95, 130, 200, 55, 100, 115, 130, 130]
        anchors = ["center", "center", "w", "w",
                   "center", "e", "center", "center", "center"]
        self._tf, self._tree = W.make_tree(
            self, cols, widths, anchors, height=16)

        # Tags de urgencia y canal
        self._tree.tag_configure("urgente",   foreground=theme.C_RED)
        self._tree.tag_configure("advertir",  foreground=theme.C_ORANGE)
        self._tree.tag_configure("ok",        foreground=theme.C_GREEN)
        self._tree.tag_configure("ml",        foreground="#3483fa")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        # Barra de acciones
        act = ctk.CTkFrame(self, fg_color="transparent")
        act.pack(fill="x", padx=24, pady=(0, 12))

        self._btn_detail = ctk.CTkButton(
            act, text="Ver detalle envío", width=150, height=34,
            fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
            state="disabled", command=self._view_detail)
        self._btn_detail.pack(side="left", padx=(0, 6))

        self._btn_label = ctk.CTkButton(
            act, text="🖨 Imprimir etiqueta", width=160, height=34,
            fg_color="#3483fa", hover_color="#2563eb",
            state="disabled", command=self._print_label)
        self._btn_label.pack(side="left", padx=(0, 6))

        self._btn_ship = ctk.CTkButton(
            act, text="✅ Marcar despachado", width=170, height=34,
            fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
            state="disabled", command=self._mark_shipped)
        self._btn_ship.pack(side="left", padx=(0, 6))

        self._btn_copy = ctk.CTkButton(
            act, text="Copiar ID orden", width=130, height=34,
            fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
            text_color=theme.TEXT_DIM,
            state="disabled", command=self._copy_id)
        self._btn_copy.pack(side="left")

        self._act_status = ctk.CTkLabel(act, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color=theme.TEXT_DIM)
        self._act_status.pack(side="right")

    # ══════════════════════════════════════════════════════
    #  Datos
    # ══════════════════════════════════════════════════════
    def _load(self):
        """Carga la cola de despacho en background."""
        self._count_lbl.configure(text="Cargando…")
        threading.Thread(target=self._load_bg, daemon=True).start()

    def _load_bg(self):
        try:
            rows = api.get_dispatch_queue()
            self.after(0, lambda r=rows: self._apply_rows(r))
        except Exception as e:
            self.after(0, lambda: self._count_lbl.configure(
                text=f"Error: {e}", text_color=theme.C_RED))

    def _apply_rows(self, rows: list):
        self._rows = rows
        self._refresh_kpis()
        self._render()

    def _refresh_kpis(self):
        now = datetime.now()
        urgente = advertir = total = 0
        for row in self._rows:
            total += 1
            sla = row[8]
            if sla:
                try:
                    sla_dt = datetime.strptime(str(sla)[:16], "%Y-%m-%d %H:%M")
                    h = (sla_dt - now).total_seconds() / 3600
                    if h < _URGENTE_HORAS:
                        urgente += 1
                    elif h < _ADVERTIR_HORAS:
                        advertir += 1
                except Exception:
                    pass
        pendiente = total - urgente - advertir
        for key, val in [
            ("urgente",   urgente),
            ("hoy",       advertir),
            ("pendiente", pendiente),
            ("total",     total),
        ]:
            lbl = self._kpi_labels.get(key)
            if lbl:
                lbl.configure(text=str(val))

    def _render(self):
        self._tree.delete(*self._tree.get_children())
        canal_filter = self._canal_var.get()
        now = datetime.now()
        shown = 0

        for row in self._rows:
            (id_int, canal, id_ext, comprador, prods,
             qty, total, est_envio, sla, fecha) = row

            if canal_filter != "Todos" and canal != canal_filter:
                continue
            shown += 1

            # Tag de urgencia
            tag = "ml" if canal == "MercadoLibre" else "ok"
            sla_txt = "—"
            if sla:
                try:
                    sla_dt  = datetime.strptime(str(sla)[:16], "%Y-%m-%d %H:%M")
                    h       = (sla_dt - now).total_seconds() / 3600
                    sla_txt = str(sla)[:16]
                    if h < _URGENTE_HORAS:
                        tag = "urgente"
                    elif h < _ADVERTIR_HORAS:
                        tag = "advertir"
                except Exception:
                    sla_txt = str(sla)[:16]

            icon = _CANAL_ICON.get(canal, "·")
            self._tree.insert("", "end", iid=f"{canal}_{id_int}", values=(
                f"{icon} {canal}",
                str(id_ext)[-10:] if id_ext else str(id_int)[-10:],
                (comprador or "—")[:20],
                (prods or "—")[:40],
                qty,
                f"${float(total):,.0f}",
                est_envio or "—",
                sla_txt,
                str(fecha)[:10] if fecha else "—",
            ), tags=(tag,))

        self._count_lbl.configure(
            text=f"{shown} pedidos en cola",
            text_color=theme.TEXT_DIM)

    # ══════════════════════════════════════════════════════
    #  Selección y acciones
    # ══════════════════════════════════════════════════════
    def _on_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            self._sel_row = None
            for btn in (self._btn_detail, self._btn_label,
                        self._btn_ship, self._btn_copy):
                btn.configure(state="disabled")
            return

        iid = sel[0]
        self._sel_row = next(
            (r for r in self._rows
             if f"{r[1]}_{r[0]}" == iid), None)

        state = "normal" if self._sel_row else "disabled"
        for btn in (self._btn_detail, self._btn_label,
                    self._btn_ship, self._btn_copy):
            btn.configure(state=state)

    def _view_detail(self):
        if not self._sel_row:
            return
        canal = self._sel_row[1]
        if canal == "MercadoLibre":
            self._open_ml_detail()

    def _open_ml_detail(self):
        """Abre el diálogo de detalle de envío de ml."""
        try:
            from mercadolibre import ShippingDialog
            from ml_api import get_all_ml_accounts
            accounts = get_all_ml_accounts()
            active   = next((a for a in accounts if a[3]), None)
            if not active:
                messagebox.showwarning("Sin cuenta ML", "No hay cuenta ML activa.")
                return
            ml_uid    = str(active[0])
            order_id  = self._sel_row[2]  # id_ext = ml_order_id
            ShippingDialog(self, ml_user_id=ml_uid, ml_order_id=int(order_id))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _print_label(self):
        if not self._sel_row:
            return
        canal    = self._sel_row[1]
        order_id = self._sel_row[2]
        if canal != "MercadoLibre":
            messagebox.showinfo("No disponible",
                                "La impresión de etiquetas solo está disponible para MercadoLibre.")
            return
        self._act_status.configure(text="Obteniendo etiqueta…", text_color=theme.TEXT_DIM)

        def _run():
            try:
                from ml_api import get_all_ml_accounts, get_valid_token
                from db import execute_query
                accounts = get_all_ml_accounts()
                active   = next((a for a in accounts if a[3]), None)
                if not active:
                    self.after(0, lambda: self._act_status.configure(
                        text="Sin cuenta ML activa.", text_color=theme.C_RED))
                    return
                ml_uid    = str(active[0])
                token     = get_valid_token(ml_uid)
                ship_row  = execute_query(
                    "SELECT shipping_id FROM ml_orders WHERE ml_order_id=%s",
                    (order_id,), fetch="one")
                if not ship_row or not ship_row[0]:
                    self.after(0, lambda: self._act_status.configure(
                        text="Sin ID de envío.", text_color=theme.C_RED))
                    return
                label_url = (
                    f"https://api.mercadolibre.com/shipment_labels"
                    f"?shipment_ids={ship_row[0]}&response_type=pdf"
                    f"&access_token={token}")
                webbrowser.open(label_url)
                self.after(0, lambda: self._act_status.configure(
                    text="Etiqueta abierta en el navegador.", text_color=theme.C_GREEN))
            except Exception as e:
                self.after(0, lambda err=str(e): self._act_status.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))

        threading.Thread(target=_run, daemon=True).start()

    def _mark_shipped(self):
        if not self._sel_row:
            return
        canal    = self._sel_row[1]
        order_id = self._sel_row[2]

        if not messagebox.askyesno("Confirmar",
                                   f"Marcar orden {str(order_id)[-10:]} como despachada?"):
            return
        try:
            if canal == "MercadoLibre":
                from db import execute_query
                execute_query(
                    "UPDATE ml_orders SET shipping_status='shipped' "
                    "WHERE ml_order_id=%s", (order_id,))
            # Si en el futuro hay otros canales, se agregan aquí
            self._act_status.configure(
                text="Marcada como despachada.", text_color=theme.C_GREEN)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _copy_id(self):
        if not self._sel_row:
            return
        order_id = str(self._sel_row[2] or self._sel_row[0])
        self.clipboard_clear()
        self.clipboard_append(order_id)
        self.update()
        self._act_status.configure(
            text=f"Copiado: {order_id[-12:]}", text_color=theme.C_GREEN)

    # ══════════════════════════════════════════════════════
    #  Ciclo de vida
    # ══════════════════════════════════════════════════════
    def _refresh_treeview_style(self):
        self._tree.configure(style="Cs.Treeview")

    def on_show(self):
        self._load()
