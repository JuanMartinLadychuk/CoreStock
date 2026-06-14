"""analytics.py – Rendimiento, Proyecciones y Salud Financiera."""
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime, date
import calendar
import api, theme
import widgets as W

MONTH_NAMES = ["", "Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]


class AnalyticsFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._fc_months_var = ctk.StringVar(value="3")
        self._salary_entries: dict = {}
        self._build_ui()

    def _build_ui(self):
        W.page_header(self, "📊  Rendimiento y Proyecciones", refresh_cmd=self.on_show)

        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=24, pady=(0, 8))

        tabs = ctk.CTkTabview(self, anchor="w")
        tabs.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._tab_real      = tabs.add("Rendimiento Real")
        self._tab_forecast  = tabs.add("Proyeccion")
        self._tab_costs     = tabs.add("💸  Costos")
        self._tab_employees = tabs.add("👥  Empleados")
        self._tab_health    = tabs.add("🏥  Salud")

        for tab, builder in [
            (self._tab_real,      self._build_real_tab),
            (self._tab_forecast,  self._build_forecast_tab),
            (self._tab_costs,     self._build_costs_tab),
            (self._tab_employees, self._build_employees_tab),
            (self._tab_health,    self._build_health_tab),
        ]:
            builder(tab)

    # ── KPIs ───────────────────────────────────────────────
    def _refresh_kpis(self):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        for i in range(5):
            self._kpi_row.columnconfigure(i, weight=1)

        today      = date.today()
        days_gone  = today.day
        days_total = calendar.monthrange(today.year, today.month)[1]

        # Usar get_real_performance para el mes actual → consistencia total
        try:
            perf = api.get_real_performance(today.month, today.year)
            rev      = perf["gross_sales"]
            tax_amt  = perf["taxes"]
            # Salario a mostrar: el que esté activo (egresos o nómina)
            salaries = perf["salary_displayed"]
            net      = perf["net_performance"]
        except Exception:
            s        = api.get_sells_summary()
            rev      = s["month_revenue"]
            tax_amt  = s["month_tax"]
            salaries = self._total_salaries()
            net      = rev - tax_amt - salaries

        margin_pct = (net / rev * 100) if rev > 0 else 0
        projected  = (rev / days_gone * days_total) if days_gone else 0

        for col, (icon, label, value, sub, color) in enumerate([
            ("🗓️", "Este mes",       f"${rev:,.0f}",        f"{api.get_sells_summary()['month_count']} ventas", theme.C_GREEN),
            ("📉", "Impuestos mes",   f"${tax_amt:,.0f}",    "tributos",                                        theme.C_ORANGE),
            ("👥", "Salarios mes",    f"${salaries:,.0f}",   "nómina",                                          theme.C_RED),
            ("💰", "Renta neta real", f"${net:,.0f}",        f"margen {margin_pct:.1f}%",                       theme.C_GREEN if net >= 0 else theme.C_RED),
            ("🔮", "Proyección mes",  f"${projected:,.0f}",  f"a {days_total} días",                            theme.C_BLUE),
        ]):
            W.kpi_card(self._kpi_row, icon, label, value, sub, color, col)

    def _total_salaries(self) -> float:
        """Fallback para cuando get_real_performance no está disponible."""
        rows = api.get_all_users_with_salary()
        return sum(float(r[7] or 0) for r in rows if r[4])

    # ── Pestana Rendimiento Real ────────────────────────────
    def _build_real_tab(self, parent):
        self._real_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._real_scroll.pack(fill="both", expand=True)

    def _refresh_real(self):
        for w in self._real_scroll.winfo_children():
            w.destroy()
        p = self._real_scroll

        # Selector de mes/anio
        from datetime import date
        today = date.today()
        ctrl = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=10)
        ctrl.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(ctrl, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(inner, text="Periodo:",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        if not hasattr(self, "_real_month_var"):
            self._real_month_var = ctk.StringVar(value=str(today.month).zfill(2))
            self._real_year_var  = ctk.StringVar(value=str(today.year))
        months = [str(m).zfill(2) for m in range(1, 13)]
        years  = [str(y) for y in range(today.year - 2, today.year + 2)]
        ctk.CTkOptionMenu(inner, variable=self._real_month_var,
                          values=months, width=70,
                          command=lambda _: self._refresh_real()).pack(side="left", padx=8)
        ctk.CTkOptionMenu(inner, variable=self._real_year_var,
                          values=years, width=90,
                          command=lambda _: self._refresh_real()).pack(side="left")

        try:
            month = int(self._real_month_var.get())
            year  = int(self._real_year_var.get())
            perf  = api.get_real_performance(month, year)
        except Exception as e:
            ctk.CTkLabel(p, text=f"Error al calcular rendimiento: {e}",
                         text_color=theme.C_RED).pack(pady=20)
            return

        if perf["gross_sales"] == 0:
            ctk.CTkLabel(p, text="Sin ventas registradas en este periodo.",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=13)).pack(pady=30)
            return

        # KPI principal
        net = perf["net_performance"]
        net_color = theme.C_GREEN if net >= 0 else theme.C_RED
        kpi_outer = ctk.CTkFrame(p, fg_color=theme.CARD, corner_radius=12,
                                  border_width=1, border_color=theme.SEP)
        kpi_outer.pack(fill="x", pady=(0, 14))
        kpi_inner = ctk.CTkFrame(kpi_outer, fg_color="transparent")
        kpi_inner.pack(fill="x", padx=20, pady=18)
        kpi_inner.columnconfigure((0,1,2,3), weight=1)
        for col, (label, val, color) in enumerate([
            ("Ventas brutas",        f"${perf['gross_sales']:,.0f}",    theme.C_BLUE),
            ("COGS (reposicion)",     f"${perf['cogs']:,.0f}",           theme.C_ORANGE),
            ("Margen bruto",          f"${perf['gross_profit']:,.0f}",   theme.C_PURPLE),
            ("RENDIMIENTO NETO",      f"${net:,.0f}", net_color),
        ]):
            kpi_inner.columnconfigure(col, weight=1)
            ctk.CTkLabel(kpi_inner, text=label, font=ctk.CTkFont(size=10),
                         text_color=theme.TEXT_DIM).grid(row=0, column=col, padx=8)
            ctk.CTkLabel(kpi_inner, text=val,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=color).grid(row=1, column=col, padx=8, pady=(2,0))
        ctk.CTkLabel(kpi_inner,
                     text=f"Margen neto: {perf['margin_pct']:.1f}%",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=net_color).grid(row=2, column=3, padx=8, pady=(4,0))

        # Waterfall: desglose de la formula
        self._sec_title(p, "Desglose del rendimiento (formula real)")

        # Etiqueta de salarios con fuente
        sal_source = perf.get("salary_source", "nomina")
        sal_displayed = perf.get("salary_displayed", 0.0)
        if sal_source == "egresos":
            sal_label = "  Salarios (incluido en gastos)"
            sal_amount = 0.0   # ya descontado en expenses_total
            sal_note   = f"  → ${sal_displayed:,.0f} registrados como egresos de Sueldos"
        else:
            sal_label  = "  Salarios (nómina del sistema)"
            sal_amount = -perf["salaries"]
            sal_note   = None

        items = [
            ("Ventas brutas",                perf["gross_sales"],        theme.C_GREEN),
            ("  Comisiones medios de pago",  -perf["commissions"],       theme.C_ORANGE),
            ("  COGS por costo reposicion",  -perf["cogs"],              theme.C_ORANGE),
            ("  Impuestos",                  -perf["taxes"],             theme.C_ORANGE),
            ("  Gastos fijos",               -perf["expenses_fixed"],    theme.C_RED),
            ("  Gastos variables",           -perf["expenses_variable"], theme.C_RED),
            (sal_label,                       sal_amount,                theme.C_RED),
            ("  Perdidas por devoluciones",  -perf["return_losses"],     theme.C_RED),
        ]
        wf = ctk.CTkFrame(p, fg_color=theme.CARD, corner_radius=12,
                          border_width=1, border_color=theme.SEP)
        wf.pack(fill="x", pady=(0, 14))
        for label, amount, color in items:
            row_f = ctk.CTkFrame(wf, fg_color="transparent")
            row_f.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row_f, text=label, anchor="w",
                         font=ctk.CTkFont(size=12),
                         text_color=theme.TEXT if not label.startswith(" ") else theme.TEXT_DIM
                         ).pack(side="left")
            if amount != 0:
                ctk.CTkLabel(row_f, text=f"${abs(amount):>12,.2f}",
                             font=ctk.CTkFont(size=12),
                             text_color=color).pack(side="right")

        # Nota si salarios vienen de egresos
        if sal_note:
            note_f = ctk.CTkFrame(wf, fg_color="transparent")
            note_f.pack(fill="x", padx=16, pady=(0, 4))
            ctk.CTkLabel(note_f, text=sal_note,
                         font=ctk.CTkFont(size=10),
                         text_color="#64748b",
                         anchor="w").pack(side="left")

        ctk.CTkFrame(wf, height=1, fg_color=theme.SEP).pack(fill="x", padx=16, pady=4)
        net_row = ctk.CTkFrame(wf, fg_color="transparent")
        net_row.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkLabel(net_row, text="Rendimiento Neto Real",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkLabel(net_row, text=f"${perf['net_performance']:>12,.2f}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=net_color).pack(side="right")

        # USD equivalente
        if perf.get("net_usd_blue") is not None or perf.get("net_usd_oficial") is not None:
            usd_f = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=10)
            usd_f.pack(fill="x", pady=(0, 14))
            usd_i = ctk.CTkFrame(usd_f, fg_color="transparent")
            usd_i.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(usd_i, text="Equivalente en USD:",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=theme.TEXT_DIM).pack(side="left")
            if perf.get("net_usd_blue") is not None:
                ctk.CTkLabel(usd_i,
                             text=f"  Blue: u$s{perf['net_usd_blue']:,.0f}",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=theme.C_BLUE).pack(side="left", padx=12)
            if perf.get("net_usd_oficial") is not None:
                ctk.CTkLabel(usd_i,
                             text=f"  Oficial: u$s{perf['net_usd_oficial']:,.0f}",
                             font=ctk.CTkFont(size=12),
                             text_color=theme.TEXT_DIM).pack(side="left")

        # COGS: comparacion costo compra vs reposicion
        if perf["cogs_diff"] > 0:
            self._sec_title(p, "Impacto de la inflacion en el stock")
            inf_card = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
            inf_card.pack(fill="x", pady=(0, 14))
            ir = ctk.CTkFrame(inf_card, fg_color="transparent")
            ir.pack(fill="x", padx=20, pady=16)
            ir.columnconfigure((0,1,2), weight=1)
            for col, (label, val, color) in enumerate([
                ("COGS por costo de compra",    f"${perf['cogs_by_purchase']:,.0f}", theme.C_BLUE),
                ("COGS por costo de reposicion", f"${perf['cogs']:,.0f}",            theme.C_ORANGE),
                ("Diferencia (impacto inflacion)", f"${perf['cogs_diff']:,.0f}",     theme.C_RED),
            ]):
                ctk.CTkLabel(ir, text=label, font=ctk.CTkFont(size=10),
                             text_color=theme.TEXT_DIM).grid(row=0, column=col, padx=8)
                ctk.CTkLabel(ir, text=val,
                             font=ctk.CTkFont(size=15, weight="bold"),
                             text_color=color).grid(row=1, column=col, padx=8, pady=(2,8))
            ctk.CTkLabel(inf_card,
                         text=f"El negocio necesito ${perf['cogs_diff']:,.0f} extra este mes para reponer el stock vendido.",
                         font=ctk.CTkFont(size=11), text_color=theme.C_ORANGE,
                         wraplength=700).pack(padx=20, pady=(0, 12))

        # Comisiones por metodo
        if perf["commission_detail"]:
            self._sec_title(p, "Comisiones por metodo de pago")
            tf, tree = W.make_tree(p, ["Metodo", "Facturado", "Comision"],
                                   [220, 200, 200], height=len(perf["commission_detail"])+1)
            for item in perf["commission_detail"]:
                tree.insert("", "end", values=(
                    item["method"],
                    f"${item['subtotal']:,.2f}",
                    f"${item['commission']:,.2f}",
                ))
            tf.pack(fill="x", pady=(0, 14))

        # Gastos del período seleccionado (no siempre el mes actual)
        exp_rows = api.get_expenses(month=month, year=year)
        if exp_rows:
            self._sec_title(p, f"Gastos operativos — {month:02d}/{year} ({len(exp_rows)} items)")
            tf2, tree2 = W.make_tree(p, ["Descripcion", "Categoria", "Tipo", "Monto"],
                                     [280, 150, 90, 150],
                                     height=min(8, len(exp_rows)))
            tree2.tag_configure("fijo",     foreground=theme.C_BLUE)
            tree2.tag_configure("variable", foreground=theme.C_ORANGE)
            tree2.tag_configure("sueldos",  foreground=theme.C_RED)
            for row in exp_rows:
                tag = "sueldos" if row[4] == "Sueldos" else row[3]
                tree2.insert("", "end", values=(
                    row[1][:50], row[4], row[3].capitalize(), f"${float(row[2]):,.2f}"
                ), tags=(tag,))
            tf2.pack(fill="x", pady=(0, 14))

        # Devoluciones del mes
        ret_rows = api.get_returns(month=month, year=year)
        if ret_rows:
            self._sec_title(p, f"Devoluciones del mes ({len(ret_rows)})")
            tf3, tree3 = W.make_tree(p, ["Producto", "Estado", "Reintegro"],
                                     [280, 150, 150], height=min(6, len(ret_rows)))
            for r in ret_rows:
                tree3.insert("", "end", values=(r[2][:40], r[6], f"${float(r[5]):,.2f}"))
            tf3.pack(fill="x", pady=(0, 14))


    # -- Pestana Proyeccion --
    def _build_forecast_tab(self, parent):
        self._fc_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._fc_scroll.pack(fill="both", expand=True)

    def _refresh_forecast(self):
        for w in self._fc_scroll.winfo_children():
            w.destroy()
        p = self._fc_scroll

        ctrl = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=10)
        ctrl.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(ctrl, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(inner, text="Proyectar:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkOptionMenu(inner, variable=self._fc_months_var,
                          values=["1","2","3","6","12"], width=80,
                          command=lambda _: self._refresh_forecast()).pack(side="left", padx=8)
        ctk.CTkLabel(inner, text="meses hacia adelante", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left")

        hist = api.get_monthly_revenue_history(6)
        if not hist:
            ctk.CTkLabel(p, text="⚠️  Sin datos históricos suficientes.",
                         text_color=theme.C_ORANGE, font=ctk.CTkFont(size=13)).pack(pady=30)
            return

        months_ahead = int(self._fc_months_var.get())
        values = [float(r[2]) for r in hist]; n = len(values)
        avg = sum(values)/n; indices = list(range(n)); slope = 0.0
        if n >= 2:
            mx  = (n-1)/2
            num = sum((indices[i]-mx)*(values[i]-avg) for i in range(n))
            den = sum((indices[i]-mx)**2 for i in range(n))
            slope = num/den if den else 0.0

        projections = []
        ly, lm = int(hist[-1][0]), int(hist[-1][1])
        for k in range(1, months_ahead+1):
            pv = max(0, avg + slope*(n-1+k))
            m = lm+k; y = ly+(m-1)//12; m = ((m-1)%12)+1
            projections.append((y, m, pv))

        # Tabla histórica + proyección
        self._sec_title(p, "Histórico de ingresos vs. proyección")
        tf, tree = W.make_tree(p, ["Período","Ingresos","Variación","Tipo"],
                               [160,180,160,120], height=len(hist)+months_ahead+1)
        tree.tag_configure("hist", foreground=theme.C_GREEN)
        tree.tag_configure("proj", foreground=theme.C_BLUE)
        tree.tag_configure("pn",   foreground=theme.C_ORANGE)
        prev = None
        for yr, mo, rev in hist:
            rev = float(rev); var = f"{((rev-prev)/prev*100):+.1f}%" if prev else "—"
            tree.insert("","end", values=(f"{MONTH_NAMES[int(mo)]} {yr}", f"${rev:,.2f}", var, "Real"), tags=("hist",))
            prev = rev
        for yr, mo, pv in projections:
            var = f"{((pv-prev)/prev*100):+.1f}%" if prev else "—"
            tag = "proj" if pv >= (prev or 0) else "pn"
            tree.insert("","end", values=(f"🔮 {MONTH_NAMES[int(mo)]} {yr}", f"${pv:,.2f}", var, "Proyectado"), tags=(tag,))
            prev = pv
        tf.pack(fill="x", pady=(0, 10))

        # Gráfico ASCII
        self._sec_title(p, "Gráfico de tendencia")
        all_data = [(f"{MONTH_NAMES[int(m)]} {y}", float(v)) for y,m,v in hist]
        all_data += [(f"🔮{MONTH_NAMES[int(m)]} {y}", v) for y,m,v in projections]
        max_v = max(v for _,v in all_data) or 1
        lines = []
        for lbl, val in all_data:
            filled = int((val/max_v)*32)
            lines.append(f"  {lbl[:10].ljust(10)}  {'█'*filled+'░'*(32-filled)}  ${val:>10,.0f}")
        chart = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
        chart.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(chart, text="\n".join(lines),
                     font=ctk.CTkFont(size=11, family="Courier New"),
                     justify="left", text_color=theme.TEXT).pack(padx=16, pady=12)

        # Resumen proyectado
        total_proj  = sum(v for _,_,v in projections)
        salaries    = self._total_salaries()
        tax_rate    = sum(float(t[2]) for t in api.get_active_taxes())
        proj_tax    = total_proj * tax_rate/100 if tax_rate else 0
        proj_sal    = salaries * months_ahead
        proj_net    = total_proj - proj_tax - proj_sal

        self._sec_title(p, "Resumen financiero proyectado")
        sg = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
        sg.pack(fill="x", pady=(0, 12))
        sgr = ctk.CTkFrame(sg, fg_color="transparent")
        sgr.pack(fill="x", padx=20, pady=16)
        for col, (lbl, val, color) in enumerate([
            (f"Ingreso proyectado ({months_ahead}m)", f"${total_proj:,.0f}", theme.C_GREEN),
            ("Impuestos estimados",                   f"${proj_tax:,.0f}",   theme.C_ORANGE),
            (f"Salarios ({months_ahead}m)",           f"${proj_sal:,.0f}",   theme.C_RED),
            ("Renta neta proyectada",                 f"${proj_net:,.0f}",   theme.C_GREEN if proj_net >= 0 else theme.C_RED),
        ]):
            sgr.columnconfigure(col, weight=1)
            ctk.CTkLabel(sgr, text=lbl, text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=10)).grid(row=0, column=col, padx=8)
            ctk.CTkLabel(sgr, text=val, text_color=color,
                         font=ctk.CTkFont(size=15, weight="bold")).grid(row=1, column=col, padx=8, pady=(2,8))

    # ── Pestaña Costos ─────────────────────────────────────
    def _build_costs_tab(self, parent):
        self._cost_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._cost_scroll.pack(fill="both", expand=True)

    def _refresh_costs(self):
        for w in self._cost_scroll.winfo_children():
            w.destroy()
        p = self._cost_scroll
        s        = api.get_sells_summary()
        rev      = s["month_revenue"]; taxes = api.get_active_taxes()
        total_tax_pct = sum(float(t[2]) for t in taxes)
        tax_amt  = rev * total_tax_pct/100 if total_tax_pct else s["month_tax"]
        salaries = self._total_salaries()
        inv_val  = api.get_inventory_value()
        net      = rev - tax_amt - salaries
        margin   = (net/rev*100) if rev > 0 else 0

        self._sec_title(p, "Desglose de ingresos — mes actual")
        tf, tree = W.make_tree(p, ["Componente","Monto","% del ingreso"], [220,200,160])
        tree.tag_configure("tax",    foreground=theme.C_ORANGE)
        tree.tag_configure("salary", foreground=theme.C_RED)
        tree.tag_configure("net",    foreground=theme.C_GREEN)
        tree.tag_configure("total",  foreground=theme.C_BLUE)

        components = []
        if taxes:
            for _, t_name, t_pct, _ in taxes:
                components.append((f"🧾 {t_name} ({float(t_pct):.1f}%)", rev*float(t_pct)/100, "tax"))
        else:
            components.append(("🧾 Impuestos", tax_amt, "tax"))
        components.append(("👥 Salarios", salaries, "salary"))
        components.append(("💰 Renta neta", net, "net"))
        for lbl, amt, tag in components:
            pct = (amt/rev*100) if rev > 0 else 0
            tree.insert("","end", values=(lbl, f"${amt:,.2f}", f"{pct:.1f}%"), tags=(tag,))
        tree.insert("","end", values=("📊 INGRESO TOTAL", f"${rev:,.2f}", "100%"), tags=("total",))
        tf.pack(fill="x", pady=(0, 10))

        m_color = theme.C_GREEN if margin >= 30 else (theme.C_ORANGE if margin >= 10 else theme.C_RED)
        ctk.CTkLabel(p, text=f"Margen neto estimado: {margin:.1f}%",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=m_color).pack(
            anchor="w", pady=(0, 10))

        self._sec_title(p, "Inventario")
        low = api.get_low_stock_products()
        ig = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
        ig.pack(fill="x", pady=(0, 10))
        igr = ctk.CTkFrame(ig, fg_color="transparent"); igr.pack(fill="x", padx=20, pady=16)
        for col, (lbl, val, color) in enumerate([
            ("Valor del inventario", f"${inv_val:,.0f}", theme.C_BLUE),
            ("Stock bajo",           str(len(low)),       theme.C_RED if low else theme.C_GREEN),
            ("Ventas este mes",      str(s["month_count"]), theme.C_PURPLE),
        ]):
            igr.columnconfigure(col, weight=1)
            ctk.CTkLabel(igr, text=lbl, text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).grid(row=0,column=col,padx=12)
            ctk.CTkLabel(igr, text=val, text_color=color, font=ctk.CTkFont(size=16, weight="bold")).grid(row=1,column=col,padx=12,pady=(2,8))

        top = api.get_sales_by_product()
        if top:
            self._sec_title(p, "Top 10 productos más vendidos")
            tf2, tree2 = W.make_tree(p, ["Producto","Unidades","Ingresos"],
                                     [260,160,180], height=min(10, len(top)))
            for prod, units, revenue in top:
                tree2.insert("","end", values=(prod or "—", int(units or 0), f"${float(revenue or 0):,.2f}"))
            tf2.pack(fill="x", pady=(0, 10))

    # ── Pestaña Empleados ──────────────────────────────────
    def _build_employees_tab(self, parent):
        self._emp_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._emp_scroll.pack(fill="both", expand=True)

    def _refresh_employees(self):
        for w in self._emp_scroll.winfo_children():
            w.destroy()
        p   = self._emp_scroll
        can = self.perms.get("gestionar_usuarios", False)

        hdr = ctk.CTkFrame(p, fg_color="transparent"); hdr.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr, text="Nómina de empleados",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        if can:
            ctk.CTkButton(hdr, text="💾  Guardar salarios", width=160, height=34,
                          fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                          command=self._save_salaries).pack(side="right")
        if not can:
            ctk.CTkLabel(p, text="🔒  Solo con permiso 'Gestionar usuarios' podés editar salarios.",
                         text_color=theme.C_ORANGE, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 8))

        users = api.get_all_users_with_salary()
        cols  = ["Usuario","Nombre","Rol","Estado","Salario ($)"]
        widths = [130, 190, 130, 90, 150]
        tf, tree = W.make_tree(p, cols, widths, height=min(10, len(users)))
        tree.tag_configure("active",   foreground=theme.C_GREEN)
        tree.tag_configure("inactive", foreground=theme.TEXT_DIM[1])

        total_a = total_all = 0.0
        self._salary_entries = {}
        for (id_u, uname, role, fname, active, created, id_r, salary) in users:
            sal = float(salary or 0); total_all += sal
            if active: total_a += sal
            tag = "active" if active else "inactive"
            tree.insert("","end", iid=str(id_u), values=(
                uname, fname or "—", role or "—",
                "✅ Activo" if active else "❌ Inactivo", f"${sal:,.2f}"), tags=(tag,))
        tf.pack(fill="x", pady=(0, 10))

        if can:
            self._sec_title(p, "Editar salarios")
            ef = ctk.CTkScrollableFrame(p, fg_color=theme.CARD2, corner_radius=12, height=220)
            ef.pack(fill="x", pady=(0, 10))
            for (id_u, uname, role, fname, active, *_, salary) in users:
                row = ctk.CTkFrame(ef, fg_color="transparent"); row.pack(fill="x", padx=12, pady=4)
                color = theme.TEXT if active else theme.TEXT_DIM
                ctk.CTkLabel(row, text=f"{uname}  ({fname or role or ''})",
                             width=280, anchor="w", text_color=color).pack(side="left")
                e = ctk.CTkEntry(row, width=130, justify="center", placeholder_text="0.00")
                e.insert(0, f"{float(salary or 0):.2f}")
                if not active: e.configure(state="disabled")
                e.pack(side="left", padx=8)
                ctk.CTkLabel(row, text="$/mes", text_color=theme.TEXT_DIM).pack(side="left")
                self._salary_entries[id_u] = e

        self._sec_title(p, "Resumen de nómina")
        sg = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
        sg.pack(fill="x", pady=(0, 12))
        sgr = ctk.CTkFrame(sg, fg_color="transparent"); sgr.pack(fill="x", padx=20, pady=16)
        for col, (lbl, val, color) in enumerate([
            ("Activos (mensual)", f"${total_a:,.2f}",      theme.C_GREEN),
            ("Total (mensual)",   f"${total_all:,.2f}",    theme.C_ORANGE),
            ("Total (anual)",     f"${total_all*12:,.2f}", theme.C_RED),
        ]):
            sgr.columnconfigure(col, weight=1)
            ctk.CTkLabel(sgr, text=lbl, text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).grid(row=0,column=col,padx=12)
            ctk.CTkLabel(sgr, text=val, text_color=color, font=ctk.CTkFont(size=16, weight="bold")).grid(row=1,column=col,padx=12,pady=(2,8))

    def _save_salaries(self):
        saved = 0
        for id_u, entry in self._salary_entries.items():
            try:
                sal = float(entry.get()); assert sal >= 0
                api.update_user_salary(id_u, sal); saved += 1
            except Exception:
                messagebox.showerror("Error", f"Salario inválido para ID {id_u}."); return
        messagebox.showinfo("Guardado", f"✅ {saved} salarios actualizados.")
        self._refresh_employees(); self._refresh_kpis()

    # ── Pestaña Salud ──────────────────────────────────────
    def _build_health_tab(self, parent):
        self._health_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._health_scroll.pack(fill="both", expand=True)

    def _refresh_health(self):
        for w in self._health_scroll.winfo_children():
            w.destroy()
        p        = self._health_scroll
        s        = api.get_sells_summary()
        rev      = s["month_revenue"]; tax_amt = s["month_tax"]
        salaries = self._total_salaries(); low = api.get_low_stock_products()
        net      = rev - tax_amt - salaries
        margin   = (net/rev*100) if rev > 0 else 0
        tax_pct  = (tax_amt/rev*100) if rev > 0 else 0
        sal_pct  = (salaries/rev*100) if rev > 0 else 0

        self._sec_title(p, "Semáforo financiero")
        for ind_name, val, unit, thresholds, inverted in [
            ("Margen neto",              margin,      "%",         [(30,"🟢 Excelente",theme.C_GREEN,"Margen >30%. Excelente."),(15,"🟡 Aceptable",theme.C_ORANGE,"Margen 15-30%."),(0,"🔴 Bajo",theme.C_RED,"Margen <15%.")], False),
            ("Carga impositiva",         tax_pct,     "%",         [(0,"🟢 Normal",theme.C_GREEN,"Carga normal."),(20,"🟡 Alta",theme.C_ORANGE,">20% del ingreso."),(35,"🔴 Muy alta",theme.C_RED,">35%. Consultá contador.")], True),
            ("Carga salarial",           sal_pct,     "%",         [(0,"🟢 Normal",theme.C_GREEN,"Parámetros saludables."),(40,"🟡 Elevada",theme.C_ORANGE,">40% del ingreso."),(60,"🔴 Crítica",theme.C_RED,">60% del ingreso.")], True),
            ("Productos stock bajo",     len(low),    "productos", [(0,"🟢 OK",theme.C_GREEN,"Sin alertas."),(3,"🟡 Atención",theme.C_ORANGE,f"{len(low)} productos cerca de agotarse."),(10,"🔴 Crítico",theme.C_RED,f"{len(low)} productos. ¡Reabastecer!")], True),
        ]:
            label_text, color, desc = thresholds[0][1], thresholds[0][2], thresholds[0][3]
            thr = reversed(thresholds) if inverted else reversed(thresholds)
            if inverted:
                for thold, lbl, clr, d in reversed(thresholds):
                    if val >= thold: label_text=lbl; color=clr; desc=d; break
            else:
                for thold, lbl, clr, d in reversed(thresholds):
                    if val >= thold: label_text=lbl; color=clr; desc=d; break

            card = ctk.CTkFrame(p, fg_color=theme.CARD2, corner_radius=12)
            card.pack(fill="x", pady=(0, 8))
            inner = ctk.CTkFrame(card, fg_color="transparent"); inner.pack(fill="x", padx=18, pady=14)
            ctk.CTkLabel(inner, text=ind_name, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            ctk.CTkLabel(inner, text=f"{val:.1f} {unit}",
                         font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=color).pack(side="left", padx=16)
            ctk.CTkLabel(inner, text=f"{label_text}  —  {desc}",
                         font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM,
                         wraplength=460, justify="left").pack(side="left")

        self._sec_title(p, "💡 Recomendaciones automáticas")
        recs = []
        if margin < 15:   recs.append(("🔴","Margen bajo","Revisá precios de venta o reducí costos operativos."))
        if tax_pct > 30:  recs.append(("🟡","Alta carga impositiva","Consultá con un contador sobre tu estructura impositiva."))
        if sal_pct > 50:  recs.append(("🟡","Nómina elevada","Los salarios superan el 50% del ingreso."))
        if len(low) >= 3: recs.append(("🔴",f"{len(low)} productos con stock bajo","Contactá proveedores para reabastecer."))
        if not recs:      recs.append(("🟢","¡Todo en orden!","No se detectaron alertas críticas. Seguí así."))
        for icon, title, desc in recs:
            rc = ctk.CTkFrame(p, fg_color=theme.CARD, corner_radius=10)
            rc.pack(fill="x", pady=(0, 6))
            ri = ctk.CTkFrame(rc, fg_color="transparent"); ri.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(ri, text=f"{icon}  {title}",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(ri, text=desc, font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM,
                         wraplength=600, justify="left").pack(anchor="w", pady=(4, 0))

    # ── Helpers ────────────────────────────────────────────
    def _sec_title(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(12, 4))
        ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=(0, 6))

    def _refresh_treeview_style(self):
        pass

    def on_show(self):
        self._refresh_kpis()
        self._refresh_real()
        self._refresh_forecast()
        self._refresh_costs()
        self._refresh_employees()
        self._refresh_health()
