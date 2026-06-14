"""pos.py – Terminal POS CoreStack Pro.

 · UI construida UNA SOLA VEZ en __init__ — sin flash al volver a entrar
 · on_show() solo recarga la sesión activa y enfoca el campo de scan
 · Hotkeys F1/F2/F4/Esc registrados en on_show, liberados en on_hide
 · Sugerencias de autocomplete con debounce (100ms)
 · Cálculo de vuelto e impuestos en tiempo real
 · Soporte MercadoPago Point (polling async)
 · Apertura / cierre de caja con resumen
 · AFIP WSFEv1 si está habilitado"""

import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime
import threading
import time

import api
import theme

# ── Beep ───────────────────────────────────────────────────────
try:
    import winsound
    def _beep_ok():    winsound.Beep(1200, 80)
    def _beep_error(): winsound.Beep(400, 300)
    def _beep_cash():  winsound.Beep(800, 100); time.sleep(0.05); winsound.Beep(1000, 100)
except ImportError:
    def _beep_ok():    print("\a", end="", flush=True)
    def _beep_error(): print("\a\a", end="", flush=True)
    def _beep_cash():  print("\a", end="", flush=True)

try:
    import urllib.request
    import json as _json
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

PAYMENT_METHODS = [
    ("Efectivo",       "Efectivo"),
    ("Débito",         "Débito"),
    ("Crédito",        "Crédito"),
    ("MP / Billetera", "Billetera Virtual"),
    ("Transferencia",  "Transferencia"),
    ("MP Point",      "MP_Point"),
]


# ══════════════════════════════════════════════════════════════
#  Frame principal
# ══════════════════════════════════════════════════════════════
class POSFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user    = user
        self.perms   = user.get("permissions", {})
        self._cart: list[dict]   = []
        self._active_session: dict | None = None
        self._hotkey_ids: list[str]       = []
        self._tax_rows: list[ctk.CTkFrame] = []
        self._sug_btns: list              = []
        self._debounce_id: str | None     = None
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  UI  (construida una sola vez)
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_header()
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x", padx=20)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=10)
        body.columnconfigure(0, weight=3, minsize=520)
        body.columnconfigure(1, weight=2, minsize=300)
        body.rowconfigure(0, weight=1)
        self._build_left(body)
        self._build_right(body)

    # ── Header ─────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 6))

        ctk.CTkLabel(hdr, text="Terminal POS",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        # Botones de caja — lado derecho
        ctk.CTkButton(hdr, text="Historial", width=100, height=28,
                      fg_color="transparent", hover_color=theme.CARD2,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11),
                      command=self._show_history).pack(side="right")

        self._close_btn = ctk.CTkButton(
            hdr, text="Cerrar caja", width=120, height=28,
            fg_color=theme.BTN_PURPLE, hover_color=theme.BTN_PURPLEH,
            font=ctk.CTkFont(size=11), state="disabled",
            command=self._close_session)
        self._close_btn.pack(side="right", padx=(0, 6))

        self._open_btn = ctk.CTkButton(
            hdr, text="Abrir caja", width=120, height=28,
            fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
            font=ctk.CTkFont(size=11),
            command=self._open_session)
        self._open_btn.pack(side="right", padx=(0, 6))

        self._session_lbl = ctk.CTkLabel(
            hdr, text="Sin sesion de caja",
            font=ctk.CTkFont(size=11),
            text_color=theme.C_ORANGE)
        self._session_lbl.pack(side="left", padx=14)

    # ── Panel izquierdo ─────────────────────────────────────
    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        # ── Buscador / scanner ─────────────────────────────
        scan_card = ctk.CTkFrame(left, fg_color=theme.CARD, corner_radius=14)
        scan_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        si = ctk.CTkFrame(scan_card, fg_color="transparent")
        si.pack(fill="x", padx=16, pady=(14, 10))

        ctk.CTkLabel(si, text="Escanear o buscar producto",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(0, 8))

        scan_row = ctk.CTkFrame(si, fg_color="transparent")
        scan_row.pack(fill="x")
        scan_row.columnconfigure(0, weight=1)

        self._scan_e = ctk.CTkEntry(
            scan_row, height=44,
            placeholder_text="Apuntá el lector o escribí nombre / código EAN",
            font=ctk.CTkFont(size=13),
            border_color=theme.SEP)
        self._scan_e.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._scan_e.bind("<Return>",     self._on_scan)
        self._scan_e.bind("<KeyRelease>", self._on_scan_type)

        self._qty_e = ctk.CTkEntry(
            scan_row, width=58, height=44,
            placeholder_text="×1", justify="center",
            font=ctk.CTkFont(size=15))
        self._qty_e.grid(row=0, column=1, padx=(0, 6))
        self._qty_e.insert(0, "1")
        self._qty_e.bind("<Return>", self._on_scan)

        ctk.CTkButton(scan_row, text="＋", width=44, height=44,
                      corner_radius=10,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_H,
                      font=ctk.CTkFont(size=18),
                      command=self._on_scan).grid(row=0, column=2)

        # Feedback de scan
        self._scan_fb = ctk.CTkLabel(
            si, text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.C_GREEN)
        self._scan_fb.pack(anchor="w", pady=(6, 0))

        # Panel de sugerencias (oculto por defecto)
        self._sug_frame = ctk.CTkFrame(
            si, fg_color=theme.CARD2, corner_radius=8)

        # ── Header del carrito ─────────────────────────────
        ch_row = ctk.CTkFrame(left, fg_color="transparent")
        ch_row.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(ch_row, text="Carrito",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        ctk.CTkButton(ch_row, text="Vaciar", width=80, height=26,
                      corner_radius=6,
                      fg_color="transparent",
                      hover_color=("#ffe5e5", "#3a1010"),
                      text_color=("#c62828", "#ef5350"),
                      font=ctk.CTkFont(size=11),
                      command=self._cancel_cart).pack(side="right")

        ctk.CTkButton(ch_row, text="Quitar", width=80, height=26,
                      corner_radius=6,
                      fg_color="transparent", hover_color=theme.CARD2,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11),
                      command=self._remove_selected).pack(side="right", padx=(0, 4))

        # ── Tabla del carrito ──────────────────────────────
        cart_f = ctk.CTkFrame(left, fg_color=theme.CARD, corner_radius=14)
        cart_f.grid(row=2, column=0, sticky="nsew")

        cols = ("Producto", "Cant.", "P. Unit.", "Subtotal")
        self._cart_tree = ttk.Treeview(
            cart_f, columns=cols, show="headings",
            style="Cs.Treeview", selectmode="browse", height=14)

        for col, w, anc in zip(
            cols,
            [310, 56, 110, 120],
            ["w", "center", "e", "e"]
        ):
            self._cart_tree.heading(col, text=col)
            self._cart_tree.column(col, width=w, anchor=anc)

        sc = ttk.Scrollbar(cart_f, orient="vertical",
                           command=self._cart_tree.yview)
        self._cart_tree.configure(yscrollcommand=sc.set)
        self._cart_tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        sc.pack(side="right", fill="y", pady=8)
        self._cart_tree.bind("<Double-1>", self._edit_item)

        # Hotkey hint
        ctk.CTkLabel(left,
                     text="F1 Cobrar F2 Cancelar F4 Abrir caja Esc Limpiar búsqueda",
                     font=ctk.CTkFont(size=9),
                     text_color=theme.TEXT_DIM).grid(row=3, column=0,
                                                      sticky="w", pady=(4, 0))

    # ── Panel derecho ───────────────────────────────────────
    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # ── Totalizador ────────────────────────────────────
        tot = ctk.CTkFrame(right, fg_color=theme.CARD, corner_radius=14)
        tot.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(tot, text="Resumen",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(pady=(12, 6), padx=16, anchor="w")

        # Contenedor de filas de totales
        self._tot_frame = ctk.CTkFrame(tot, fg_color="transparent")
        self._tot_frame.pack(fill="x", padx=16, pady=(0, 4))

        self._lbl_subtotal = self._tot_row("Subtotal:", "$0.00", theme.TEXT)
        self._lbl_discount = self._tot_row("Descuento:", "—", theme.C_BLUE)
        ctk.CTkFrame(self._tot_frame, height=1,
                     fg_color=theme.SEP).pack(fill="x", pady=5)
        self._lbl_total = self._tot_row(
            "TOTAL:", "$0.00", theme.C_GREEN, big=True)

        # Descuento
        disc_row = ctk.CTkFrame(tot, fg_color="transparent")
        disc_row.pack(fill="x", padx=16, pady=(2, 14))
        ctk.CTkLabel(disc_row, text="Descuento %:",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._disc_e = ctk.CTkEntry(
            disc_row, width=70, placeholder_text="0",
            height=28, justify="center")
        self._disc_e.pack(side="left", padx=8)
        self._disc_e.bind("<KeyRelease>", lambda _: self._refresh_totals())

        # ── Métodos de pago ────────────────────────────────
        pay = ctk.CTkFrame(right, fg_color=theme.CARD, corner_radius=14)
        pay.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        ctk.CTkLabel(pay, text="Metodo de pago",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(pady=(12, 8), padx=16, anchor="w")

        self._pay_var = ctk.StringVar(value="Efectivo")
        grid_f = ctk.CTkFrame(pay, fg_color="transparent")
        grid_f.pack(fill="x", padx=16, pady=(0, 4))
        for i, (label, value) in enumerate(PAYMENT_METHODS):
            ctk.CTkRadioButton(
                grid_f, text=label,
                variable=self._pay_var, value=value,
                command=self._on_pay_change,
                font=ctk.CTkFont(size=11)
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=3)

        # Panel efectivo (visible por defecto)
        self._cash_panel = ctk.CTkFrame(pay, fg_color="transparent")
        cash_row = ctk.CTkFrame(self._cash_panel, fg_color="transparent")
        cash_row.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkLabel(cash_row, text="Recibido: $",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self._cash_e = ctk.CTkEntry(
            cash_row, width=110, placeholder_text="0.00", height=30)
        self._cash_e.pack(side="left", padx=4)
        self._cash_e.bind("<KeyRelease>", self._calc_change)
        self._change_lbl = ctk.CTkLabel(
            cash_row, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.C_GREEN)
        self._change_lbl.pack(side="left", padx=10)
        self._cash_panel.pack(fill="x")

        # Panel MP Point (oculto por defecto)
        self._mp_panel = ctk.CTkFrame(pay, fg_color="transparent")
        self._mp_status = ctk.CTkLabel(
            self._mp_panel, text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.C_ORANGE)
        self._mp_status.pack(padx=16, pady=(4, 2))
        ctk.CTkButton(self._mp_panel, text="Ver dispositivos",
                      height=24, fg_color="transparent",
                      hover_color=theme.CARD2,
                      text_color=theme.C_BLUE, font=ctk.CTkFont(size=10),
                      command=self._mp_list_devices_ui).pack(padx=16, pady=(0, 10))

        # ── Botones de acción ──────────────────────────────
        ctk.CTkButton(
            right, text="COBRAR [F1]",
            height=52, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
            command=self._checkout
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            right, text="Cancelar venta [F2]",
            height=30, corner_radius=8,
            fg_color="transparent",
            hover_color=("#ffe5e5", "#3a1010"),
            text_color=("#c62828", "#ef5350"),
            font=ctk.CTkFont(size=11),
            command=self._cancel_cart
        ).grid(row=3, column=0, sticky="ew")

    def _tot_row(self, label: str, value: str,
                 color, big: bool = False) -> ctk.CTkLabel:
        row = ctk.CTkFrame(self._tot_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label,
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11 if not big else 14)).pack(side="left")
        lbl = ctk.CTkLabel(row, text=value,
                           text_color=color,
                           font=ctk.CTkFont(
                               size=14 if not big else 20,
                               weight="bold" if big else "normal"))
        lbl.pack(side="right")
        return lbl

    # ══════════════════════════════════════════════════════
    #  Hotkeys
    # ══════════════════════════════════════════════════════
    def _register_hotkeys(self):
        root = self.winfo_toplevel()
        for seq, cmd in [
            ("<F1>",     lambda e: self._checkout()),
            ("<F2>",     lambda e: self._cancel_cart()),
            ("<F4>",     lambda e: self._open_session()),
            ("<Escape>", lambda e: self._clear_scan()),
        ]:
            root.bind(seq, cmd, "+")
            self._hotkey_ids.append(seq)

    def _unregister_hotkeys(self):
        try:
            root = self.winfo_toplevel()
            for seq in self._hotkey_ids:
                root.unbind(seq)
        except Exception:
            pass
        self._hotkey_ids.clear()

    # ══════════════════════════════════════════════════════
    #  Scanner / autocomplete
    # ══════════════════════════════════════════════════════
    def _on_scan(self, _=None):
        raw = self._scan_e.get().strip()
        self._hide_sug()
        if not raw:
            return

        # Formato: "3 * Coca" o "3x Coca"
        qty, code = 1, raw
        for sep in ("*", "x", "X"):
            if sep in raw:
                parts = raw.split(sep, 1)
                try:
                    qty  = int(parts[0].strip())
                    code = parts[1].strip()
                    break
                except ValueError:
                    pass

        try:
            qty = max(1, int(self._qty_e.get()))
        except ValueError:
            pass

        prod = api.search_product_by_barcode(code) or api.search_product_by_name(code)
        if prod:
            self._add_to_cart(prod, qty)
            self._scan_e.delete(0, "end")
            self._qty_e.delete(0, "end")
            self._qty_e.insert(0, "1")
            self._scan_e.focus()
            if api.get_setting("pos_beep_enabled", "1") == "1":
                threading.Thread(target=_beep_ok, daemon=True).start()
        else:
            self._scan_fb.configure(
                text=f"'{code[:30]}' no encontrado",
                text_color=theme.C_RED)
            self._scan_e.select_range(0, "end")
            if api.get_setting("pos_beep_enabled", "1") == "1":
                threading.Thread(target=_beep_error, daemon=True).start()
            self.after(2800, lambda: self._scan_fb.configure(text=""))

    def _on_scan_type(self, _=None):
        """Autocomplete con debounce de 120 ms para no spamear la DB."""
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        txt = self._scan_e.get().strip()
        if len(txt) < 2 or txt.isdigit():
            self._hide_sug()
            return
        self._debounce_id = self.after(120, lambda: self._fetch_suggestions(txt))

    def _fetch_suggestions(self, txt: str):
        try:
            prods = api.get_active_products(search=txt)[:7]
            self._show_sug(prods)
        except Exception:
            pass

    def _show_sug(self, products: list):
        self._hide_sug()
        if not products:
            return
        self._sug_frame.pack(fill="x", pady=(4, 0))
        for (id_, name, cat, cost, price, stock) in products:
            stock_color = theme.C_RED if stock <= 3 else (
                          theme.C_ORANGE if stock <= 10 else theme.C_GREEN)
            btn = ctk.CTkButton(
                self._sug_frame,
                text=f"{name:<40} ${float(price):>10,.2f} · stock: {stock}",
                anchor="w", height=30, corner_radius=0,
                fg_color="transparent", hover_color=theme.ACCENT,
                text_color=theme.TEXT, font=ctk.CTkFont(size=11),
                command=lambda p=(id_, name, cat, cost, price, stock):
                    self._sel_sug(p))
            btn.pack(fill="x")
            self._sug_btns.append(btn)

    def _hide_sug(self):
        self._sug_frame.pack_forget()
        for b in self._sug_btns:
            try:
                b.destroy()
            except Exception:
                pass
        self._sug_btns.clear()

    def _sel_sug(self, prod: tuple):
        self._hide_sug()
        try:
            qty = max(1, int(self._qty_e.get()))
        except ValueError:
            qty = 1
        self._add_to_cart(prod, qty)
        self._scan_e.delete(0, "end")
        self._qty_e.delete(0, "end")
        self._qty_e.insert(0, "1")
        self._scan_e.focus()

    def _clear_scan(self):
        self._scan_e.delete(0, "end")
        self._hide_sug()
        self._scan_fb.configure(text="")
        self._scan_e.focus()

    # ══════════════════════════════════════════════════════
    #  Carrito
    # ══════════════════════════════════════════════════════
    def _add_to_cart(self, prod: tuple, qty: int):
        id_, name, cat, cost, price, stock = prod
        price = float(price)

        # Si ya existe en el carrito, actualizar cantidad
        for item in self._cart:
            if item["id"] == id_:
                new_qty = item["qty"] + qty
                if new_qty > stock:
                    self._scan_fb.configure(
                        text=f"Stock insuficiente (disponible: {stock})",
                        text_color=theme.C_ORANGE)
                    self.after(2000, lambda: self._scan_fb.configure(text=""))
                    return
                item["qty"]   = new_qty
                item["total"] = round(price * new_qty, 2)
                self._scan_fb.configure(
                    text=f"{name[:35]} → ×{new_qty}",
                    text_color=theme.C_GREEN)
                self._render_cart()
                return

        # Item nuevo
        if qty > stock:
            self._scan_fb.configure(
                text=f"Stock insuficiente (disponible: {stock})",
                text_color=theme.C_ORANGE)
            self.after(2000, lambda: self._scan_fb.configure(text=""))
            return

        self._cart.append({
            "id": id_, "name": name,
            "qty": qty, "unit_price": price,
            "total": round(price * qty, 2),
            "stock": stock,
        })
        self._scan_fb.configure(
            text=f"{name[:35]} ×{qty} agregado",
            text_color=theme.C_GREEN)
        self._render_cart()

    def _render_cart(self):
        self._cart_tree.delete(*self._cart_tree.get_children())
        for item in self._cart:
            self._cart_tree.insert("", "end", values=(
                item["name"],
                item["qty"],
                f"${item['unit_price']:,.2f}",
                f"${item['total']:,.2f}",
            ))
        self._refresh_totals()

    def _remove_selected(self):
        sel = self._cart_tree.selection()
        if not sel:
            return
        idx = self._cart_tree.index(sel[0])
        if 0 <= idx < len(self._cart):
            self._cart.pop(idx)
            self._render_cart()

    def _edit_item(self, _=None):
        sel = self._cart_tree.selection()
        if not sel:
            return
        idx = self._cart_tree.index(sel[0])
        if 0 <= idx < len(self._cart):
            CartItemEditDialog(self, self._cart[idx],
                               on_save=self._render_cart)

    def _cancel_cart(self):
        if self._cart:
            if not messagebox.askyesno("Cancelar venta",
                                       "¿Cancelar la venta actual?"):
                return
        self._cart.clear()
        self._render_cart()
        self._scan_e.delete(0, "end")
        self._scan_fb.configure(text="")
        self._scan_e.focus()

    # ══════════════════════════════════════════════════════
    #  Totales e impuestos
    # ══════════════════════════════════════════════════════
    def _refresh_totals(self):
        raw = sum(i["total"] for i in self._cart)
        try:
            dp = max(0.0, min(100.0, float(self._disc_e.get())))
        except ValueError:
            dp = 0.0

        disc = round(raw * dp / 100, 2)
        sub  = round(raw - disc, 2)

        net, bd = api.calculate_tax_breakdown_multi(sub) if sub else (0.0, [])

        self._lbl_subtotal.configure(text=f"${raw:,.2f}")
        self._lbl_discount.configure(
            text=f"−${disc:,.2f}" if disc > 0 else "—")
        self._lbl_total.configure(text=f"${sub:,.2f}")

        # Limpiar filas de impuestos anteriores
        for r in self._tax_rows:
            try:
                r.destroy()
            except Exception:
                pass
        self._tax_rows.clear()

        # Insertar filas de impuestos debajo del subtotal
        for t in bd:
            row = ctk.CTkFrame(self._tot_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row,
                         text=f"{t['name']} {t['percent']:.0f}%:",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=10)).pack(side="left")
            ctk.CTkLabel(row,
                         text=f"${t['amount']:,.2f}",
                         text_color=theme.C_ORANGE,
                         font=ctk.CTkFont(size=10)).pack(side="right")
            self._tax_rows.append(row)

        self._calc_change()

    def _calc_change(self, _=None):
        if self._pay_var.get() != "Efectivo":
            self._change_lbl.configure(text="")
            return
        try:
            recv = float(self._cash_e.get())
            raw  = sum(i["total"] for i in self._cart)
            try:
                dp = max(0.0, min(100.0, float(self._disc_e.get())))
            except ValueError:
                dp = 0.0
            total  = round(raw * (1 - dp / 100), 2)
            change = round(recv - total, 2)
            self._change_lbl.configure(
                text=f"Vuelto: ${change:,.2f}",
                text_color=theme.C_GREEN if change >= 0 else theme.C_RED)
        except ValueError:
            self._change_lbl.configure(text="")

    def _on_pay_change(self):
        method = self._pay_var.get()
        self._cash_panel.pack_forget()
        self._mp_panel.pack_forget()
        if method == "Efectivo":
            self._cash_panel.pack(fill="x")
        elif method == "MP_Point":
            self._mp_panel.pack(fill="x")
            self._mp_status.configure(
                text="Se enviará al dispositivo Point.",
                text_color=theme.C_ORANGE)

    # ══════════════════════════════════════════════════════
    #  Cobrar
    # ══════════════════════════════════════════════════════
    def _checkout(self):
        if not self._cart:
            messagebox.showwarning("Carrito vacío",
                                   "Agregá al menos un producto.")
            self._scan_e.focus()
            return

        session_required = api.get_setting("cash_session_mode", "1") == "1"
        if session_required and not self._active_session:
            if not messagebox.askyesno("Sin sesión de caja",
                                       "No hay caja abierta.\n¿Continuar igual?"):
                return

        method = self._pay_var.get()
        try:
            dp = max(0.0, min(100.0, float(self._disc_e.get())))
        except ValueError:
            dp = 0.0

        raw   = sum(i["total"] for i in self._cart)
        disc  = round(raw * dp / 100, 2)
        total = round(raw - disc, 2)

        if method == "MP_Point":
            self._checkout_mp(total, disc)
        else:
            self._finalize(method, total, disc)

    def _finalize(self, method: str, total: float, discount: float):
        try:
            raw   = sum(i["total"] for i in self._cart)
            ratio = discount / raw if raw > 0 else 0.0
            last_id = None

            for item in self._cart:
                item_disc   = round(item["total"] * ratio, 2)
                item_net    = round(item["total"] - item_disc, 2)
                last_id = api.add_sell_v2(
                    payment_type=method,
                    quantity=item["qty"],
                    total_amount=item_net,
                    product_name=item["name"],
                    discount=item_disc)

            if api.get_setting("pos_beep_enabled", "1") == "1":
                threading.Thread(target=_beep_cash, daemon=True).start()

            afip_r = {"ok": False, "cae": "", "cae_vto": "", "nro": 0, "error": ""}
            if api.afip_esta_habilitado() and last_id:
                net, bd = api.calculate_tax_breakdown_multi(total)
                afip_r  = api.autorizar_venta_afip(
                    id_sell=last_id, total=total,
                    neto=net,
                    iva=sum(t["amount"] for t in bd))

            # Mostrar ticket
            ReceiptDialog(self,
                          cart=self._cart[:],
                          method=method,
                          total=total,
                          discount=discount,
                          afip_result=afip_r)

            # Limpiar
            self._cart.clear()
            self._render_cart()
            self._disc_e.delete(0, "end")
            self._cash_e.delete(0, "end")
            self._change_lbl.configure(text="")
            self._scan_e.focus()

        except Exception as e:
            messagebox.showerror("Error al registrar venta", str(e))

    # ══════════════════════════════════════════════════════
    #  MercadoPago Point
    # ══════════════════════════════════════════════════════
    def _checkout_mp(self, amount: float, discount: float):
        token  = api.get_setting("mp_access_token", "")
        dev_id = api.get_setting("mp_device_id", "")
        if not token or not dev_id:
            messagebox.showwarning(
                "MP no configurado",
                "Configurá el Access Token y el Device ID\nen Configuración → POS / Pagos.")
            return
        self._mp_status.configure(text="⏳ Enviando al dispositivo…",
                                   text_color=theme.C_ORANGE)
        self.update()
        threading.Thread(
            target=self._mp_request,
            args=(token, dev_id, amount, discount),
            daemon=True).start()

    def _mp_request(self, token, device_id, amount, discount):
        try:
            if not _HAS_URLLIB:
                raise RuntimeError("urllib no disponible")
            url = (f"https://api.mercadopago.com/point/integration-api"
                   f"/devices/{device_id}/payment-intents")
            payload = _json.dumps({
                "amount": int(round(amount * 100)),
                "description": "Venta CoreStack",
                "payment": {
                    "installments": 1,
                    "type": "credit_card",
                    "installments_cost": "seller",
                },
            }).encode()
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = _json.loads(r.read())
            intent_id = data.get("id", "")
            if not intent_id:
                raise RuntimeError(f"Sin ID en respuesta: {data}")
            id_intent = api.create_mp_intent(None, amount, device_id)
            api.update_mp_intent(id_intent, "pending", intent_id)
            self.after(0, lambda: self._mp_poll(
                token, device_id, intent_id, id_intent, amount, discount))
        except Exception as e:
            self.after(0, lambda err=str(e): self._mp_error(err))

    def _mp_poll(self, token, device_id, intent_id,
                 id_intent, amount, discount, attempts=0):
        if attempts > 30:
            self._mp_error("Tiempo de espera agotado (60 s).")
            return
        self._mp_status.configure(
            text=f"⏳ Esperando pago en dispositivo… ({attempts * 2} s)",
            text_color=theme.C_ORANGE)

        def _do():
            try:
                url = (f"https://api.mercadopago.com/point/integration-api"
                       f"/devices/{device_id}/payment-intents/{intent_id}")
                req = urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    st = _json.loads(r.read()).get("state", "pending").lower()
                self.after(0, lambda s=st: self._mp_handle(
                    s, id_intent, amount, discount,
                    token, device_id, intent_id, attempts))
            except Exception as e:
                self.after(0, lambda: self._mp_error(str(e)))

        self.after(2000, lambda: threading.Thread(target=_do, daemon=True).start())

    def _mp_handle(self, status, id_intent, amount, discount,
                   token, device_id, intent_id, attempts):
        if status in ("processed", "approved", "finished"):
            api.update_mp_intent(id_intent, "approved", intent_id)
            self._mp_status.configure(
                text="Pago aprobado.", text_color=theme.C_GREEN)
            self._finalize("MP_Point", amount, discount)
        elif status in ("canceled", "cancelled", "rejected", "error", "abandoned"):
            api.update_mp_intent(id_intent, status, intent_id)
            self._mp_error(f"El pago fue {status} por el dispositivo.")
        else:
            self._mp_poll(token, device_id, intent_id,
                          id_intent, amount, discount, attempts + 1)

    def _mp_error(self, msg: str):
        self._mp_status.configure(text=f"{msg}", text_color=theme.C_RED)
        messagebox.showerror("Error MercadoPago Point", msg)

    def _mp_list_devices_ui(self):
        token = api.get_setting("mp_access_token", "")
        if not token:
            messagebox.showwarning(
                "Sin token",
                "Configurá el Access Token en Configuración → POS.")
            return
        self._mp_status.configure(text="⏳ Consultando dispositivos…",
                                   text_color=theme.C_ORANGE)
        self.update()

        def _go():
            try:
                url = "https://api.mercadopago.com/point/integration-api/devices"
                req = urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    devices = _json.loads(r.read()).get("devices", [])
            except Exception:
                devices = []
            self.after(0, lambda d=devices: MPDevicesDialog(self, d))

        threading.Thread(target=_go, daemon=True).start()

    # ══════════════════════════════════════════════════════
    #  Sesión de caja
    # ══════════════════════════════════════════════════════
    def _open_session(self):
        if self._active_session:
            messagebox.showinfo("Sesión activa",
                                "Ya hay una caja abierta.")
            return
        CashSessionOpenDialog(self,
                              id_user=self.user["id"],
                              on_open=self._on_opened)

    def _on_opened(self, sess: dict):
        self._active_session = sess
        self._update_session_ui()
        self._scan_e.focus()

    def _close_session(self):
        if not self._active_session:
            return
        CashSessionCloseDialog(self,
                               session=self._active_session,
                               id_user=self.user["id"],
                               on_close=self._on_closed)

    def _on_closed(self):
        self._active_session = None
        self._update_session_ui()

    def _update_session_ui(self):
        if self._active_session:
            opened = str(self._active_session.get("opened_at", ""))[:16]
            amt    = float(self._active_session.get("opening_amount", 0))
            self._session_lbl.configure(
                text=f"Caja abierta | ${amt:,.0f} | desde {opened}",
                text_color=theme.C_GREEN)
            self._open_btn.configure(state="disabled")
            self._close_btn.configure(state="normal")
        else:
            self._session_lbl.configure(
                text="Sin sesion de caja",
                text_color=theme.C_ORANGE)
            self._open_btn.configure(state="normal")
            self._close_btn.configure(state="disabled")

    def _show_history(self):
        CashHistoryDialog(self, id_user=self.user["id"])

    # ══════════════════════════════════════════════════════
    #  Hooks del ciclo de vida
    # ══════════════════════════════════════════════════════
    def _refresh_treeview_style(self):
        self._cart_tree.configure(style="Cs.Treeview")

    def on_show(self):
        sess = api.get_active_cash_session(self.user["id"])
        self._active_session = sess
        self._update_session_ui()
        self._register_hotkeys()
        self._scan_e.focus()

    def on_hide(self):
        self._unregister_hotkeys()


# ══════════════════════════════════════════════════════════════
#  Diálogo: editar ítem del carrito
# ══════════════════════════════════════════════════════════════
class CartItemEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, item: dict, on_save):
        super().__init__(parent)
        self._item    = item
        self._on_save = on_save
        self.title(f"Editar: {item['name'][:30]}")
        self.geometry("330x200")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text=item["name"],
                     font=ctk.CTkFont(size=14, weight="bold"),
                     wraplength=290).pack(pady=(20, 2), padx=20)
        ctk.CTkLabel(self, text=f"Stock disponible: {item['stock']}",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack()

        r = ctk.CTkFrame(self, fg_color="transparent")
        r.pack(fill="x", padx=28, pady=12)
        ctk.CTkLabel(r, text="Cantidad:").pack(side="left")
        self._q = ctk.CTkEntry(r, width=80, justify="center",
                                font=ctk.CTkFont(size=15))
        self._q.insert(0, str(item["qty"]))
        self._q.pack(side="left", padx=10)
        self._q.bind("<Return>", lambda _: self._save())

        self._err = ctk.CTkLabel(self, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack()

        ctk.CTkButton(self, text="Aplicar cambio", height=38,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._save).pack(fill="x", padx=28, pady=(4, 16))

    def _save(self):
        try:
            qty = int(self._q.get())
            assert 1 <= qty <= self._item["stock"]
        except (ValueError, AssertionError):
            self._err.configure(
                text=f"Cantidad entre 1 y {self._item['stock']}.")
            return
        self._item["qty"]   = qty
        self._item["total"] = round(self._item["unit_price"] * qty, 2)
        self._on_save()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  Diálogo: ticket de venta
# ══════════════════════════════════════════════════════════════
class ReceiptDialog(ctk.CTkToplevel):
    def __init__(self, parent, cart: list, method: str,
                 total: float, discount: float, afip_result: dict | None = None):
        super().__init__(parent)
        has_afip = bool(afip_result and afip_result.get("cae"))
        self.title("Ticket de venta")
        self.geometry(f"430x{'640' if has_afip else '560'}")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build(cart, method, total, discount, afip_result or {})

    def _build(self, cart, method, total, discount, afip):
        company = api.get_setting("company_name", "CoreStack Pro")
        cuit    = api.get_setting("company_cuit", "")

        ctk.CTkLabel(self, text=company,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(22, 2))
        if cuit:
            ctk.CTkLabel(self, text=f"CUIT: {cuit}",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack()
        ctk.CTkLabel(self, text=datetime.now().strftime("%d/%m/%Y %H:%M"),
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack()

        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=22, pady=10)

        # Ítems
        sc = ctk.CTkScrollableFrame(
            self, fg_color=theme.CARD2, corner_radius=10, height=150)
        sc.pack(fill="x", padx=22, pady=(0, 10))
        for item in cart:
            r = ctk.CTkFrame(sc, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=12)
            ctk.CTkLabel(r, text=f"{item['name']} ×{item['qty']}",
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=f"${item['total']:,.2f}",
                         text_color=theme.C_BLUE).pack(side="right")

        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=22, pady=8)

        # Totales fiscales
        fi = ctk.CTkFrame(self, fg_color="transparent")
        fi.pack(fill="x", padx=30)

        def row(lbl, val, color=None, big=False):
            r = ctk.CTkFrame(fi, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=lbl,
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11 if not big else 14)).pack(side="left")
            ctk.CTkLabel(r, text=val,
                         text_color=color or theme.TEXT,
                         font=ctk.CTkFont(
                             size=12 if not big else 20,
                             weight="bold" if big else "normal")).pack(side="right")

        gross = sum(i["total"] for i in cart)
        _, bd = api.calculate_tax_breakdown_multi(total)
        row("Subtotal bruto:", f"${gross:,.2f}")
        if discount > 0:
            row("Descuento:", f"−${discount:,.2f}", theme.C_BLUE)
        for t in bd:
            row(f"{t['name']} {t['percent']:.0f}%:",
                f"${t['amount']:,.2f}", theme.C_ORANGE)
        ctk.CTkFrame(fi, height=1, fg_color=theme.DIV).pack(fill="x", pady=5)
        row("TOTAL:", f"${total:,.2f}", theme.C_GREEN, big=True)
        row("Método de pago:", method)

        # AFIP
        if api.afip_esta_habilitado():
            ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=22, pady=8)
            af = ctk.CTkFrame(self, fg_color=theme.CARD2, corner_radius=10)
            af.pack(fill="x", padx=22)
            if afip.get("cae"):
                ctk.CTkLabel(af, text="Autorizado por AFIP",
                             text_color=theme.C_GREEN,
                             font=ctk.CTkFont(size=12, weight="bold")).pack(
                    anchor="w", padx=14, pady=(10, 4))
                for lbl, val in [("Nro.:", str(afip.get("nro", ""))),
                                  ("CAE:", afip["cae"]),
                                  ("Vto.:", afip.get("cae_vto", ""))]:
                    r2 = ctk.CTkFrame(af, fg_color="transparent")
                    r2.pack(fill="x", padx=14, pady=2)
                    ctk.CTkLabel(r2, text=lbl, text_color=theme.TEXT_DIM,
                                 font=ctk.CTkFont(size=11)).pack(side="left")
                    ctk.CTkLabel(r2, text=val,
                                 font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
                ctk.CTkFrame(af, height=4, fg_color="transparent").pack()
            elif afip.get("error"):
                ctk.CTkLabel(af, text="No autorizado por AFIP",
                             text_color=theme.C_RED,
                             font=ctk.CTkFont(size=12, weight="bold")).pack(
                    anchor="w", padx=14, pady=(10, 2))
                ctk.CTkLabel(af, text=afip["error"][:220],
                             text_color="#ff8a80",
                             font=ctk.CTkFont(size=10),
                             wraplength=370, justify="left").pack(
                    anchor="w", padx=14, pady=(0, 10))

        ctk.CTkButton(self, text="Cerrar", height=40,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self.destroy).pack(fill="x", padx=26, pady=14)


# ══════════════════════════════════════════════════════════════
#  Diálogo: dispositivos MP
# ══════════════════════════════════════════════════════════════
class MPDevicesDialog(ctk.CTkToplevel):
    def __init__(self, parent, devices: list):
        super().__init__(parent)
        self.title("Dispositivos MercadoPago Point")
        self.geometry("540x360")
        self.resizable(False, True)
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text="Dispositivos registrados en tu cuenta",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(18, 4))
        ctk.CTkLabel(self, text="Copiá el Device ID y pegalo en Configuración → POS / Pagos.",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM).pack(pady=(0, 10))

        if not devices:
            ctk.CTkLabel(self, text="No se encontraron dispositivos.",
                         text_color=theme.C_ORANGE,
                         font=ctk.CTkFont(size=13)).pack(pady=20)
        else:
            sc = ctk.CTkScrollableFrame(
                self, fg_color=theme.CARD2, corner_radius=10)
            sc.pack(fill="both", expand=True, padx=16)
            for dev in devices:
                did = dev.get("id", "—")
                c = ctk.CTkFrame(sc, fg_color=theme.CARD, corner_radius=8)
                c.pack(fill="x", padx=8, pady=4)
                rw = ctk.CTkFrame(c, fg_color="transparent")
                rw.pack(fill="x", padx=14, pady=10)
                ctk.CTkLabel(rw, text=did,
                             font=ctk.CTkFont(size=12, weight="bold",
                                              family="Courier New"),
                             text_color=theme.C_BLUE).pack(side="left")
                ctk.CTkButton(rw, text="Copiar", width=90, height=26,
                              fg_color=theme.ACCENT, hover_color=theme.ACCENT_H,
                              command=lambda d=did: (
                                  self.clipboard_clear(),
                                  self.clipboard_append(d),
                                  self.update())
                              ).pack(side="right")

        ctk.CTkButton(self, text="Cerrar", height=34,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT,
                      command=self.destroy).pack(pady=10)


# ══════════════════════════════════════════════════════════════
#  Diálogo: apertura de caja
# ══════════════════════════════════════════════════════════════
class CashSessionOpenDialog(ctk.CTkToplevel):
    def __init__(self, parent, id_user: int, on_open):
        super().__init__(parent)
        self._id_user = id_user
        self._on_open = on_open
        self.title("Apertura de caja")
        self.geometry("360x240")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text="Apertura de caja",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(22, 4))
        ctk.CTkLabel(self, text="Ingresá el efectivo inicial en caja",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack()
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=22, pady=14)

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=30)
        ctk.CTkLabel(frm, text="Monto inicial ($):", anchor="w",
                     text_color=theme.TEXT_DIM).pack(fill="x")
        self._amt = ctk.CTkEntry(frm, placeholder_text="0.00",
                                  font=ctk.CTkFont(size=20), justify="center", height=42)
        self._amt.pack(fill="x", pady=(4, 0))
        self._amt.bind("<Return>", lambda _: self._open())

        self._err = ctk.CTkLabel(self, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=6)
        ctk.CTkButton(self, text="Abrir caja", height=40,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._open).pack(fill="x", padx=30, pady=(0, 18))

    def _open(self):
        try:
            amount = float(self._amt.get() or "0")
            assert amount >= 0
        except (ValueError, AssertionError):
            self._err.configure(text="Monto inválido.")
            return
        api.open_cash_session(self._id_user, amount)
        sess = api.get_active_cash_session(self._id_user)
        self._on_open(sess)
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  Diálogo: cierre de caja
# ══════════════════════════════════════════════════════════════
class CashSessionCloseDialog(ctk.CTkToplevel):
    def __init__(self, parent, session: dict, id_user: int, on_close):
        super().__init__(parent)
        self._session  = session
        self._on_close = on_close
        self.title("Cierre de caja")
        self.geometry("460x510")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text="Cierre de caja",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(22, 4))

        # Resumen de la sesión
        summary = api.get_cash_session_summary(session["id"])
        sc = ctk.CTkScrollableFrame(
            self, fg_color=theme.CARD2, corner_radius=12, height=175)
        sc.pack(fill="x", padx=22, pady=(8, 4))

        ctk.CTkLabel(sc, text="Resumen por método de pago",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=12, pady=(8, 4))

        for method, count, total, taxes in summary["rows"]:
            r = ctk.CTkFrame(sc, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(r, text=f"{method} ×{int(count)}",
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=f"${float(total):,.2f}",
                         text_color=theme.C_GREEN).pack(side="right")

        ctk.CTkLabel(sc,
                     text=f"Total: ${summary['total']:,.2f}"
                          f"({summary['ticket_count']} tickets)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.C_BLUE).pack(anchor="e", padx=12, pady=(6, 8))

        # Formulario de cierre
        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=26)

        ctk.CTkLabel(frm, text="Efectivo contado al cerrar ($):",
                     anchor="w", text_color=theme.TEXT_DIM).pack(fill="x", pady=(8, 0))
        self._close_e = ctk.CTkEntry(
            frm, placeholder_text="0.00",
            font=ctk.CTkFont(size=17), justify="center", height=40)
        self._close_e.pack(fill="x", pady=(2, 8))

        self._expected = summary["cash_total"]
        self._diff_lbl = ctk.CTkLabel(
            frm, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self._diff_lbl.pack(anchor="w", pady=(0, 8))
        self._close_e.bind("<KeyRelease>", self._calc_diff)

        ctk.CTkLabel(frm, text="Observaciones:",
                     anchor="w", text_color=theme.TEXT_DIM).pack(fill="x")
        self._notes = ctk.CTkEntry(frm, placeholder_text="Sin novedad", height=34)
        self._notes.pack(fill="x", pady=(2, 0))

        self._err = ctk.CTkLabel(self, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=6)

        ctk.CTkButton(self, text="Confirmar cierre de caja", height=40,
                      fg_color=theme.BTN_PURPLE, hover_color=theme.BTN_PURPLEH,
                      command=self._close).pack(fill="x", padx=26, pady=(0, 18))

    def _calc_diff(self, _=None):
        try:
            counted = float(self._close_e.get())
            diff    = round(counted - self._expected, 2)
            sign    = "+" if diff >= 0 else ""
            self._diff_lbl.configure(
                text=f"Esperado: ${self._expected:,.2f} → Diferencia: {sign}${diff:,.2f}",
                text_color=theme.C_GREEN if diff >= 0 else theme.C_RED)
        except ValueError:
            self._diff_lbl.configure(text="")

    def _close(self):
        try:
            closing = float(self._close_e.get() or "0")
        except ValueError:
            self._err.configure(text="Monto inválido.")
            return
        api.close_cash_session(
            self._session["id"], closing,
            self._expected, self._notes.get().strip())
        messagebox.showinfo("Caja cerrada",
                            "La sesión fue cerrada correctamente.")
        self._on_close()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  Diálogo: historial de sesiones
# ══════════════════════════════════════════════════════════════
class CashHistoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, id_user: int):
        super().__init__(parent)
        self.title("Historial de sesiones de caja")
        self.geometry("780x440")
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text="Historial de sesiones",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(18, 8))

        frame = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        cols = ("ID", "Apertura", "Cierre", "Inicial", "Contado", "Dif.", "Estado", "Usuario")
        tree = ttk.Treeview(
            frame, columns=cols,
            show="headings", style="Cs.Treeview")
        tree.tag_configure("abierta", foreground=theme.C_GREEN)
        tree.tag_configure("neg",     foreground=theme.C_RED)

        for col, w in zip(cols, [45, 150, 150, 110, 110, 90, 80, 110]):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")

        rows = api.get_cash_sessions_history(id_user, limit=60)
        for (id_s, opened, closed, oa, ca, diff, status, uname) in rows:
            df  = float(diff) if diff is not None else 0.0
            tag = ("abierta" if status == "abierta"
                   else "neg" if df < 0
                   else "")
            tree.insert("", "end", values=(
                id_s,
                str(opened)[:16]  if opened else "—",
                str(closed)[:16]  if closed else "—",
                f"${float(oa):,.2f}",
                f"${float(ca):,.2f}" if ca is not None else "—",
                f"${df:+,.2f}"       if diff is not None else "—",
                status.capitalize(),
                uname or "—",
            ), tags=(tag,))

        sc = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        sc.pack(side="right", fill="y", pady=8)
