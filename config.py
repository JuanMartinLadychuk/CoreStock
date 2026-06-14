"""config.py – Configuración del sistema con tema integrado."""
import customtkinter as ctk
from tkinter import ttk, messagebox
import smtplib, ssl
import api, theme
import widgets as W


def _get_categories():
    try:
        cats = api.get_all_categories()
        return cats if cats else ["Sin Categoría"]
    except Exception:
        return ["Sin Categoría"]


class ConfigFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._app  = app
        self._build_ui()

    def _build_ui(self):
        if not self.perms.get("ver_configuracion"):
            ctk.CTkLabel(self, text="Sin permiso para ver la configuración.",
                         text_color=theme.C_RED, font=ctk.CTkFont(size=15)).pack(expand=True)
            return

        W.page_header(self, "Configuracion")

        tab = ctk.CTkTabview(self, anchor="w")
        tab.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self._build_negocio(tab.add("🏪 Negocio"))      # ← PRIMERA — nueva
        self._build_pricing(tab.add("Margen Global"))
        self._build_category_margins(tab.add("Por Categoria"))
        self._build_tax(tab.add("Impuestos"))
        self._build_smtp(tab.add("Email SMTP"))
        self._build_company(tab.add("Empresa"))
        self._build_pos_payments(tab.add("POS / Pagos"))
        self._build_afip(tab.add("AFIP"))
        self._build_theme(tab.add("Apariencia"))

    # ── Helpers UI ─────────────────────────────────────────
    @staticmethod
    def _card(parent, title: str):
        sc = ctk.CTkScrollableFrame(parent, fg_color=theme.CARD, corner_radius=12)
        sc.pack(fill="both", expand=True, pady=4)
        ctk.CTkLabel(sc, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=theme.TEXT).pack(pady=(16, 6), padx=18, anchor="w")
        ctk.CTkFrame(sc, height=1, fg_color=theme.SEP).pack(fill="x", padx=16, pady=(0, 12))
        inner = ctk.CTkFrame(sc, fg_color="transparent")
        inner.pack(fill="x", padx=18)
        return inner

    @staticmethod
    def _save_btn(parent, cmd, text="Guardar cambios"):
        ctk.CTkButton(parent, text=text, height=38, width=200,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=cmd).pack(anchor="w", pady=(14, 16))

    @staticmethod
    def _sep(parent):
        ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=10)

    def _lbl(self, parent, text):
        ctk.CTkLabel(parent, text=text, anchor="w", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x", pady=(6, 0))

    # ════════════════════════════════════════════════════════
    #  TAB 0 – TIPO DE NEGOCIO
    # ════════════════════════════════════════════════════════
    def _build_negocio(self, parent):
        card = self._card(parent, "Tipo de negocio")

        ctk.CTkLabel(card,
                     text="Elegí cómo opera tu comercio. Esto habilita o deshabilita módulos "
                          "del menú lateral para que solo veas lo que necesitás.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12),
                     wraplength=700, justify="left").pack(anchor="w", pady=(0, 18))

        # Tarjetas de tipo de negocio
        opts_f = ctk.CTkFrame(card, fg_color="transparent")
        opts_f.pack(fill="x", pady=(0, 20))
        opts_f.columnconfigure((0, 1, 2), weight=1)

        self._btype_var = ctk.StringVar(value=api.get_business_type())

        OPTIONS = [
            ("fisico",    "🏪", "Local Físico",
             "POS, caja, inventario presencial.\nSin módulo de MercadoLibre.",
             "#1a56db"),
            ("ecommerce", "🌐", "E-commerce Puro",
             "Gestión de pedidos online y ML.\nSin POS ni caja.",
             "#7c3aed"),
            ("ambos",     "⚡", "Local + E-commerce",
             "Todos los módulos habilitados.\nOperación híbrida.",
             "#16a34a"),
        ]

        self._btype_cards: dict = {}
        for col, (key, icon, title, desc, color) in enumerate(OPTIONS):
            card_btn = ctk.CTkFrame(opts_f, corner_radius=14, cursor="hand2",
                                    border_width=2)
            card_btn.grid(row=0, column=col, sticky="nsew",
                          padx=(0 if col == 0 else 8, 0), pady=4)

            inner = ctk.CTkFrame(card_btn, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=16)

            ctk.CTkLabel(inner, text=icon,
                         font=ctk.CTkFont(size=32)).pack()
            ctk.CTkLabel(inner, text=title,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=theme.TEXT).pack(pady=(6, 2))
            ctk.CTkLabel(inner, text=desc,
                         font=ctk.CTkFont(size=10),
                         text_color=theme.TEXT_DIM,
                         justify="center").pack()

            rb = ctk.CTkRadioButton(inner, text="Seleccionar",
                                     variable=self._btype_var, value=key,
                                     fg_color=color,
                                     command=lambda k=key, c=color: self._on_btype_select(k, c))
            rb.pack(pady=(10, 0))
            self._btype_cards[key] = (card_btn, color)

        self._update_btype_card_styles()

        # Módulos afectados — info visual
        self._modules_info = ctk.CTkFrame(card, fg_color=theme.CARD2, corner_radius=10)
        self._modules_info.pack(fill="x", pady=(0, 12))
        self._render_modules_info()

        # Banner de aviso
        warn_f = ctk.CTkFrame(card, fg_color=("#fef3c7", "#422006"),
                               corner_radius=8, border_width=1,
                               border_color=("#fde68a", "#92400e"))
        warn_f.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(warn_f,
                     text="⚠  El cambio aplica al reiniciar la sesión (Cerrar sesión → Ingresar).",
                     text_color=("#92400e", "#fde68a"),
                     font=ctk.CTkFont(size=11)).pack(padx=14, pady=8)

        self._save_btn(card, self._save_negocio, text="Guardar tipo de negocio")

    def _on_btype_select(self, key: str, color: str):
        self._update_btype_card_styles()
        self._render_modules_info()

    def _update_btype_card_styles(self):
        selected = self._btype_var.get()
        for key, (card_w, color) in self._btype_cards.items():
            if key == selected:
                card_w.configure(fg_color=theme.CARD2, border_color=color)
            else:
                card_w.configure(fg_color="transparent", border_color=theme.SEP)

    def _render_modules_info(self):
        for w in self._modules_info.winfo_children():
            w.destroy()
        btype   = self._btype_var.get()
        enabled = api.BUSINESS_MODULE_MAP.get(btype, set())
        all_keys = {r[0]: r[4] for r in [
            ("dashboard","","","","Dashboard",""), ("pos","","","","POS / Caja",""),
            ("inventory","","","","Inventario",""), ("sales","","","","Ventas",""),
            ("suppliers","","","","Proveedores",""), ("analytics","","","","Rendimiento",""),
            ("mercadolibre","","","","MercadoLibre",""), ("categories","","","","Categorías",""),
            ("emails","","","","Emails",""),
        ]}

        hdr = ctk.CTkFrame(self._modules_info, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(hdr, text="Módulos habilitados con esta configuración:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(side="left")

        chips_f = ctk.CTkFrame(self._modules_info, fg_color="transparent")
        chips_f.pack(fill="x", padx=14, pady=(0, 10))

        MODULE_LABELS = {
            "dashboard":    "Dashboard",    "pos":         "POS / Caja",
            "inventory":    "Inventario",   "sales":       "Ventas",
            "suppliers":    "Proveedores",  "analytics":   "Rendimiento",
            "mercadolibre": "MercadoLibre", "categories":  "Categorías",
            "emails":       "Emails",       "config":      "Config",
            "users":        "Usuarios",     "roles":       "Roles",
            "about":        "Acerca de",
        }
        check_keys = ["dashboard","pos","inventory","sales","suppliers",
                      "analytics","mercadolibre","emails"]
        for key in check_keys:
            is_on = key in enabled
            chip = ctk.CTkFrame(chips_f, corner_radius=6,
                                fg_color=("#dcfce7","#14532d") if is_on
                                         else ("#fee2e2","#450a0a"))
            chip.pack(side="left", padx=(0, 6), pady=2)
            ctk.CTkLabel(chip,
                         text=f"{'✓' if is_on else '✗'} {MODULE_LABELS.get(key, key)}",
                         font=ctk.CTkFont(size=10),
                         text_color=("#15803d","#4ade80") if is_on
                                     else ("#b91c1c","#f87171")).pack(padx=8, pady=3)

    def _save_negocio(self):
        btype = self._btype_var.get()
        api.set_business_type(btype)
        self._update_btype_card_styles()
        label = api.BUSINESS_TYPES.get(btype, btype)
        # Notificar a main.py para recargar el sidebar si está disponible
        if self._app and hasattr(self._app, "reload_nav"):
            self._app.reload_nav()
        messagebox.showinfo(
            "Tipo de negocio guardado",
            f"Modo: {label}\n\n"
            "El menú lateral se actualizó.\n"
            "Si los cambios no se reflejan, cerrá y volvé a iniciar sesión.")

    def _load_negocio(self):
        if hasattr(self, "_btype_var"):
            self._btype_var.set(api.get_business_type())
            self._update_btype_card_styles()
            self._render_modules_info()

    # ════════════════════════════════════════════════════════
    #  TAB 1 – MARGEN GLOBAL
    # ════════════════════════════════════════════════════════
    def _build_pricing(self, parent):
        card = self._card(parent, "Margen global de la jerarquía (Nivel 3)")
        ctk.CTkLabel(card, text="Se aplica cuando el producto y su categoría no tienen margen propio.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12),
                     wraplength=700, justify="left").pack(anchor="w", pady=(0, 12))

        # Diagrama jerarquía
        hier = ctk.CTkFrame(card, fg_color=theme.CARD2, corner_radius=10)
        hier.pack(fill="x", pady=(0, 14))
        hi = ctk.CTkFrame(hier, fg_color="transparent"); hi.pack(fill="x", padx=14, pady=10)
        hi.columnconfigure((0,1,2), weight=1)
        for i, (nivel, desc, color) in enumerate([
            ("Nivel 1", "Margen del producto\n(prioridad máxima)", theme.C_ORANGE),
            ("Nivel 2", "Margen de categoría\n(herencia)", theme.C_BLUE),
            ("Nivel 3", "Margen global\n(base)", theme.C_GREEN),
        ]):
            ctk.CTkLabel(hi, text=nivel, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).grid(row=0, column=i, padx=6)
            ctk.CTkLabel(hi, text=desc, font=ctk.CTkFont(size=10), text_color=theme.TEXT_DIM,
                         justify="center").grid(row=1, column=i, padx=6, pady=4)

        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row, text="Margen global (%):",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        self.markup_e = ctk.CTkEntry(row, width=80, justify="center",
                                      font=ctk.CTkFont(size=17, weight="bold"))
        self.markup_e.pack(side="left", padx=12)
        self.markup_slider = ctk.CTkSlider(row, from_=1, to=500, width=300,
                                            command=self._on_markup_slider)
        self.markup_slider.pack(side="left", padx=8)
        self.markup_e.bind("<FocusOut>", self._on_markup_entry)
        self.markup_e.bind("<Return>",   self._on_markup_entry)

        self._sep(card)
        ctk.CTkLabel(card, text="Calculadora de precio",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w")
        cr = ctk.CTkFrame(card, fg_color="transparent"); cr.pack(fill="x", pady=8)
        ctk.CTkLabel(cr, text="Costo: $", font=ctk.CTkFont(size=12)).pack(side="left")
        self.calc_cost = ctk.CTkEntry(cr, width=100, placeholder_text="1000", height=34)
        self.calc_cost.pack(side="left", padx=6)
        self.calc_cost.bind("<KeyRelease>", self._update_preview)
        self.calc_result = ctk.CTkLabel(cr, text="Precio: $—",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=theme.C_GREEN)
        self.calc_result.pack(side="left", padx=12)
        self.markup_gain_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12),
                                             text_color=theme.C_ORANGE)
        self.markup_gain_lbl.pack(anchor="w")
        self._save_btn(card, self._save_pricing)

    def _load_pricing(self):
        val = api.get_setting("markup_percent", "20")
        self.markup_e.delete(0, "end"); self.markup_e.insert(0, val)
        try: self.markup_slider.set(float(val))
        except Exception: self.markup_slider.set(20)

    def _on_markup_slider(self, val):
        v = round(float(val), 1)
        self.markup_e.delete(0, "end"); self.markup_e.insert(0, str(v))
        self._update_preview()

    def _on_markup_entry(self, _=None):
        try:
            v = max(1, min(500, float(self.markup_e.get())))
            self.markup_slider.set(v)
        except ValueError: pass
        self._update_preview()

    def _update_preview(self, _=None):
        try:
            cost = float(self.calc_cost.get()); markup = float(self.markup_e.get())
            sell = round(cost*(1+markup/100), 2)
            self.calc_result.configure(text=f"Precio: ${sell:,.2f}")
            self.markup_gain_lbl.configure(text=f"Ganancia: ${sell-cost:,.2f} ({markup}%)")
        except ValueError: pass

    def _save_pricing(self):
        try: val = float(self.markup_e.get()); assert 1 <= val <= 500
        except Exception: messagebox.showerror("Error", "El margen debe estar entre 1 y 500."); return
        api.set_setting("markup_percent", str(val))
        messagebox.showinfo("Guardado", f"Margen global actualizado a {val}%.")

    # ════════════════════════════════════════════════════════
    #  TAB 2 – MÁRGENES POR CATEGORÍA
    # ════════════════════════════════════════════════════════
    def _build_category_margins(self, parent):
        card = self._card(parent, "Márgenes por categoría (Nivel 2)")
        ctk.CTkLabel(card, text="Si el producto no tiene margen propio, se usa el de su categoría.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12),
                     wraplength=700, justify="left").pack(anchor="w", pady=(0, 12))
        self._cat_entries: dict = {}
        self._cat_sliders: dict = {}
        self._cat_preview: dict = {}
        self._cat_grid   = ctk.CTkFrame(card, fg_color="transparent")
        self._cat_grid.pack(fill="x")
        self._save_btn(card, self._save_category_margins)

    def _load_category_margins(self):
        for w in self._cat_grid.winfo_children():
            w.destroy()
        self._cat_entries.clear(); self._cat_sliders.clear(); self._cat_preview.clear()
        cats       = _get_categories()
        cat_margins = api.get_category_margins()
        global_m   = float(api.get_setting("markup_percent", "20"))
        for cat in cats:
            current = cat_margins.get(cat, global_m)
            rf = ctk.CTkFrame(self._cat_grid, fg_color=theme.CARD2, corner_radius=10)
            rf.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(rf, fg_color="transparent"); inner.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(inner, text=f"{cat}", font=ctk.CTkFont(size=13, weight="bold"),
                         width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(inner, width=70, justify="center",
                              font=ctk.CTkFont(size=14, weight="bold"))
            e.insert(0, str(current)); e.pack(side="left", padx=8)
            sl = ctk.CTkSlider(inner, from_=1, to=500, width=250)
            sl.set(current); sl.pack(side="left", padx=6)
            pv = ctk.CTkLabel(inner, text="", text_color=theme.C_GREEN,
                               font=ctk.CTkFont(size=11), width=160)
            pv.pack(side="left", padx=6)
            self._cat_entries[cat] = e; self._cat_sliders[cat] = sl; self._cat_preview[cat] = pv
            sl.configure(command=lambda v, c=cat: self._upd_cat(v, c))
            e.bind("<KeyRelease>", lambda ev, c=cat: self._upd_cat_slider(ev, c))
            self._update_cat_preview(cat)

    def _upd_cat(self, val, cat):
        v = round(float(val), 1)
        self._cat_entries[cat].delete(0, "end"); self._cat_entries[cat].insert(0, str(v))
        self._update_cat_preview(cat)

    def _upd_cat_slider(self, _ev, cat):
        try:
            v = max(1, min(500, float(self._cat_entries[cat].get())))
            self._cat_sliders[cat].set(v)
        except ValueError: pass
        self._update_cat_preview(cat)

    def _update_cat_preview(self, cat):
        try:
            m = float(self._cat_entries[cat].get())
            sell = round(1000*(1+m/100), 2); gain = round(sell-1000, 2)
            self._cat_preview[cat].configure(text=f"$1000 → ${sell:,.0f} (gan. ${gain:,.0f})")
        except ValueError: self._cat_preview[cat].configure(text="")

    def _save_category_margins(self):
        for cat, entry in self._cat_entries.items():
            try: m = float(entry.get()); assert 1 <= m <= 500; api.set_category_margin(cat, m)
            except Exception: messagebox.showerror("Error", f"Margen inválido para '{cat}'."); return
        messagebox.showinfo("Guardado", "Márgenes por categoría actualizados.")

    # ════════════════════════════════════════════════════════
    #  TAB 3 – IMPUESTOS
    # ════════════════════════════════════════════════════════
    def _build_tax(self, parent):
        can_edit = self.perms.get("editar_impuestos", False)
        top = ctk.CTkFrame(parent, fg_color="transparent"); top.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(top, text="Gestión de Tributos",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        if can_edit:
            ctk.CTkButton(top, text="＋ Nuevo tributo", width=150, height=34,
                          fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                          command=self._add_tax_dialog).pack(side="right")

        ctk.CTkLabel(parent, text="Cada tributo se aplica automáticamente al vender. La tasa queda"
                     "'fotografiada' en cada transacción para inmutabilidad histórica.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12),
                     wraplength=720, justify="left").pack(anchor="w", pady=(0, 10))
        if not can_edit:
            ctk.CTkLabel(parent, text="Solo lectura.", text_color=theme.C_ORANGE,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")

        tf, self._tax_tree = W.make_tree(parent,
            ["ID","Nombre","% Tasa","Modo","Estado"],
            [50,200,90,220,90], height=6)
        self._tax_tree.tag_configure("active",   foreground=theme.C_GREEN)
        self._tax_tree.tag_configure("inactive", foreground=theme.TEXT_DIM[1])
        tf.pack(fill="x", pady=(4, 8))

        if can_edit:
            br = ctk.CTkFrame(parent, fg_color="transparent"); br.pack(fill="x", pady=(0, 8))
            for text, color, hover, cmd in [
                ("Editar", theme.BTN_BLUE,   theme.BTN_BLUEH,   self._edit_tax_dialog),
                ("⏸ Activar/Desactivar", theme.BTN_ORANGE, theme.BTN_ORANGEH, self._toggle_tax),
                ("Eliminar", theme.BTN_RED,  theme.BTN_REDH,    self._delete_tax),
            ]:
                ctk.CTkButton(br, text=text, width=160, height=32, fg_color=color, hover_color=hover,
                              command=cmd).pack(side="left", padx=(0, 6))

        ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=8)
        ctk.CTkLabel(parent, text="Vista previa fiscal (base $1.000):",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w")
        self._tax_preview_lbl = ctk.CTkLabel(parent, text="—",
                                              font=ctk.CTkFont(size=11, family="Courier New"),
                                              justify="left")
        self._tax_preview_lbl.pack(anchor="w", pady=(4, 10))

        ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=4)
        ctk.CTkLabel(parent, text="Historial de cambios (auditoría)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(6, 4))
        af, self._audit_tree = W.make_tree(parent,
            ["ID","Tributo","% Ant.","% Nuevo","Modo","Acción","Usuario","Fecha"],
            [40,160,80,80,100,110,120,170], height=5)
        af.pack(fill="both", expand=True, pady=(0, 4))

    def _load_tax_table(self):
        self._tax_tree.delete(*self._tax_tree.get_children())
        for id_, name, pct, is_inc, active in api.get_all_taxes():
            mode = "Incluido en precio" if is_inc else "Se suma al precio"
            tag  = "active" if active else "inactive"
            self._tax_tree.insert("","end", iid=str(id_),
                                  values=(id_, name, f"{float(pct):.2f}%", mode,
                                          "Activo" if active else "Inactivo"),
                                  tags=(tag,))

    def _load_audit_log(self):
        self._audit_tree.delete(*self._audit_tree.get_children())
        for row in api.get_tax_audit_log(limit=100):
            id_log, t_name, old_p, new_p, is_inc, action, username, changed_at = row
            mode = ("Incluido" if is_inc else "Sumado") if is_inc is not None else "—"
            self._audit_tree.insert("","end", values=(
                id_log, t_name or "—",
                f"{float(old_p):.2f}%" if old_p is not None else "—",
                f"{float(new_p):.2f}%" if new_p is not None else "—",
                mode, action, username, str(changed_at)[:19] if changed_at else "—"))

    def _refresh_tax_preview(self):
        taxes = api.get_active_taxes()
        if not taxes: self._tax_preview_lbl.configure(text="Sin tributos activos."); return
        base = 1000.0
        incl_rate = sum(float(t[2]) for t in taxes if t[3])
        net = round(base/(1+incl_rate/100), 2) if incl_rate else base
        lines = [f"Base: ${base:>9.2f}"]; total_tax = 0.0
        for _, name, pct, is_inc in taxes:
            pct = float(pct); amt = round(net*pct/100, 2); total_tax += amt
            lines.append(f"{name} {pct:.0f}% {'(incl.)' if is_inc else '(sumado)'}: ${amt:>9.2f}")
        lines.append(f"{'─'*36}")
        lines.append(f"Neto sin impuestos: ${net:>9.2f}")
        lines.append(f"Total impuestos: ${total_tax:>9.2f}")
        self._tax_preview_lbl.configure(text="\n".join(lines))

    def _get_selected_tax_id(self):
        sel = self._tax_tree.selection()
        return int(sel[0]) if sel else None

    def _add_tax_dialog(self):
        TaxDialog(self, title="Nuevo Tributo", user_id=self.user["id"],
                  on_save=lambda: (self._load_tax_table(), self._load_audit_log(), self._refresh_tax_preview()))

    def _edit_tax_dialog(self):
        id_tax = self._get_selected_tax_id()
        if not id_tax: messagebox.showwarning("Sin selección", "Seleccioná un tributo."); return
        tax = api.get_tax_by_id(id_tax)
        if tax:
            TaxDialog(self, title="Editar Tributo", user_id=self.user["id"], data=tax,
                      on_save=lambda: (self._load_tax_table(), self._load_audit_log(), self._refresh_tax_preview()))

    def _toggle_tax(self):
        id_tax = self._get_selected_tax_id()
        if not id_tax: messagebox.showwarning("Sin selección", "Seleccioná un tributo."); return
        tax = api.get_tax_by_id(id_tax)
        if not tax: return
        new_state = not tax["active"]
        if messagebox.askyesno("Confirmar", f"¿{'Activar' if new_state else 'Desactivar'} '{tax['name']}'?"):
            api.toggle_tax_active(id_tax, new_state, self.user["id"])
            self._load_tax_table(); self._load_audit_log(); self._refresh_tax_preview()

    def _delete_tax(self):
        id_tax = self._get_selected_tax_id()
        if not id_tax: messagebox.showwarning("Sin selección", "Seleccioná un tributo."); return
        tax = api.get_tax_by_id(id_tax)
        if not tax: return
        if messagebox.askyesno("Eliminar", f"¿Eliminar '{tax['name']}'?"):
            api.delete_tax(id_tax, self.user["id"])
            self._load_tax_table(); self._load_audit_log(); self._refresh_tax_preview()

    # ════════════════════════════════════════════════════════
    #  TAB 4 – SMTP
    # ════════════════════════════════════════════════════════
    def _build_smtp(self, parent):
        card = self._card(parent, "Servidor de correo (SMTP)")
        ctk.CTkLabel(card, text="Necesario para enviar emails a proveedores desde la app.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 10))

        pr = ctk.CTkFrame(card, fg_color="transparent"); pr.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(pr, text="Presets:", text_color=theme.TEXT_DIM).pack(side="left")
        for name, host, port in [("Gmail","smtp.gmail.com",587),("Outlook","smtp.outlook.com",587),("Yahoo","smtp.mail.yahoo.com",587)]:
            ctk.CTkButton(pr, text=name, width=90, height=28, fg_color=theme.CARD2,
                          hover_color=theme.ACCENT,
                          command=lambda h=host, p=port: self._apply_smtp_preset(h, p)).pack(side="left", padx=4)

        grid = ctk.CTkFrame(card, fg_color="transparent"); grid.pack(fill="x"); grid.columnconfigure(1, weight=1)
        self._smtp_e: dict = {}
        for i, (lbl, key, ph, pw) in enumerate([
            ("Servidor SMTP:", "smtp_host",      "smtp.gmail.com", False),
            ("Puerto:",        "smtp_port",      "587",            False),
            ("Usuario/Email:", "smtp_user",      "correo@gmail.com", False),
            ("Contraseña:",    "smtp_password",  "", True),
            ("Nombre emisor:", "smtp_from_name", "CoreStack Pro", False),
        ]):
            ctk.CTkLabel(grid, text=lbl, anchor="w").grid(row=i, column=0, sticky="w", padx=(0, 14), pady=7)
            e = ctk.CTkEntry(grid, placeholder_text=ph, show="•" if pw else "", height=34)
            e.grid(row=i, column=1, sticky="ew", pady=7)
            self._smtp_e[key] = e

        tr = ctk.CTkFrame(card, fg_color="transparent"); tr.pack(fill="x", pady=(10, 4))
        ctk.CTkButton(tr, text="Probar conexión", width=160, fg_color=theme.BTN_ORANGE,
                      hover_color=theme.BTN_ORANGEH, command=self._test_smtp).pack(side="left")
        self.smtp_status = ctk.CTkLabel(tr, text="", font=ctk.CTkFont(size=12))
        self.smtp_status.pack(side="left", padx=12)
        ctk.CTkLabel(card, text="ℹ Gmail: activá la verificación en 2 pasos y generá una App Password.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(6, 0))
        self._save_btn(card, self._save_smtp)

    def _load_smtp(self):
        try:
            s = api.get_all_settings()
            for key, e in self._smtp_e.items():
                e.delete(0, "end"); e.insert(0, s.get(key, ""))
        except Exception: pass

    def _apply_smtp_preset(self, host, port):
        self._smtp_e["smtp_host"].delete(0, "end"); self._smtp_e["smtp_host"].insert(0, host)
        self._smtp_e["smtp_port"].delete(0, "end"); self._smtp_e["smtp_port"].insert(0, str(port))

    def _test_smtp(self):
        host = self._smtp_e["smtp_host"].get().strip()
        user = self._smtp_e["smtp_user"].get().strip()
        pw   = self._smtp_e["smtp_password"].get()
        try: port = int(self._smtp_e["smtp_port"].get())
        except Exception: self.smtp_status.configure(text="Puerto inválido.", text_color=theme.C_RED); return
        self.smtp_status.configure(text="⏳ Conectando…", text_color=theme.TEXT_DIM); self.update()
        try:
            with smtplib.SMTP(host, port, timeout=8) as srv:
                srv.ehlo(); srv.starttls(context=ssl.create_default_context())
                if user and pw: srv.login(user, pw)
            self.smtp_status.configure(text="Conexión exitosa.", text_color=theme.C_GREEN)
        except Exception as e:
            self.smtp_status.configure(text=f"{e}", text_color=theme.C_RED)

    def _save_smtp(self):
        for key, e in self._smtp_e.items(): api.set_setting(key, e.get().strip())
        messagebox.showinfo("Guardado", "SMTP guardado.")

    # ════════════════════════════════════════════════════════
    #  TAB 5 – EMPRESA
    # ════════════════════════════════════════════════════════
    def _build_company(self, parent):
        card = self._card(parent, "Datos de la empresa")
        ctk.CTkLabel(card, text="Aparecen en PDFs y encabezados de emails.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 12))
        grid = ctk.CTkFrame(card, fg_color="transparent"); grid.pack(fill="x"); grid.columnconfigure(1, weight=1)
        self._company_e: dict = {}
        for i, (lbl, key) in enumerate([("Nombre:","company_name"),("Dirección:","company_address"),
                                          ("Teléfono:","company_phone"),("CUIT/CUIL:","company_cuit"),("Email:","company_email")]):
            ctk.CTkLabel(grid, text=lbl, anchor="w").grid(row=i, column=0, sticky="w", padx=(0,14), pady=8)
            e = ctk.CTkEntry(grid, height=34)
            e.grid(row=i, column=1, sticky="ew", pady=8)
            self._company_e[key] = e
        self._save_btn(card, self._save_company)

    def _load_company(self):
        try:
            s = api.get_all_settings()
            for key, e in self._company_e.items(): e.delete(0, "end"); e.insert(0, s.get(key, ""))
        except Exception: pass

    def _save_company(self):
        for key, e in self._company_e.items(): api.set_setting(key, e.get().strip())
        messagebox.showinfo("Guardado", "Datos de empresa actualizados.")

    # ════════════════════════════════════════════════════════
    #  TAB 6 – POS / PAGOS
    # ════════════════════════════════════════════════════════
    def _build_pos_payments(self, parent):
        card = self._card(parent, "Configuración del Terminal POS")

        ctk.CTkLabel(card, text="Lector de Barras", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.C_BLUE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(card, text="El lector USB es emulador de teclado. No requiere configuración adicional.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11), wraplength=700).pack(anchor="w", pady=(0, 8))
        beep_row = ctk.CTkFrame(card, fg_color="transparent"); beep_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(beep_row, text="Sonido de confirmación (beep):").pack(side="left")
        self._beep_var = ctk.StringVar(value=api.get_setting("pos_beep_enabled", "1"))
        ctk.CTkSwitch(beep_row, text="Activado", variable=self._beep_var, onvalue="1", offvalue="0",
                      command=lambda: api.set_setting("pos_beep_enabled", self._beep_var.get())).pack(side="left", padx=12)

        self._sep(card)
        ctk.CTkLabel(card, text="MercadoPago Point", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.C_BLUE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(card, text="1. Creá una app en developers.mercadopago.com\n"
                     "2. Obtené el Access Token de producción\n"
                     "3. Obtené el Device ID del dispositivo vinculado",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", pady=(0, 10))

        mp_mode_row = ctk.CTkFrame(card, fg_color="transparent"); mp_mode_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(mp_mode_row, text="Modo:").pack(side="left")
        self._mp_mode_var = ctk.StringVar(value=api.get_setting("mp_integration", "0"))
        ctk.CTkRadioButton(mp_mode_row, text="Manual", variable=self._mp_mode_var, value="0").pack(side="left", padx=12)
        ctk.CTkRadioButton(mp_mode_row, text="API Point (automático)", variable=self._mp_mode_var, value="1").pack(side="left")

        grid = ctk.CTkFrame(card, fg_color="transparent"); grid.pack(fill="x"); grid.columnconfigure(1, weight=1)
        self._mp_entries: dict = {}
        for i, (lbl, key, ph, secret) in enumerate([
            ("Access Token:", "mp_access_token", "TEST-xxxx... o APP_USR-xxxx...", True),
            ("Device ID:",    "mp_device_id",    "PAX_A910__SMARTPOS...", False),
        ]):
            ctk.CTkLabel(grid, text=lbl, anchor="w").grid(row=i, column=0, sticky="w", padx=(0,14), pady=7)
            e = ctk.CTkEntry(grid, placeholder_text=ph, show="•" if secret else "", height=34)
            e.grid(row=i, column=1, sticky="ew", pady=7)
            val = api.get_setting(key, "")
            if val: e.insert(0, val)
            self._mp_entries[key] = e

        self._sep(card)
        ctk.CTkLabel(card, text="Sesión de Caja", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.C_BLUE).pack(anchor="w", pady=(0, 4))
        cash_row = ctk.CTkFrame(card, fg_color="transparent"); cash_row.pack(fill="x")
        ctk.CTkLabel(cash_row, text="Requerir apertura de caja antes de vender:").pack(side="left")
        self._cash_mode_var = ctk.StringVar(value=api.get_setting("cash_session_mode", "1"))
        ctk.CTkSwitch(cash_row, text="Activado", variable=self._cash_mode_var, onvalue="1", offvalue="0",
                      command=lambda: api.set_setting("cash_session_mode", self._cash_mode_var.get())).pack(side="left", padx=12)
        self._save_btn(card, self._save_pos_payments)

    def _save_pos_payments(self):
        api.set_setting("mp_integration", self._mp_mode_var.get())
        for key, e in self._mp_entries.items():
            if e.get().strip(): api.set_setting(key, e.get().strip())
        messagebox.showinfo("Guardado", "Configuración POS actualizada.")

    # ════════════════════════════════════════════════════════
    #  TAB 7 – AFIP
    # ════════════════════════════════════════════════════════
    def _build_afip(self, parent):
        card = self._card(parent, "Factura Electrónica AFIP")
        ctk.CTkLabel(card, text="Integración con WSFEv1. Requiere certificado digital AFIP.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12), wraplength=700).pack(anchor="w", pady=(0, 10))

        dep_row = ctk.CTkFrame(card, fg_color=theme.CARD2, corner_radius=8)
        dep_row.pack(fill="x", pady=(0, 10))
        di = ctk.CTkFrame(dep_row, fg_color="transparent"); di.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(di, text="Dependencias:", text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12)).pack(side="left")
        self._afip_dep_lbl = ctk.CTkLabel(di, text="verificando…", text_color=theme.C_ORANGE,
                                           font=ctk.CTkFont(size=12, weight="bold"))
        self._afip_dep_lbl.pack(side="left", padx=10)
        ctk.CTkButton(di, text="Instalar dependencias", width=180, height=28,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._afip_install_deps).pack(side="right")
        self._check_afip_deps()

        sw_row = ctk.CTkFrame(card, fg_color="transparent"); sw_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(sw_row, text="Activar facturación AFIP:", font=ctk.CTkFont(size=12)).pack(side="left")
        self._afip_enabled_var = ctk.StringVar(value=api.get_setting("afip_habilitado", "0"))
        ctk.CTkSwitch(sw_row, text="Habilitado", variable=self._afip_enabled_var, onvalue="1", offvalue="0",
                      command=lambda: api.set_setting("afip_habilitado", self._afip_enabled_var.get())).pack(side="left", padx=14)

        self._sep(card)
        grid = ctk.CTkFrame(card, fg_color="transparent"); grid.pack(fill="x"); grid.columnconfigure(1, weight=1)
        self._afip_e: dict = {}
        for i, (lbl, key, ph) in enumerate([
            ("Certificado (.crt/.pem):", "afip_cert_path",   "C:/afip/cert.pem"),
            ("Clave privada (.key):",     "afip_key_path",    "C:/afip/private.key"),
            ("Punto de venta AFIP:",      "afip_punto_venta", "1"),
        ]):
            ctk.CTkLabel(grid, text=lbl, anchor="w").grid(row=i, column=0, sticky="w", padx=(0,14), pady=8)
            e = ctk.CTkEntry(grid, placeholder_text=ph, height=34)
            e.grid(row=i, column=1, sticky="ew", pady=8)
            self._afip_e[key] = e

        sel = ctk.CTkFrame(card, fg_color="transparent"); sel.pack(fill="x", pady=(8, 0))
        sel.columnconfigure((1,3), weight=1)
        self._afip_modo_var = ctk.StringVar(value=api.get_setting("afip_modo", "homologacion"))
        self._afip_tipo_var = ctk.StringVar(value=api.get_setting("afip_tipo_cbte_label", "11 – Factura C"))
        self._afip_cond_var = ctk.StringVar(value=api.get_setting("afip_condicion_iva_label", "MO – Monotributo"))
        self._afip_conc_var = ctk.StringVar(value=api.get_setting("afip_concepto_label", "1 – Productos"))
        for row_idx, (lbl, var, vals) in enumerate([
            ("Modo:", self._afip_modo_var, ["homologacion","produccion"]),
            ("Tipo cbte:", self._afip_tipo_var, ["1 – Factura A","6 – Factura B","11 – Factura C"]),
        ]):
            ctk.CTkLabel(sel, text=lbl, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=(0,10), pady=6)
            ctk.CTkOptionMenu(sel, values=vals, variable=var, width=180).grid(row=row_idx, column=1, sticky="w")
        for row_idx, (lbl, var, vals) in enumerate([
            ("Condición IVA:", self._afip_cond_var, ["MO – Monotributo","RI – Resp. Inscripto","EX – Exento"]),
            ("Concepto:", self._afip_conc_var, ["1 – Productos","2 – Servicios","3 – Productos y Servicios"]),
        ]):
            ctk.CTkLabel(sel, text=lbl, anchor="w").grid(row=row_idx, column=2, sticky="w", padx=(20,10), pady=6)
            ctk.CTkOptionMenu(sel, values=vals, variable=var, width=200).grid(row=row_idx, column=3, sticky="w")

        btn_row = ctk.CTkFrame(card, fg_color="transparent"); btn_row.pack(fill="x", pady=(12, 0))
        ctk.CTkButton(btn_row, text="Guardar AFIP", height=36, fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      command=self._save_afip).pack(side="left")
        ctk.CTkButton(btn_row, text="Probar conexión", height=36, fg_color=theme.CARD2,
                      command=self._test_afip).pack(side="left", padx=10)
        self._afip_test_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12), wraplength=680, justify="left")
        self._afip_test_lbl.pack(anchor="w", pady=(10, 0))

        ctk.CTkLabel(card, text="Pasos: auth.afip.gob.ar → Administrador de Relaciones → wsfe → Certificados Digitales",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11), wraplength=700).pack(anchor="w", pady=(14, 0))

    def _check_afip_deps(self):
        try:
            from afip import verificar_instalacion
            ok, msg = verificar_instalacion()
            if ok: self._afip_dep_lbl.configure(text="zeep y cryptography instalados", text_color=theme.C_GREEN)
            else:  self._afip_dep_lbl.configure(text=f"{msg}", text_color=theme.C_ORANGE)
        except Exception:
            self._afip_dep_lbl.configure(text="afip.py no encontrado", text_color=theme.C_RED)

    def _afip_install_deps(self):
        import subprocess, sys, threading
        self._afip_dep_lbl.configure(text="⏳ Instalando…", text_color=theme.C_ORANGE)
        def _install():
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "zeep", "cryptography", "--quiet"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.after(0, self._check_afip_deps)
            except Exception as e:
                self.after(0, lambda: self._afip_dep_lbl.configure(text=f"{e}", text_color=theme.C_RED))
        threading.Thread(target=_install, daemon=True).start()

    def _load_afip(self):
        try:
            s = api.get_all_settings()
            for key, e in self._afip_e.items(): e.delete(0,"end"); e.insert(0, s.get(key, api.get_setting(key, "")))
            self._afip_enabled_var.set(api.get_setting("afip_habilitado", "0"))
        except Exception: pass

    def _save_afip(self):
        for key, e in self._afip_e.items(): api.set_setting(key, e.get().strip())
        api.set_setting("afip_modo", self._afip_modo_var.get())
        api.set_setting("afip_tipo_cbte",     self._afip_tipo_var.get().split("")[0])
        api.set_setting("afip_condicion_iva", self._afip_cond_var.get().split("")[0])
        api.set_setting("afip_concepto",      self._afip_conc_var.get().split("")[0])
        messagebox.showinfo("AFIP", "Configuración AFIP guardada.")

    def _test_afip(self):
        import threading
        self._afip_test_lbl.configure(text="⏳ Conectando con AFIP…", text_color=theme.C_ORANGE)
        def _do():
            try:
                from afip import WSFEClient
                client = WSFEClient.from_settings()
                tipo = int(api.get_setting("afip_tipo_cbte", "11"))
                ultimo = client.ultimo_comprobante(tipo)
                msg = f"Conexión exitosa.\nÚltimo tipo {tipo}: Nº {ultimo}."
                color = theme.C_GREEN
            except Exception as e:
                msg = f"Error: {e}"; color = theme.C_RED
            self.after(0, lambda: self._afip_test_lbl.configure(text=msg, text_color=color))
        threading.Thread(target=_do, daemon=True).start()

    # ── on_show ────────────────────────────────────────────
    def on_show(self):
        for attr, method in [
            ("_btype_var",     self._load_negocio),
            ("markup_e",       self._load_pricing),
            ("_cat_grid",      self._load_category_margins),
            ("_tax_tree",      lambda: (self._load_tax_table(), self._load_audit_log(), self._refresh_tax_preview())),
            ("_smtp_e",        self._load_smtp),
            ("_company_e",     self._load_company),
            ("_afip_e",        self._load_afip),
            ("_theme_mode_var", self._load_theme),
        ]:
            try:
                if hasattr(self, attr): method()
            except Exception: pass

    def _refresh_treeview_style(self):
        if hasattr(self, "_tax_tree"):  self._tax_tree.configure(style="Cs.Treeview")
        if hasattr(self, "_audit_tree"): self._audit_tree.configure(style="Cs.Treeview")


    # ════════════════════════════════════════════════════════
    #  TAB 8 - APARIENCIA
    # ════════════════════════════════════════════════════════
    def _build_theme(self, parent):
        card = self._card(parent, "Apariencia de la interfaz")
        ctk.CTkLabel(card, text="Cambia entre modo claro y oscuro. El cambio se aplica de inmediato y se guarda.",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=12), wraplength=700).pack(anchor="w", pady=(0, 20))

        self._theme_mode_var = ctk.StringVar(value="dark")

        mode_row = ctk.CTkFrame(card, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 20))

        for label, value in [("Modo oscuro", "dark"), ("Modo claro", "light")]:
            rb = ctk.CTkRadioButton(
                mode_row, text=label,
                variable=self._theme_mode_var,
                value=value,
                font=ctk.CTkFont(size=13),
                command=self._apply_theme_change,
            )
            rb.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(card, text="Vista previa del modo seleccionado:",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(0, 8))

        self._preview_frame = ctk.CTkFrame(card, fg_color=theme.CARD2, corner_radius=8, height=80)
        self._preview_frame.pack(fill="x")
        self._preview_frame.pack_propagate(False)
        self._preview_lbl = ctk.CTkLabel(
            self._preview_frame,
            text="Modo oscuro activo",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_DIM,
        )
        self._preview_lbl.pack(expand=True)

    def _load_theme(self):
        try:
            saved = api.get_setting("ui_theme", "dark")
            self._theme_mode_var.set(saved)
            label = "Modo oscuro activo" if saved == "dark" else "Modo claro activo"
            if hasattr(self, "_preview_lbl"):
                self._preview_lbl.configure(text=label)
        except Exception:
            pass

    def _apply_theme_change(self):
        mode = self._theme_mode_var.get()
        label = "Modo oscuro activo" if mode == "dark" else "Modo claro activo"
        if hasattr(self, "_preview_lbl"):
            self._preview_lbl.configure(text=label)
        if self._app and hasattr(self._app, "apply_theme"):
            self._app.apply_theme(mode)
        else:
            import customtkinter as ctk
            ctk.set_appearance_mode(mode)
            try:
                api.set_setting("ui_theme", mode)
            except Exception:
                pass


# -- Dialogo tributo ---
class TaxDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, user_id, on_save, data=None):
        super().__init__(parent)
        self.title(title); self.geometry("420x320")
        self.resizable(False, False); self.grab_set(); self.focus()
        self._user_id = user_id; self._on_save = on_save; self._data = data
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text=self.title(),
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 4))
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=(0, 12))
        frm = ctk.CTkFrame(self, fg_color="transparent"); frm.pack(fill="x", padx=28)

        ctk.CTkLabel(frm, text="Nombre del tributo * (ej: IVA, IIBB)", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM).pack(fill="x")
        self.name_e = ctk.CTkEntry(frm, placeholder_text="IVA 21%", height=36)
        self.name_e.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(frm, text="Porcentaje (%) *", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM).pack(fill="x")
        self.pct_e = ctk.CTkEntry(frm, placeholder_text="21", justify="center", width=100, height=36)
        self.pct_e.pack(anchor="w", pady=(2, 10))

        ctk.CTkLabel(frm, text="Modo de aplicación:", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM).pack(fill="x")
        self.mode_var = ctk.StringVar(value="included")
        mf = ctk.CTkFrame(frm, fg_color="transparent"); mf.pack(fill="x", pady=(2, 12))
        ctk.CTkRadioButton(mf, text="Incluido en el precio (desglose interno)",
                            variable=self.mode_var, value="included").pack(anchor="w")
        ctk.CTkRadioButton(mf, text="Se suma al precio neto",
                            variable=self.mode_var, value="added").pack(anchor="w", pady=(6, 0))

        if self._data:
            self.name_e.insert(0, self._data["name"]); self.pct_e.insert(0, str(self._data["percent"]))
            self.mode_var.set("included" if self._data["is_included"] else "added")

        self.err = ctk.CTkLabel(frm, text="", text_color=theme.C_RED, font=ctk.CTkFont(size=11))
        self.err.pack(pady=4)
        ctk.CTkButton(frm, text="Guardar", height=40,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._save).pack(fill="x", pady=(2, 16))

    def _save(self):
        name = self.name_e.get().strip()
        if not name: self.err.configure(text="Nombre obligatorio."); return
        try: pct = float(self.pct_e.get()); assert 0 < pct <= 100
        except Exception: self.err.configure(text="Porcentaje entre 0.01 y 100."); return
        is_inc = self.mode_var.get() == "included"
        if self._data: api.update_tax(self._data["id"], name, pct, is_inc, self._user_id)
        else:          api.add_tax(name, pct, is_inc, self._user_id)
        self._on_save(); self.destroy()
