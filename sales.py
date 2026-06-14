"""sales.py – Módulo de Ventas unificado (POS + MercadoLibre).
Columna "Canal" para distinguir el origen de cada venta.
Export Excel/PDF incluye ambos canales.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading
import api
import theme
import widgets as W

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.units import cm
    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False

# Icono por canal
_CANAL_ICONS = {
    "POS":           "🖥",
    "MercadoLibre":  "🛍",
}
_CANAL_COLORS = {
    "POS":           theme.C_BLUE,
    "MercadoLibre":  "#3483fa",
}


class SalesFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user      = user
        self._all_rows = []
        self._build_ui()

    def _build_ui(self):
        extra = []
        if _HAS_PDF:
            extra.append(dict(text="PDF", width=90, fg_color=theme.BTN_PURPLE,
                              hover_color=theme.BTN_PURPLEH, command=self._export_pdf))
        if _HAS_PANDAS:
            extra.append(dict(text="Excel", width=90, fg_color=theme.BTN_BLUE,
                              hover_color=theme.BTN_BLUEH, command=self._export_excel))
        W.page_header(self, "Ventas", refresh_cmd=self.on_show, extra_btns=extra)

        # KPI row
        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=24, pady=(0, 10))

        # Filtros
        bar = W.filter_bar(self)

        ctk.CTkLabel(bar, text="Canal:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(14, 4), pady=8)
        self._canal_var = ctk.StringVar(value="Todos")
        self._canal_menu = ctk.CTkOptionMenu(
            bar, variable=self._canal_var,
            values=["Todos", "POS", "MercadoLibre"],
            width=140, height=34,
            command=lambda _: self._apply_filter())
        self._canal_menu.pack(side="left")

        ctk.CTkLabel(bar, text="Desde:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 4))
        self._date_from = ctk.CTkEntry(bar, width=110, height=34,
                                        placeholder_text="AAAA-MM-DD")
        self._date_from.pack(side="left")

        ctk.CTkLabel(bar, text="Hasta:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 4))
        self._date_to = ctk.CTkEntry(bar, width=110, height=34,
                                      placeholder_text="AAAA-MM-DD")
        self._date_to.pack(side="left")

        ctk.CTkLabel(bar, text="Método:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 4))
        self._pay_var = ctk.StringVar(value="Todos")
        self._pay_menu = ctk.CTkOptionMenu(bar, variable=self._pay_var,
                                            values=["Todos"], width=150, height=34)
        self._pay_menu.pack(side="left")

        ctk.CTkButton(bar, text="Filtrar", width=80, height=34, corner_radius=7,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_H,
                      command=self._apply_filter).pack(side="left", padx=(10, 4))
        ctk.CTkButton(bar, text="✕", width=36, height=34, corner_radius=7,
                      fg_color="transparent", hover_color=theme.CARD2,
                      text_color=theme.TEXT_DIM,
                      command=self._clear_filter).pack(side="left")

        self._total_lbl = ctk.CTkLabel(bar, text="", text_color=theme.TEXT_DIM,
                                        font=ctk.CTkFont(size=11))
        self._total_lbl.pack(side="right", padx=16)

        # Leyenda de canales
        legend = ctk.CTkFrame(self, fg_color="transparent")
        legend.pack(fill="x", padx=24, pady=(0, 6))
        for canal, color in _CANAL_COLORS.items():
            icon = _CANAL_ICONS.get(canal, "·")
            ctk.CTkLabel(legend, text=f" {icon} {canal} ",
                         fg_color=color, corner_radius=5,
                         text_color="#ffffff",
                         font=ctk.CTkFont(size=10), padx=6, pady=2).pack(
                side="left", padx=(0, 6))

        # Tabla — columna Canal añadida
        cols    = ("ID", "Canal", "Productos", "Método", "Neto", "Impuesto", "Total", "Cant.", "Fecha")
        widths  = [50, 100, 240, 120, 95, 95, 105, 55, 165]
        anchors = ["center", "center", "w", "center", "e", "e", "e", "center", "center"]
        self._tf, self.tree = W.make_tree(self, cols, widths, anchors, height=20)

        # Tags de color por canal
        self.tree.tag_configure("POS",          foreground=theme.C_BLUE)
        self.tree.tag_configure("MercadoLibre", foreground="#3483fa")

        self.tree.bind("<Double-1>", self._show_detail)
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 6))

        ctk.CTkLabel(self, text="Doble clic para ver el detalle de la venta",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=28, pady=(2, 8))

    def _refresh_treeview_style(self):
        self.tree.configure(style="Cs.Treeview")

    def on_show(self):
        self._load_kpis()
        self._load_payment_options()
        # Cargar en background para no bloquear la UI
        threading.Thread(target=self._load_data_bg, daemon=True).start()

    def _load_data_bg(self):
        """Carga los datos unificados en un thread y actualiza la UI."""
        try:
            rows = self._fetch_unified()
            self.after(0, lambda r=rows: self._set_rows(r))
        except Exception as e:
            self.after(0, lambda err=str(e): self._total_lbl.configure(
                text=f"Error: {err}", text_color=theme.C_RED))

    def _fetch_unified(self) -> list:
        canal = "" if self._canal_var.get() == "Todos" else self._canal_var.get()
        df    = self._date_from.get().strip()
        dt    = self._date_to.get().strip()
        pay   = "" if self._pay_var.get() == "Todos" else self._pay_var.get()
        return api.get_all_sells_unified(
            limit=1000, date_from=df, date_to=dt,
            payment=pay, canal=canal)

    def _set_rows(self, rows: list):
        self._all_rows = rows
        self._render_table()

    def _load_kpis(self):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        for i in range(5):
            self._kpi_row.columnconfigure(i, weight=1)

        s     = api.get_sells_summary()
        taxes = api.get_active_taxes()
        tn    = "+".join(t[1] for t in taxes) if taxes else api.get_setting("tax_name", "IVA")

        # KPI de ML si hay Neon
        ml_rev = 0.0
        try:
            from neon_db import execute_query_pg as _eq
            r = _eq(
                "SELECT COALESCE(SUM(total_amount),0) FROM ml_orders "
                "WHERE status NOT IN ('cancelled') "
                "  AND EXTRACT(MONTH FROM date_created)=EXTRACT(MONTH FROM CURRENT_DATE) "
                "  AND EXTRACT(YEAR FROM date_created)=EXTRACT(YEAR FROM CURRENT_DATE)",
                fetch="one")
            ml_rev = float(r[0]) if r and r[0] else 0.0
        except Exception:
            pass

        for col, (icon, label, value, sub, color) in enumerate([
            ("", "Hoy (POS)",      f"${s['today_revenue']:,.0f}", f"{s['today_count']} tickets", theme.C_BLUE),
            ("", "Esta semana",   f"${s['week_revenue']:,.0f}",  f"{s['week_count']} tickets",  theme.C_PURPLE),
            ("", "Mes (POS)",     f"${s['month_revenue']:,.0f}", f"{s['month_count']} tickets", theme.C_GREEN),
            ("", "Mes (ML)",      f"${ml_rev:,.0f}",             "MercadoLibre",                "#3483fa"),
            ("", tn[:18],         f"${s['month_tax']:,.0f}",    "tributos",                    theme.C_ORANGE),
        ]):
            W.kpi_card(self._kpi_row, icon, label, value, sub, color, col)

    def _load_payment_options(self):
        methods = ["Todos"] + (api.get_payment_methods() or [])
        self._pay_menu.configure(values=methods)

    def _apply_filter(self):
        self._total_lbl.configure(text="Cargando…", text_color=theme.TEXT_DIM)
        threading.Thread(target=self._load_data_bg, daemon=True).start()

    def _clear_filter(self):
        self._date_from.delete(0, "end")
        self._date_to.delete(0, "end")
        self._pay_var.set("Todos")
        self._canal_var.set("Todos")
        self._apply_filter()

    def _render_table(self):
        self.tree.delete(*self.tree.get_children())
        total_rev = total_tax = 0.0
        pos_count = ml_count = 0

        for row in self._all_rows:
            (id_, prods, pay, net, trate, tax, total, qty, dt, canal, canal_oid) = row
            tf   = float(total or 0)
            nf   = float(net or 0)
            txf  = float(tax or 0)
            total_rev += tf
            total_tax += txf

            icon  = _CANAL_ICONS.get(str(canal), "·")
            tag   = str(canal) if str(canal) in _CANAL_COLORS else ""
            label = f"{icon} {canal}"

            if canal == "POS":
                pos_count += 1
            else:
                ml_count += 1

            # IDs de ML son strings largos — mostrar abreviado
            id_display = str(id_)[:10] if len(str(id_)) > 10 else str(id_)
            # Para ML mostramos el order_id externo si está disponible
            if canal == "MercadoLibre" and canal_oid:
                id_display = str(canal_oid)[-8:]

            self.tree.insert("", "end", iid=f"{canal}_{id_}", values=(
                id_display,
                label,
                (prods or "—")[:50],
                pay or "—",
                f"${nf:,.2f}",
                f"${txf:,.2f}" if txf > 0 else "—",
                f"${tf:,.2f}",
                qty,
                str(dt)[:16] if dt else "—",
            ), tags=(tag,) if tag else ())

        tn = api.get_setting("tax_name", "IVA")
        parts = [f"{len(self._all_rows)} ventas | Total: ${total_rev:,.2f}"]
        if total_tax > 0:
            parts.append(f"{tn}: ${total_tax:,.2f}")
        if pos_count and ml_count:
            parts.append(f"POS: {pos_count}  ML: {ml_count}")
        self._total_lbl.configure(text="  |  ".join(parts),
                                   text_color=theme.TEXT_DIM)

    def _show_detail(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        row = next((r for r in self._all_rows
                    if f"{r[9]}_{r[0]}" == iid or
                       f"{r[9]}_{r[10]}" == iid.replace(f"{r[9]}_", f"{r[9]}_")), None)

        # Fallback: buscar por coincidencia de iid
        if not row:
            for r in self._all_rows:
                if str(r[0]) in iid or (r[10] and str(r[10])[-8:] in iid):
                    row = r
                    break
        if row:
            SaleDetailDialog(self, row)

    # ── Export ────────────────────────────────────────────────
    def _export_excel(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"ventas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        if not path:
            return
        cols = ["ID", "Canal", "Productos", "Método", "Neto",
                "Impuesto", "Total", "Cant.", "Fecha"]
        data = []
        for r in self._all_rows:
            (id_, prods, pay, net, trate, tax, total, qty, dt, canal, canal_oid) = r
            data.append([
                str(canal_oid or id_), canal,
                (prods or "—"), pay or "—",
                float(net or 0), float(tax or 0), float(total or 0),
                qty, str(dt)[:19] if dt else ""])
        pd.DataFrame(data, columns=cols).to_excel(path, index=False)
        messagebox.showinfo("Exportado", f"Guardado en:\n{path}")

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"cierre_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not path:
            return
        cfg      = api.get_all_settings()
        company  = cfg.get("company_name", "CoreStack Pro")
        tax_name = cfg.get("tax_name", "IVA")

        doc    = SimpleDocTemplate(path, pagesize=A4,
                                   topMargin=1.5*cm, bottomMargin=1.5*cm,
                                   leftMargin=1.5*cm, rightMargin=1.5*cm)
        styles = getSampleStyleSheet()
        ts = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, spaceAfter=4)
        ss = ParagraphStyle("sub",   fontName="Helvetica", fontSize=10,
                             textColor=rl_colors.grey)
        hs = ParagraphStyle("hdr",   fontName="Helvetica-Bold", fontSize=12,
                             spaceBefore=12, spaceAfter=4)

        s    = api.get_sells_summary()
        elem = [
            Paragraph(company, ts),
            Paragraph(f"Cierre unificado — {datetime.now().strftime('%d/%m/%Y %H:%M')}", ss),
            Spacer(1, 0.4*cm),
            HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor("#0f3460")),
            Spacer(1, 0.4*cm),
        ]

        tdata = [["Canal", "ID", "Productos", "Método", "Neto", tax_name, "Total", "Fecha"]]
        tr = tt = 0.0
        for row in self._all_rows:
            (id_, prods, pay, net, trate, tax, total, qty, dt, canal, canal_oid) = row
            tf = float(total or 0); nf = float(net or 0); txf = float(tax or 0)
            tr += tf; tt += txf
            tdata.append([
                canal,
                str(canal_oid or id_)[-10:],
                (prods or "—")[:40],
                pay or "—",
                f"${nf:,.2f}", f"${txf:,.2f}", f"${tf:,.2f}",
                str(dt)[:10] if dt else "—"])
        tdata.append(["", "TOTAL", "", "", f"${tr-tt:,.2f}", f"${tt:,.2f}", f"${tr:,.2f}", ""])

        cws = [2.3*cm, 1.8*cm, 5.5*cm, 2.8*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.0*cm]
        t = Table(tdata, colWidths=cws, repeatRows=1)
        last = len(tdata) - 1
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0),    (-1, 0),    rl_colors.HexColor("#0f3460")),
            ("TEXTCOLOR",  (0, 0),    (-1, 0),    rl_colors.white),
            ("FONTNAME",   (0, 0),    (-1, 0),    "Helvetica-Bold"),
            ("BACKGROUND", (0, last), (-1, last), rl_colors.HexColor("#1b5e20")),
            ("TEXTCOLOR",  (0, last), (-1, last), rl_colors.white),
            ("FONTNAME",   (0, last), (-1, last), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, last-1),
             [rl_colors.white, rl_colors.HexColor("#f5f5f5")]),
            ("GRID",       (0, 0),    (-1, -1),   0.3, rl_colors.lightgrey),
            ("FONTSIZE",   (0, 0),    (-1, -1),   8),
            ("ALIGN",      (4, 0),    (-1, -1),   "RIGHT"),
            ("ALIGN",      (0, 0),    (3, -1),    "CENTER"),
        ]))
        elem += [Paragraph("Detalle de ventas (todos los canales)", hs), t,
                 Spacer(1, 0.5*cm),
                 Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} — CoreStack Pro", ss)]
        doc.build(elem)
        messagebox.showinfo("Exportado", f"PDF guardado en:\n{path}")


# ── Diálogo de detalle ─────────────────────────────────────────
class SaleDetailDialog(ctk.CTkToplevel):
    def __init__(self, parent, row: tuple):
        super().__init__(parent)
        (id_, prods, pay, net, trate, tax, total, qty, dt, canal, canal_oid) = row
        self.title(f"Detalle venta — {canal}")
        self.geometry("480x520")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        company = api.get_setting("company_name", "CoreStack Pro")
        tf  = float(total or 0)
        nf  = float(net or 0)
        txf = float(tax or 0)
        trf = float(trate or 21)

        canal_color = _CANAL_COLORS.get(str(canal), theme.C_BLUE)
        icon        = _CANAL_ICONS.get(str(canal), "·")

        # Header
        hdr = ctk.CTkFrame(self, fg_color=canal_color, height=56, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(side="left", fill="y", padx=18)
        ctk.CTkLabel(hi, text=f"{icon}  {canal}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").pack(side="left", pady=16)

        order_ref = str(canal_oid) if canal_oid else f"#{id_}"
        ctk.CTkLabel(hdr, text=f"Orden {order_ref[-12:]}",
                     font=ctk.CTkFont(size=11),
                     text_color="#e0e0e0").pack(side="right", padx=18, pady=18)

        # Info general
        ctk.CTkLabel(self, text=company,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(14, 0))
        ctk.CTkLabel(self, text=str(dt)[:19] if dt else "—",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).pack()

        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=10)

        # Ítems (para POS cargamos detalle real; para ML mostramos el título)
        det_f = ctk.CTkScrollableFrame(self, height=120,
                                        fg_color=theme.CARD2, corner_radius=10)
        det_f.pack(fill="x", padx=20, pady=(0, 8))

        if str(canal) == "POS":
            detail_rows = api.get_sell_detail(int(id_)) or []
            if detail_rows:
                for prod, qty_d, sub in detail_rows:
                    r = ctk.CTkFrame(det_f, fg_color="transparent")
                    r.pack(fill="x", pady=2, padx=12)
                    ctk.CTkLabel(r, text=f"{prod} ×{qty_d}", anchor="w").pack(side="left")
                    ctk.CTkLabel(r, text=f"${float(sub):,.2f}",
                                 text_color=theme.C_BLUE).pack(side="right")
            else:
                ctk.CTkLabel(det_f, text="Sin detalle de items.",
                             text_color=theme.TEXT_DIM).pack(pady=12)
        else:
            # ML: mostrar título y comprador
            ctk.CTkLabel(det_f,
                         text=prods or "—",
                         font=ctk.CTkFont(size=12),
                         text_color=theme.TEXT,
                         wraplength=400, justify="left").pack(
                padx=12, pady=12, anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=8)

        # Fiscal
        fi = ctk.CTkFrame(self, fg_color="transparent")
        fi.pack(fill="x", padx=30, pady=4)

        def row_lbl(lbl, val, color=None, big=False):
            r = ctk.CTkFrame(fi, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=lbl, anchor="w", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11 if not big else 14)).pack(side="left")
            ctk.CTkLabel(r, text=val, text_color=color or theme.TEXT,
                         font=ctk.CTkFont(size=12 if not big else 20,
                                          weight="bold" if big else "normal")).pack(side="right")

        row_lbl("Subtotal (sin impuestos):", f"${nf:,.2f}")
        if txf > 0:
            taxes = api.get_active_taxes()
            if taxes:
                total_pct = sum(float(t[2]) for t in taxes) or trf
                for _, t_name, t_pct, _ in taxes:
                    share = round(txf * float(t_pct) / total_pct, 2)
                    row_lbl(f"{t_name} ({float(t_pct):.0f}%):", f"${share:,.2f}", theme.C_ORANGE)
            else:
                row_lbl(f"Impuesto ({trf:.0f}%):", f"${txf:,.2f}", theme.C_ORANGE)

        ctk.CTkFrame(fi, height=1, fg_color=theme.DIV).pack(fill="x", pady=6)
        row_lbl("TOTAL:", f"${tf:,.2f}", theme.C_GREEN, big=True)
        row_lbl("Método / Canal:", f"{pay or '—'}  [{canal}]")

        ctk.CTkButton(self, text="Cerrar", width=100, height=34,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT,
                      command=self.destroy).pack(pady=14)
