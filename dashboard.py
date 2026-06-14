"""dashboard.py – Panel principal CoreStack Pro.

Diseño:
 · UI construida UNA SOLA VEZ en __init__ — sin destroy/rebuild
 · on_show() solo actualiza números/filas, sin flash al volver a entrar
 · Carga de datos en background thread → la UI nunca se congela
 · Bug fix: cada sub_lbl se guarda con su key correcto
 · v0.9: Calendario de despachos ML + panel de alertas integrado"""

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime
import threading
import api
import theme
import widgets as W

# Importar el calendario/alertas ML (silencioso si no está disponible)
try:
    from ml_calendar import MLDashboardCalendarFrame
    _HAS_ML_CALENDAR = True
except ImportError:
    _HAS_ML_CALENDAR = False

_WEEK_DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user         = user
        self._app         = app
        self._ml_user_id  = ""
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._chart_lbl:  ctk.CTkLabel | None = None
        self._low_tree:   ttk.Treeview  | None = None
        self._low_tf:     ctk.CTkFrame  | None = None
        self._low_title:  ctk.CTkLabel  | None = None
        self._sales_tree: ttk.Treeview  | None = None
        self._cal_block   = None
        self._loading = False
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  Construcción de UI (solo una vez)
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        self._refresh_btn = ctk.CTkButton(
            hdr, text="Actualizar", width=110, height=30,
            corner_radius=7, fg_color=theme.CARD2,
            hover_color=theme.ACCENT_H, text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=12), command=self.on_show)
        self._refresh_btn.pack(side="right")

        self._loading_lbl = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM)
        self._loading_lbl.pack(side="right", padx=(0, 10))

        # Scroll container
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._build_kpi_row()
        self._build_chart_section()
        self._build_low_stock_section()
        self._build_recent_sales_section()
        self._build_calendar_section()

    # ── KPIs ───────────────────────────────────────────────
    def _build_kpi_row(self):
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        for i in range(4):
            row.columnconfigure(i, weight=1)

        kpi_defs = [
            ("today",  "", "Ventas hoy",     theme.C_BLUE),
            ("week",   "", "Esta semana",    theme.C_PURPLE),
            ("month",  "", "Este mes",       theme.C_GREEN),
            ("tax",    "", "Impuestos mes",  theme.C_ORANGE),
        ]

        for col, (key, icon, title, color) in enumerate(kpi_defs):
            card = ctk.CTkFrame(row, fg_color=theme.CARD, corner_radius=14)
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 8, 0), pady=2)

            # Ícono con fondo de color suave
            icon_bg = ctk.CTkFrame(card, fg_color=theme.CARD2,
                                   corner_radius=10, width=42, height=42)
            icon_bg.pack(pady=(16, 6))
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text=icon,
                         font=ctk.CTkFont(size=20)).pack(expand=True)

            val_lbl = ctk.CTkLabel(card, text="—",
                                   font=ctk.CTkFont(size=22, weight="bold"),
                                   text_color=color)
            val_lbl.pack()

            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=theme.TEXT).pack(pady=(2, 0))

            sub_lbl = ctk.CTkLabel(card, text="cargando…",
                                   font=ctk.CTkFont(size=10),
                                   text_color=theme.TEXT_DIM)
            sub_lbl.pack(pady=(2, 14))

            # Guardar cada label con su key única — ← FIX del bug de sobreescritura
            self._kpi_labels[f"{key}_val"] = val_lbl
            self._kpi_labels[f"{key}_sub"] = sub_lbl

    # ── Gráfico de barras ASCII ────────────────────────────
    def _build_chart_section(self):
        sec_hdr = ctk.CTkFrame(self._scroll, fg_color="transparent")
        sec_hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(sec_hdr, text="Evolucion de ventas - 7 dias",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        chart_card = ctk.CTkFrame(self._scroll, fg_color=theme.CARD, corner_radius=14)
        chart_card.pack(fill="x", pady=(0, 16))

        self._chart_lbl = ctk.CTkLabel(
            chart_card, text="",
            font=ctk.CTkFont(size=11, family="Courier New"),
            justify="left", text_color=theme.TEXT, anchor="w")
        self._chart_lbl.pack(padx=20, pady=14, fill="x")

    # ── Stock bajo ─────────────────────────────────────────
    def _build_low_stock_section(self):
        self._low_title = ctk.CTkLabel(
            self._scroll, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.C_ORANGE)
        self._low_title.pack(anchor="w", pady=(0, 6))

        self._low_tf, self._low_tree = W.make_tree(
            self._scroll,
            cols    = ("Producto", "Stock", "Proveedor", "Email"),
            widths  = [230, 80, 190, 220],
            anchors = ["w", "center", "w", "w"],
            height  = 4)
        self._low_tree.tag_configure("critical", foreground=theme.C_RED)
        self._low_tree.tag_configure("warning",  foreground=theme.C_ORANGE)
        self._low_tf.pack(fill="x", pady=(0, 16))

    # ── Últimas ventas ─────────────────────────────────────
    def _build_recent_sales_section(self):
        sec_hdr = ctk.CTkFrame(self._scroll, fg_color="transparent")
        sec_hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(sec_hdr, text="Ultimas 10 ventas",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        self._sales_tf, self._sales_tree = W.make_tree(
            self._scroll,
            cols    = ("ID", "Productos", "Método", "Total", "Fecha"),
            widths  = [50, 340, 140, 120, 180],
            anchors = ["center", "w", "center", "e", "center"],
            height  = 10)
        self._sales_tf.pack(fill="x", pady=(0, 8))

    # ── Sección calendario ML ──────────────────────────────
    def _build_calendar_section(self):
        """
        Agrega el bloque Calendario de Despachos + Alertas al final del scroll.
        Solo se construye si ml_calendar.py está disponible.
        """
        if not _HAS_ML_CALENDAR:
            return

        # Separador visual
        ctk.CTkFrame(self._scroll, height=1, fg_color=theme.SEP).pack(
            fill="x", pady=(4, 16))

        self._cal_block = MLDashboardCalendarFrame(
            self._scroll, ml_user_id="", app=self._app)
        self._cal_block.pack(fill="both", expand=True, pady=(0, 16))

    def _try_update_ml_user(self):
        """
        Intenta obtener el primer ml_user_id activo de Neon para pasarlo
        al bloque de calendario. Silencioso si ML no está configurado.
        """
        if not _HAS_ML_CALENDAR or not self._cal_block:
            return
        try:
            import ml_api
            accounts = ml_api.get_all_ml_accounts()
            active   = next((a for a in accounts if a[3]), None)
            uid      = str(active[0]) if active else ""
            if uid != self._ml_user_id:
                self._ml_user_id = uid
                self._cal_block.set_ml_user(uid)
            else:
                # mismo usuario: solo refresh
                self._cal_block.refresh_all()
        except Exception:
            pass  # ML no configurado — silencioso

    # ══════════════════════════════════════════════════════
    #  on_show — carga datos en background (sin congelar UI)
    # ══════════════════════════════════════════════════════
    def on_show(self):
        if self._loading:
            return
        self._loading = True
        self._refresh_btn.configure(state="disabled")
        self._loading_lbl.configure(text="actualizando...")
        threading.Thread(target=self._fetch_all, daemon=True).start()
        # Actualizar bloque ML en background (no bloquea)
        threading.Thread(target=self._try_update_ml_user, daemon=True).start()

    def _fetch_all(self):
        """Consultas en background, luego actualiza la UI en el hilo principal."""
        try:
            summary   = api.get_sells_summary()
            taxes     = api.get_active_taxes()
            chart     = api.get_sales_summary_last_days(7)
            low_stock = api.get_low_stock_products()
            recent    = api.get_sells_detailed(limit=10) or []
        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))
            return
        self.after(0, lambda: self._apply_data(summary, taxes, chart, low_stock, recent))

    def _apply_data(self, summary, taxes, chart, low_stock, recent):
        self._update_kpis(summary, taxes)
        self._update_chart(chart)
        self._update_low_stock(low_stock)
        self._update_recent_sales(recent)
        self._loading = False
        self._refresh_btn.configure(state="normal")
        self._loading_lbl.configure(text=f"{datetime.now().strftime('%H:%M')}")

    def _on_error(self, msg: str):
        self._loading = False
        self._refresh_btn.configure(state="normal")
        self._loading_lbl.configure(text=f"error", text_color=theme.C_RED)

    # ── Actualización de KPIs ──────────────────────────────
    def _update_kpis(self, s: dict, taxes: list):
        tn = "+".join(t[1] for t in taxes) if taxes else api.get_setting("tax_name", "IVA")
        updates = {
            "today": (f"${s['today_revenue']:,.0f}",  f"{s['today_count']} tickets"),
            "week":  (f"${s['week_revenue']:,.0f}",   f"{s['week_count']} tickets"),
            "month": (f"${s['month_revenue']:,.0f}",  f"{s['month_count']} tickets"),
            "tax":   (f"${s['month_tax']:,.0f}",      tn[:22]),
        }
        for key, (val, sub) in updates.items():
            if f"{key}_val" in self._kpi_labels:
                self._kpi_labels[f"{key}_val"].configure(text=val)
            if f"{key}_sub" in self._kpi_labels:
                self._kpi_labels[f"{key}_sub"].configure(text=sub)

    # ── Actualización del gráfico ──────────────────────────
    def _update_chart(self, data: list):
        if not data or not self._chart_lbl:
            if self._chart_lbl:
                self._chart_lbl.configure(text="Sin datos de ventas aún.")
            return

        max_v = max(float(r[1]) for r in data) or 1
        BAR   = 36
        lines = []

        for d, v in data:
            v   = float(v)
            pct = v / max_v
            filled = int(pct * BAR)
            empty  = BAR - filled

            # Coloreado visual por porcentaje
            if pct >= 0.8:
                bar = "█" * filled + "░" * empty
            elif pct >= 0.4:
                bar = "▓" * filled + "░" * empty
            else:
                bar = "▒" * filled + "░" * empty

            try:
                day = _WEEK_DAYS[datetime.strptime(str(d), "%Y-%m-%d").weekday()]
                date_str = f"{str(d)[8:10]}/{str(d)[5:7]}"
            except Exception:
                day = "???"; date_str = str(d)[-5:]

            amount_str = f"${v:>12,.2f}"
            lines.append(f"{day} {date_str} {bar} {amount_str}")

        self._chart_lbl.configure(text="\n".join(lines))

    # ── Actualización de stock bajo ────────────────────────
    def _update_low_stock(self, low: list):
        if not self._low_tree or not self._low_title or not self._low_tf:
            return
        self._low_tree.delete(*self._low_tree.get_children())

        if not low:
            self._low_title.configure(
                text="Stock en buen estado",
                text_color=theme.C_GREEN)
            self._low_tf.pack_forget()
            return

        self._low_title.configure(
            text=f"Stock bajo — {len(low)} productos necesitan reposición",
            text_color=theme.C_ORANGE)
        self._low_tf.pack(fill="x", pady=(0, 16))

        for prod, stock, mail, supplier in low:
            tag = "critical" if int(stock) <= 3 else "warning"
            self._low_tree.insert("", "end",
                                  values=(prod, stock, supplier or "—", mail or "—"),
                                  tags=(tag,))

    # ── Actualización de ventas recientes ──────────────────
    def _update_recent_sales(self, rows: list):
        if not self._sales_tree:
            return
        self._sales_tree.delete(*self._sales_tree.get_children())
        for row in rows:
            id_, prods, pay, net, trate, tax, total, qty, dt = row
            self._sales_tree.insert("", "end", values=(
                id_,
                (prods or "—")[:55],
                pay or "—",
                f"${float(total or 0):,.2f}",
                str(dt)[:16] if dt else "—",
            ))

    # ── Refresh TTK al cambiar tema ────────────────────────
    def _refresh_treeview_style(self):
        if self._low_tree:   self._low_tree.configure(style="Cs.Treeview")
        if self._sales_tree: self._sales_tree.configure(style="Cs.Treeview")
