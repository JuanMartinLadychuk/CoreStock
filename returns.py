"""
returns.py - Modulo de Devoluciones y Notas de Credito.
Registra devoluciones, gestiona el estado del producto devuelto
y su impacto en el rendimiento.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import date
import api, theme
import widgets as W


class ReturnsFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._rows: list = []
        self._build_ui()

    def _build_ui(self):
        can_edit = self.perms.get("registrar_venta", True)
        extra = []
        if can_edit:
            extra = [
                dict(text="Registrar devolucion", width=160, fg_color=theme.BTN_ORANGE,
                     hover_color=theme.BTN_ORANGEH, command=self._add),
            ]
        W.page_header(self, "Devoluciones", extra_btns=extra)

        # KPI row
        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=24, pady=(0, 10))
        for i in range(3):
            self._kpi_row.columnconfigure(i, weight=1)

        # Filtros
        bar = W.filter_bar(self)
        ctk.CTkLabel(bar, text="Mes:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(14, 4), pady=8)
        today = date.today()
        months = [str(m).zfill(2) for m in range(1, 13)]
        self._month_var = ctk.StringVar(value=str(today.month).zfill(2))
        ctk.CTkOptionMenu(bar, variable=self._month_var,
                          values=months, width=70, height=32,
                          command=lambda _: self._load()).pack(side="left")
        ctk.CTkLabel(bar, text="Anio:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 4))
        years = [str(y) for y in range(today.year - 2, today.year + 2)]
        self._year_var = ctk.StringVar(value=str(today.year))
        ctk.CTkOptionMenu(bar, variable=self._year_var,
                          values=years, width=90, height=32,
                          command=lambda _: self._load()).pack(side="left")
        self._total_lbl = ctk.CTkLabel(bar, text="", text_color=theme.TEXT_DIM,
                                        font=ctk.CTkFont(size=11))
        self._total_lbl.pack(side="right", padx=16)

        # Tabla
        cols    = ("ID", "Venta", "Producto", "Cant.", "P.Unit.", "Reintegro",
                   "Estado producto", "Stock repuesto", "Fecha")
        widths  = [50, 65, 220, 55, 100, 110, 130, 110, 110]
        anchors = ["center", "center", "w", "center", "e", "e",
                   "center", "center", "center"]
        self._tf, self._tree = W.make_tree(self, cols, widths, anchors, height=16)
        self._tree.tag_configure("revendible", foreground=theme.C_GREEN)
        self._tree.tag_configure("danado",     foreground=theme.C_ORANGE)
        self._tree.tag_configure("perdida",    foreground=theme.C_RED)
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        ctk.CTkLabel(
            self,
            text="Verde = volvio al stock  |  Naranja = danado, no revendible  |  Rojo = perdida total",
            text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=28, pady=(0, 10))

    def _refresh_treeview_style(self):
        self._tree.configure(style="Cs.Treeview")

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        try:
            month = int(self._month_var.get())
            year  = int(self._year_var.get())
        except ValueError:
            return
        self._rows = api.get_returns(month=month, year=year)
        total_refunds = 0.0
        total_losses  = 0.0
        for row in self._rows:
            (id_r, id_sell, prod_name, qty, unit_price,
             refund, condition, restock, reason, username, rdate) = row
            total_refunds += float(refund)
            if condition in ("danado", "perdida"):
                total_losses += float(refund)
            cond_label = {"revendible": "Revendible",
                          "danado":     "Danado",
                          "perdida":    "Perdida total"}.get(condition, condition)
            self._tree.insert("", "end", iid=str(id_r), values=(
                id_r, id_sell, (prod_name or "")[:40], qty,
                f"${float(unit_price):,.2f}",
                f"${float(refund):,.2f}",
                cond_label,
                "Si" if restock else "No",
                str(rdate)[:10],
            ), tags=(condition,))

        self._total_lbl.configure(
            text=f"{len(self._rows)} devoluciones | "
                 f"Reintegros: ${total_refunds:,.2f} | "
                 f"Perdidas: ${total_losses:,.2f}")
        self._refresh_kpis(month, year, total_refunds, total_losses)

    def _refresh_kpis(self, month, year, refunds, losses):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        revendible_count = sum(1 for r in self._rows if r[6] == "revendible")
        for col, (label, val, color) in enumerate([
            ("Reintegros totales", f"${refunds:,.2f}", theme.C_ORANGE),
            ("Perdidas directas",  f"${losses:,.2f}",  theme.C_RED),
            ("Volvieron al stock", str(revendible_count), theme.C_GREEN),
        ]):
            W.kpi_card(self._kpi_row, "", label, val, "", color, col)

    def _add(self):
        ReturnDialog(self, user=self.user, on_save=self._load)

    def on_show(self):
        self._load()


class ReturnDialog(ctk.CTkToplevel):
    def __init__(self, parent, user: dict, on_save):
        super().__init__(parent)
        self._user    = user
        self._on_save = on_save
        self.title("Registrar devolucion")
        self.geometry("480x560")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Registrar devolucion",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 2))
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=(0, 12))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28)

        def lbl(t):
            ctk.CTkLabel(frm, text=t, anchor="w", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(8, 0))

        lbl("Numero de venta (ID) *")
        sell_row = ctk.CTkFrame(frm, fg_color="transparent")
        sell_row.pack(fill="x", pady=(2, 0))
        self._sell_e = ctk.CTkEntry(sell_row, width=110, placeholder_text="ID venta", height=36)
        self._sell_e.pack(side="left")
        ctk.CTkButton(sell_row, text="Buscar", width=80, height=36,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._search_sell).pack(side="left", padx=8)
        self._sell_info = ctk.CTkLabel(sell_row, text="",
                                        text_color=theme.TEXT_DIM,
                                        font=ctk.CTkFont(size=11))
        self._sell_info.pack(side="left")

        lbl("Producto devuelto *")
        self._prod_var = ctk.StringVar(value="")
        self._prod_menu = ctk.CTkOptionMenu(
            frm, variable=self._prod_var, values=["-- buscar venta primero --"],
            width=320, height=34)
        self._prod_menu.pack(anchor="w", pady=(2, 0))
        self._prod_map: dict = {}  # name -> (idProduct, unit_price)

        lbl("Cantidad devuelta *")
        self._qty_e = ctk.CTkEntry(frm, width=100, placeholder_text="1", height=36)
        self._qty_e.insert(0, "1")
        self._qty_e.pack(anchor="w", pady=(2, 0))

        lbl("Monto a reintegrar al cliente")
        self._refund_e = ctk.CTkEntry(frm, width=160, placeholder_text="0.00", height=36)
        self._refund_e.pack(anchor="w", pady=(2, 0))

        lbl("Estado del producto devuelto *")
        self._cond_var = ctk.StringVar(value="revendible")
        cond_row = ctk.CTkFrame(frm, fg_color="transparent")
        cond_row.pack(anchor="w", pady=(4, 0))
        for label, value, color in [
            ("Revendible (vuelve al stock)", "revendible", theme.C_GREEN),
            ("Danado (no se puede revender)", "danado", theme.C_ORANGE),
            ("Perdida total (descartar)", "perdida", theme.C_RED),
        ]:
            ctk.CTkRadioButton(
                frm, text=label,
                variable=self._cond_var, value=value,
                text_color=color,
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", pady=2)

        lbl("Motivo")
        self._reason = ctk.CTkEntry(frm, placeholder_text="Fallo, cambio de talle, etc.",
                                     height=36)
        self._reason.pack(fill="x", pady=(2, 0))

        self._err = ctk.CTkLabel(self, text="", text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(10, 0))
        ctk.CTkButton(self, text="Confirmar devolucion", height=40,
                      fg_color=theme.BTN_ORANGE, hover_color=theme.BTN_ORANGEH,
                      command=self._save).pack(fill="x", padx=28, pady=(6, 20))

    def _search_sell(self):
        sell_id = self._sell_e.get().strip()
        if not sell_id.isdigit():
            self._err.configure(text="ID de venta invalido.")
            return
        detail = api.get_sell_detail(int(sell_id))
        if not detail:
            self._sell_info.configure(text="Venta no encontrada", text_color=theme.C_RED)
            return
        self._sell_info.configure(
            text=f"{len(detail)} items", text_color=theme.C_GREEN)
        self._err.configure(text="")
        self._prod_map = {}
        prod_names = []
        for prod_name, qty, subtotal in detail:
            unit = round(float(subtotal) / int(qty), 2) if qty else 0
            # Buscar idProduct
            r = api.execute_query(
                "SELECT idProduct FROM products WHERE product=%s LIMIT 1",
                (prod_name,), fetch="one")
            id_prod = r[0] if r else None
            self._prod_map[prod_name] = (id_prod, unit)
            prod_names.append(prod_name)
        if prod_names:
            self._prod_var.set(prod_names[0])
            self._prod_menu.configure(values=prod_names)
            # Prellenar monto
            _, unit = self._prod_map.get(prod_names[0], (None, 0))
            self._refund_e.delete(0, "end")
            self._refund_e.insert(0, f"{unit:.2f}")

    def _save(self):
        sell_id = self._sell_e.get().strip()
        if not sell_id.isdigit():
            self._err.configure(text="Ingresa el ID de la venta."); return
        prod_name = self._prod_var.get()
        if prod_name == "-- buscar venta primero --" or not prod_name:
            self._err.configure(text="Busca la venta primero."); return
        try:
            qty = int(self._qty_e.get()); assert qty > 0
        except Exception:
            self._err.configure(text="Cantidad invalida."); return
        try:
            refund = float(self._refund_e.get()); assert refund >= 0
        except Exception:
            self._err.configure(text="Monto de reintegro invalido."); return

        id_prod, unit_price = self._prod_map.get(prod_name, (None, 0))
        api.add_return(
            id_sell=int(sell_id),
            id_product=id_prod,
            product_name=prod_name,
            quantity=qty,
            unit_price=unit_price,
            refund_amount=refund,
            condition=self._cond_var.get(),
            reason=self._reason.get().strip(),
            id_user=self._user.get("id"),
        )
        messagebox.showinfo(
            "Devolucion registrada",
            f"Producto: {prod_name}\n"
            f"Condicion: {self._cond_var.get()}\n"
            + ("Stock repuesto automaticamente." if self._cond_var.get() == "revendible" else
               "Perdida registrada en el rendimiento.")
        )
        self._on_save()
        self.destroy()
