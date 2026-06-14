"""inventory.py – Inventario.
 · UI construida una sola vez en __init__
 · on_show() solo recarga filas del Treeview (rápido, sin flash)
 · Columna ML: estado de sync con MercadoLibre por producto
 · ML Sync All: importa productos de ML al inventario local si no existen
 · Botón "Publicar en ML": crea publicación en ML para productos sin listing
 · Edición completa de producto desde el inventario (precio override, costo reposición, notas)
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
import api, theme
import widgets as W

_CATS_FALLBACK = ["Sin Categoría"]

def _get_cats():
    try:
        c = api.get_all_categories()
        return c if c else _CATS_FALLBACK
    except Exception:
        return _CATS_FALLBACK


class InventoryFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._sel_id: int | None = None
        self._show_inactive = False
        self._sort_rev = False
        self._cols: list[str] = []
        self._ml_status: dict = {}
        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 6))
        ctk.CTkLabel(hdr, text="Inventario",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_row.pack(side="right")

        ctk.CTkButton(btn_row, text="↻", width=34, height=32, corner_radius=7,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=14),
                      command=self._load).pack(side="left", padx=(0, 4))

        if self.perms.get("ver_mercadolibre", True):
            ctk.CTkButton(btn_row, text="ML Mapear", width=100, height=32,
                          corner_radius=7,
                          fg_color="#3483fa", hover_color="#2563eb",
                          text_color="white",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._open_ml_mapping).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_row, text="ML Sync All", width=100, height=32,
                          corner_radius=7,
                          fg_color="#1e3a5f", hover_color="#2563eb",
                          text_color="#93c5fd",
                          font=ctk.CTkFont(size=11),
                          command=self._sync_all_ml).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_row, text="⬆ Publicar en ML", width=140, height=32,
                          corner_radius=7,
                          fg_color="#f59e0b", hover_color="#d97706",
                          text_color="#000000",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._publish_to_ml).pack(side="left", padx=(0, 4))

        if self.perms.get("eliminar_producto", True):
            ctk.CTkButton(btn_row, text="Dar de baja", width=120, height=32,
                          corner_radius=7, fg_color=theme.BTN_RED, hover_color=theme.BTN_REDH,
                          command=self._delete).pack(side="left", padx=(0, 4))
        if self.perms.get("editar_producto", True):
            ctk.CTkButton(btn_row, text="Editar", width=96, height=32,
                          corner_radius=7, fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                          command=self._edit).pack(side="left", padx=(0, 4))
        if self.perms.get("agregar_producto", True):
            ctk.CTkButton(btn_row, text="Agregar", width=110, height=32,
                          corner_radius=7, fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                          command=self._add).pack(side="left")

        # ── Barra de filtros ───────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color=theme.CARD2, corner_radius=10)
        bar.pack(fill="x", padx=24, pady=(0, 8))

        self._search = ctk.CTkEntry(bar, width=220, placeholder_text="Buscar producto…",
                                     height=32, corner_radius=7, border_color=theme.SEP)
        self._search.pack(side="left", padx=(12, 0), pady=9)
        self._search.bind("<KeyRelease>", lambda _: self._load())

        ctk.CTkLabel(bar, text="Categoría:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(14, 4))
        self._cat_var = ctk.StringVar(value="Todas")
        self._cat_menu = ctk.CTkOptionMenu(bar, variable=self._cat_var,
                                            values=["Todas"] + _get_cats(),
                                            width=140, height=32, corner_radius=7,
                                            command=lambda _: self._load())
        self._cat_menu.pack(side="left")

        self._inactive_switch = ctk.CTkSwitch(bar, text="Inactivos",
                                               font=ctk.CTkFont(size=11),
                                               command=self._toggle_inactive)
        self._inactive_switch.pack(side="left", padx=14)

        self._inv_lbl = ctk.CTkLabel(bar, text="", text_color=theme.TEXT_DIM,
                                      font=ctk.CTkFont(size=11))
        self._inv_lbl.pack(side="right", padx=16)

        # ── Tabla ──────────────────────────────────────────────
        self._cols = ["ID", "Producto", "Categoría", "Stock", "Precio venta", "Proveedor", "ML"]
        widths     = [50, 240, 110, 75, 130, 180, 90]
        anchors    = ["center", "w", "center", "center", "e", "w", "center"]

        if self.perms.get("ver_precio_costo", True):
            self._cols.insert(4, "Costo"); self._cols.insert(5, "Margen")
            widths.insert(4, 100);  widths.insert(5, 100)
            anchors.insert(4, "e"); anchors.insert(5, "center")

        self._tf, self.tree = W.make_tree(
            self, self._cols, widths, anchors, height=20)
        self.tree.tag_configure("low",      foreground=theme.C_ORANGE)
        self.tree.tag_configure("critical", foreground=theme.C_RED)
        self.tree.tag_configure("inactive", foreground=theme.TEXT_DIM[1])
        self.tree.tag_configure("ml_sync",   foreground="#3483fa")
        self.tree.tag_configure("ml_nosync", foreground="#64748b")

        for col in self._cols:
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sort_by(c))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",          lambda _: self._edit())
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    def _refresh_treeview_style(self):
        self.tree.configure(style="Cs.Treeview")

    # ── Datos ──────────────────────────────────────────────
    def _load(self):
        self.tree.delete(*self.tree.get_children())
        search = self._search.get().strip()
        cat    = "" if self._cat_var.get() == "Todas" else self._cat_var.get()

        try:
            rows = api.get_all_products(search=search, category=cat)
        except Exception:
            return

        show_cost = self.perms.get("ver_precio_costo", True)
        inv_val   = 0.0

        self._load_ml_status_async([r[0] for r in rows])

        for (id_, name, category, cost, price, custom_margin, stock, active, supplier) in rows:
            if not active and not self._show_inactive:
                continue
            inv_val += float(price or 0) * int(stock or 0)
            tag = ("inactive" if not active
                   else "critical" if stock <= 3
                   else "low" if stock <= 10
                   else "")
            try:
                _, src, margin = api.calculate_sell_price_hierarchy(
                    float(cost or 0), category, id_)
                m_txt = f"{margin:.0f}% ({src[:4]})"
            except Exception:
                m_txt = "—"

            ml_info = self._ml_status.get(id_)
            ml_txt  = self._ml_badge(ml_info)

            if show_cost:
                vals = (id_, name, category,
                        f"${float(cost or 0):,.2f}", m_txt,
                        stock, f"${float(price or 0):,.2f}", supplier or "—", ml_txt)
            else:
                vals = (id_, name, category, stock,
                        f"${float(price or 0):,.2f}", supplier or "—", ml_txt)

            self.tree.insert("", "end", iid=str(id_), values=vals,
                             tags=(tag,) if tag else ())

        self._inv_lbl.configure(text=f"Inventario: ${inv_val:,.0f}")

    def _ml_badge(self, ml_info: dict | None) -> str:
        if not ml_info:
            return "—"
        st  = ml_info.get("status", "")
        qty = ml_info.get("available_qty", 0)
        syn = "🔄" if ml_info.get("sync_stock") else "⏸"
        labels = {
            "active":       f"✅ {qty} {syn}",
            "paused":       f"⏸ {qty}",
            "closed":       "🔒 Cerrada",
            "under_review": "🔍 Review",
        }
        return labels.get(st, f"? {st}")

    def _load_ml_status_async(self, id_products: list):
        if not id_products or not self.perms.get("ver_mercadolibre", True):
            return

        def _do():
            try:
                from ml_api import get_ml_status_for_products
                result = get_ml_status_for_products(id_products)
                self.after(0, lambda r=result: self._apply_ml_status(r))
            except Exception:
                pass

        threading.Thread(target=_do, daemon=True).start()

    def _apply_ml_status(self, status_map: dict):
        self._ml_status = status_map
        ml_col_idx = len(self._cols) - 1
        for iid in self.tree.get_children():
            try:
                id_product = int(iid)
                ml_info    = status_map.get(id_product)
                ml_txt     = self._ml_badge(ml_info)
                current    = list(self.tree.item(iid, "values"))
                current[ml_col_idx] = ml_txt
                self.tree.item(iid, values=current)
            except Exception:
                pass

    # ── ML Sync All ────────────────────────────────────────
    def _sync_all_ml(self):
        """
        1. Sincroniza stock local → ML para listings activos.
        2. Importa listings de ML que no existan como productos locales.
        """
        self._inv_lbl.configure(text="Sincronizando con ML…")

        def _do():
            try:
                from ml_api import get_all_ml_accounts, sync_all_stocks, sync_catalog_to_inventory
                accounts = get_all_ml_accounts()
                active   = next((a for a in accounts if a[3]), None)
                if not active:
                    self.after(0, lambda: self._inv_lbl.configure(
                        text="Sin cuenta ML activa."))
                    return
                uid = str(active[0])

                # Paso 1: stock local → ML
                result = sync_all_stocks(uid)

                # Paso 2: importar productos nuevos desde ML
                import_result = sync_catalog_to_inventory(uid)

                msg = (
                    f"ML sync OK — Stock actualizado: {result['synced']} | "
                    f"Errores: {result['errors']} | "
                    f"Nuevos desde ML: {import_result['created']} | "
                    f"Ya existían: {import_result['skipped']}"
                )
                self.after(0, lambda m=msg: (
                    self._inv_lbl.configure(text=m),
                    self._load()
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._inv_lbl.configure(
                    text=f"Error ML sync: {err}"))

        threading.Thread(target=_do, daemon=True).start()

    # ── Publicar en ML ──────────────────────────────────────
    def _publish_to_ml(self):
        """Abre diálogo para crear una publicación en ML del producto seleccionado."""
        if not self._sel_id:
            messagebox.showwarning("Sin selección",
                                   "Seleccioná un producto para publicar en MercadoLibre.")
            return
        ml_info = self._ml_status.get(self._sel_id)
        if ml_info and ml_info.get("ml_item_id"):
            if not messagebox.askyesno(
                "Ya publicado",
                f"Este producto ya tiene listing en ML: {ml_info['ml_item_id']}\n"
                "¿Querés crear una publicación adicional de todas formas?"
            ):
                return
        product_row = api.get_product_by_id(self._sel_id)
        if not product_row:
            return
        PublishToMLDialog(self, id_product=self._sel_id,
                          product_row=product_row,
                          on_done=self._load)

    # ── ML Mapear ──────────────────────────────────────────
    def _open_ml_mapping(self):
        if not self._sel_id:
            messagebox.showwarning("Sin selección", "Seleccioná un producto primero.")
            return
        product_row = api.get_product_by_id(self._sel_id)
        if not product_row:
            return
        MLMappingDialog(self, id_product=self._sel_id,
                        product_name=product_row[1],
                        ml_info=self._ml_status.get(self._sel_id),
                        on_save=self._load)

    def _toggle_inactive(self):
        self._show_inactive = not self._show_inactive
        self._load()

    def _sort_by(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda x: float(x[0].replace("$", "").replace(",", "")),
                       reverse=self._sort_rev)
        except ValueError:
            items.sort(key=lambda x: x[0].lower(), reverse=self._sort_rev)
        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)
        self._sort_rev = not self._sort_rev

    def _on_select(self, _=None):
        sel = self.tree.selection()
        self._sel_id = int(sel[0]) if sel else None

    def _add(self):
        cats = _get_cats()
        self._cat_menu.configure(values=["Todas"] + cats)
        ProductDialog(self, user=self.user, on_save=self._load)

    def _edit(self):
        if not self._sel_id:
            messagebox.showwarning("Sin selección", "Seleccioná un producto primero.")
            return
        data = api.get_product_by_id(self._sel_id)
        if data:
            ProductDialog(self, user=self.user, data=data, on_save=self._load)

    def _delete(self):
        if not self._sel_id:
            messagebox.showwarning("Sin selección", "Seleccioná un producto primero.")
            return
        if messagebox.askyesno("Dar de baja",
                               "¿Dar de baja el producto?\n(queda inactivo, no se elimina)"):
            api.delete_product(self._sel_id)
            self._sel_id = None
            self._load()

    def on_show(self):
        cats = _get_cats()
        self._cat_menu.configure(values=["Todas"] + cats)
        self._load()


# ══════════════════════════════════════════════════════════════
#  Diálogo: Publicar producto en MercadoLibre
# ══════════════════════════════════════════════════════════════

class PublishToMLDialog(ctk.CTkToplevel):
    """
    Crea una publicación nueva en MercadoLibre para un producto local.
    Llama a ml_api.create_listing_from_product().
    Las categorías ML se buscan en tiempo real desde la API.
    """
    def __init__(self, parent, id_product: int, product_row: tuple, on_done):
        super().__init__(parent)
        self._id_product  = id_product
        self._product_row = product_row
        self._on_done     = on_done
        self._cat_id_selected = ""      # ID real que se envía a ML
        self._cat_results     = []      # lista de (id, nombre) de la búsqueda

        (id_, name, category, cost, price, custom_margin, stock, id_supplier, *_) = product_row
        self._name  = name
        self._price = float(price or 0)
        self._stock = int(stock or 0)

        self.title(f"Publicar en ML — {name[:45]}")
        self.geometry("620x720")
        self.resizable(False, True)
        self.grab_set()
        self.focus()
        self._build()

    def _build(self):
        import theme

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#3483fa", height=56, corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⬆  Nueva publicación en MercadoLibre",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=16)

        sc = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sc.pack(fill="both", expand=True)
        frm = ctk.CTkFrame(sc, fg_color="transparent")
        frm.pack(fill="x", padx=24, pady=(12, 0))

        def lbl(t, req=False):
            ctk.CTkLabel(frm, text=f"{t} *" if req else t, anchor="w",
                         text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", pady=(8, 0))

        lbl("Título de la publicación", req=True)
        self._title_e = ctk.CTkEntry(frm, height=36)
        self._title_e.insert(0, self._name)
        self._title_e.pack(fill="x", pady=(2, 0))

        # Precio + stock en fila
        ps_row = ctk.CTkFrame(frm, fg_color="transparent")
        ps_row.pack(fill="x", pady=(8, 0))
        ps_row.columnconfigure(0, weight=1); ps_row.columnconfigure(1, weight=1)

        pl = ctk.CTkFrame(ps_row, fg_color="transparent")
        pl.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(pl, text="Precio de venta ($) *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._price_e = ctk.CTkEntry(pl, height=34, justify="center")
        self._price_e.insert(0, f"{self._price:.2f}")
        self._price_e.pack(fill="x", pady=(2, 0))

        pr = ctk.CTkFrame(ps_row, fg_color="transparent")
        pr.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(pr, text="Stock disponible *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._stock_e = ctk.CTkEntry(pr, height=34, justify="center")
        self._stock_e.insert(0, str(self._stock))
        self._stock_e.pack(fill="x", pady=(2, 0))

        # Tipo + condición
        tc_row = ctk.CTkFrame(frm, fg_color="transparent")
        tc_row.pack(fill="x", pady=(8, 0))
        tc_row.columnconfigure(0, weight=1); tc_row.columnconfigure(1, weight=1)

        tl = ctk.CTkFrame(tc_row, fg_color="transparent")
        tl.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(tl, text="Tipo de publicación", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._listing_type_var = ctk.StringVar(value="gold_special")
        ctk.CTkOptionMenu(tl, variable=self._listing_type_var,
                          values=["gold_special", "gold_pro", "free"],
                          height=32).pack(fill="x", pady=(2, 0))

        tr_f = ctk.CTkFrame(tc_row, fg_color="transparent")
        tr_f.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(tr_f, text="Condición", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._condition_var = ctk.StringVar(value="new")
        ctk.CTkOptionMenu(tr_f, variable=self._condition_var,
                          values=["new", "used"],
                          height=32).pack(fill="x", pady=(2, 0))

        # ── Sección de categoría ML ──────────────────────────
        cat_card = ctk.CTkFrame(frm, fg_color=theme.CARD2, corner_radius=10)
        cat_card.pack(fill="x", pady=(12, 0))
        cat_inner = ctk.CTkFrame(cat_card, fg_color="transparent")
        cat_inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(cat_inner, text="Categoría ML *",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(cat_inner,
                     text="Buscá la categoría por nombre (ej: 'notebook', 'zapatillas', 'celular')",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).pack(anchor="w")

        # Buscador
        search_row = ctk.CTkFrame(cat_inner, fg_color="transparent")
        search_row.pack(fill="x", pady=(8, 0))
        self._cat_search_e = ctk.CTkEntry(search_row, height=34,
                                           placeholder_text="Escribí para buscar categorías...")
        self._cat_search_e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(search_row, text="Buscar", width=90, height=34,
                      fg_color="#3483fa", hover_color="#2563eb",
                      command=self._search_categories).pack(side="left")

        # Estado de búsqueda
        self._cat_status_lbl = ctk.CTkLabel(cat_inner, text="",
                                             font=ctk.CTkFont(size=10),
                                             text_color=theme.TEXT_DIM)
        self._cat_status_lbl.pack(anchor="w", pady=(4, 0))

        # Lista de resultados (scrollable)
        self._cat_list_frame = ctk.CTkScrollableFrame(cat_inner, height=130,
                                                        fg_color=theme.CARD,
                                                        corner_radius=8)
        self._cat_list_frame.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(self._cat_list_frame,
                     text="Ingresá un término y hacé clic en Buscar",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(pady=10)

        # Selección actual
        self._cat_sel_frame = ctk.CTkFrame(cat_inner, fg_color="#1e3a5f",
                                            corner_radius=8)
        self._cat_sel_lbl = ctk.CTkLabel(self._cat_sel_frame,
                                          text="Sin categoría seleccionada",
                                          text_color="#93c5fd",
                                          font=ctk.CTkFont(size=11))
        self._cat_sel_lbl.pack(padx=12, pady=8)
        self._cat_sel_frame.pack(fill="x", pady=(6, 0))

        # También permitir ingresar ID manual como fallback
        manual_row = ctk.CTkFrame(cat_inner, fg_color="transparent")
        manual_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(manual_row, text="O ingresá el ID directamente:",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10)).pack(side="left")
        self._cat_manual_e = ctk.CTkEntry(manual_row, width=130, height=28,
                                           placeholder_text="ej: MLA1055")
        self._cat_manual_e.pack(side="left", padx=(6, 0))
        self._cat_manual_e.bind("<KeyRelease>", self._on_manual_cat)

        # Bind Enter en el buscador
        self._cat_search_e.bind("<Return>", lambda _: self._search_categories())

        # ── Descripción ──────────────────────────────────────
        lbl("Descripción (texto plano)")
        self._desc_e = ctk.CTkTextbox(frm, height=90, corner_radius=8,
                                       border_width=1, border_color=theme.SEP,
                                       font=ctk.CTkFont(size=11))
        self._desc_e.insert("1.0", f"{self._name}\n\nCaracterísticas y detalles del producto:")
        self._desc_e.pack(fill="x", pady=(2, 0))

        # Calculadora comisión
        calc_f = ctk.CTkFrame(frm, fg_color=theme.CARD2, corner_radius=8)
        calc_f.pack(fill="x", pady=(10, 0))
        ci = ctk.CTkFrame(calc_f, fg_color="transparent")
        ci.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(ci, text="Comisión ML estimada (~14%):",
                     font=ctk.CTkFont(size=11), text_color=theme.TEXT_DIM).pack(side="left")
        self._comm_lbl = ctk.CTkLabel(ci, text="—",
                                       font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color=theme.C_ORANGE)
        self._comm_lbl.pack(side="left", padx=(8, 0))
        ctk.CTkButton(ci, text="Calcular", width=80, height=26,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      font=ctk.CTkFont(size=10),
                      command=self._calc).pack(side="right")

        # Sync automático
        sw_row = ctk.CTkFrame(frm, fg_color="transparent")
        sw_row.pack(fill="x", pady=(10, 0))
        self._sync_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(sw_row, text="Sincronizar stock automáticamente tras publicar",
                      variable=self._sync_var,
                      font=ctk.CTkFont(size=11)).pack(side="left")

        self._err_lbl = ctk.CTkLabel(frm, text="",
                                      text_color=theme.C_RED,
                                      font=ctk.CTkFont(size=11), wraplength=560)
        self._err_lbl.pack(pady=(8, 0))

        # Botones
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x", pady=(4, 0))
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=24, pady=12)
        ctk.CTkButton(foot, text="Cancelar", width=100, height=38,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(foot, text="⬆  Publicar en MercadoLibre", height=38,
                      fg_color="#3483fa", hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._publish).pack(side="right")

    def _on_manual_cat(self, _=None):
        """Si el usuario escribe un ID manual, lo usa como selección."""
        val = self._cat_manual_e.get().strip().upper()
        if val.startswith("MLA"):
            self._cat_id_selected = val
            self._cat_sel_lbl.configure(
                text=f"ID manual: {val}")

    def _search_categories(self):
        """Busca categorías en la API de ML y muestra los resultados."""
        query = self._cat_search_e.get().strip()
        if not query:
            return
        self._cat_status_lbl.configure(text="Buscando…", text_color=theme.TEXT_DIM)
        for w in self._cat_list_frame.winfo_children():
            w.destroy()

        import threading
        threading.Thread(target=self._do_search_categories, args=(query,), daemon=True).start()

    def _do_search_categories(self, query: str):
        try:
            from ml_api import _get, get_all_ml_accounts, get_valid_token
            accounts = get_all_ml_accounts()
            active = next((a for a in accounts if a[3]), None)
            token = get_valid_token(str(active[0])) if active else ""

            # Predictor de categorías de ML
            import urllib.parse
            encoded = urllib.parse.quote(query)
            url = f"https://api.mercadolibre.com/sites/MLA/domain_discovery/search?q={encoded}&limit=20"
            results = _get(url, token=token)

            cats = []
            if isinstance(results, list):
                for item in results:
                    cat_id   = item.get("category_id", "")
                    cat_name = item.get("category_name", "")
                    domain   = item.get("domain_name", "")
                    if cat_id and cat_name:
                        cats.append((cat_id, cat_name, domain))
            elif isinstance(results, dict):
                # Fallback: búsqueda directa por categorías raíz
                for item in results.get("categories", []):
                    cats.append((item.get("id",""), item.get("name",""), ""))

            # Si no hay resultados con domain_discovery, buscar con suggest
            if not cats:
                url2 = f"https://api.mercadolibre.com/sites/MLA/categories/suggests?q={encoded}"
                try:
                    r2 = _get(url2, token=token)
                    if isinstance(r2, list):
                        for item in r2:
                            cats.append((item.get("category_id",""), item.get("category_name",""), ""))
                except Exception:
                    pass

            self.after(0, lambda c=cats: self._show_cat_results(c))
        except Exception as e:
            self.after(0, lambda err=str(e): self._cat_status_lbl.configure(
                text=f"Error: {err}", text_color=theme.C_RED))

    def _show_cat_results(self, cats: list):
        import theme
        for w in self._cat_list_frame.winfo_children():
            w.destroy()

        if not cats:
            ctk.CTkLabel(self._cat_list_frame,
                         text="Sin resultados. Probá con otro término o usá el ID manual.",
                         text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(pady=10)
            self._cat_status_lbl.configure(text="Sin resultados", text_color=theme.C_ORANGE)
            return

        self._cat_status_lbl.configure(
            text=f"{len(cats)} categorías encontradas — hacé clic para seleccionar",
            text_color=theme.C_GREEN)

        for (cat_id, cat_name, domain) in cats:
            display = f"{cat_name}  [{cat_id}]"
            if domain:
                display = f"{cat_name}  ({domain})  [{cat_id}]"
            btn = ctk.CTkButton(
                self._cat_list_frame,
                text=display,
                anchor="w", height=30, corner_radius=6,
                fg_color="transparent", hover_color="#1e3a5f",
                text_color=theme.TEXT, font=ctk.CTkFont(size=11),
                command=lambda cid=cat_id, cname=cat_name: self._select_category(cid, cname)
            )
            btn.pack(fill="x", pady=1)

    def _select_category(self, cat_id: str, cat_name: str):
        self._cat_id_selected = cat_id
        self._cat_sel_lbl.configure(
            text=f"✅ Seleccionada: {cat_name}  [{cat_id}]",
            text_color="#4ade80")
        # Limpiar el manual por si había algo
        self._cat_manual_e.delete(0, "end")

    def _calc(self):
        try:
            price = float(self._price_e.get())
            comm  = round(price * 0.14, 2)
            net   = round(price - comm, 2)
            self._comm_lbl.configure(
                text=f"${comm:,.2f}  →  neto aprox: ${net:,.2f}")
        except Exception:
            self._comm_lbl.configure(text="Precio inválido")

    def _publish(self):
        title = self._title_e.get().strip()
        if not title:
            self._err_lbl.configure(text="El título es obligatorio."); return
        try:
            price = float(self._price_e.get()); assert price > 0
        except Exception:
            self._err_lbl.configure(text="Precio inválido."); return
        try:
            qty = int(self._stock_e.get()); assert qty >= 0
        except Exception:
            self._err_lbl.configure(text="Stock inválido."); return

        # Categoría: primero la seleccionada por búsqueda, luego la manual
        cat_ml = self._cat_id_selected or self._cat_manual_e.get().strip()
        if not cat_ml:
            self._err_lbl.configure(
                text="Seleccioná una categoría buscando arriba, o ingresá el ID manualmente."); return

        self._err_lbl.configure(text="Publicando en MercadoLibre…",
                                 text_color=theme.TEXT_DIM)

        desc         = self._desc_e.get("1.0", "end").strip()
        sync_stock   = self._sync_var.get()
        listing_type = self._listing_type_var.get()
        condition    = self._condition_var.get()

        def _run():
            try:
                from ml_api import get_all_ml_accounts, create_listing_from_product
                accounts = get_all_ml_accounts()
                active   = next((a for a in accounts if a[3]), None)
                if not active:
                    self.after(0, lambda: self._err_lbl.configure(
                        text="Sin cuenta ML activa. Vinculá una cuenta en "
                             "Configuración → MercadoLibre → Configuración.",
                        text_color=theme.C_RED))
                    return
                uid    = str(active[0])
                result = create_listing_from_product(
                    ml_user_id   = uid,
                    id_product   = self._id_product,
                    title        = title,
                    price        = price,
                    available_qty= qty,
                    category_id  = cat_ml,
                    description  = desc,
                    listing_type = listing_type,
                    condition    = condition,
                    sync_stock   = sync_stock,
                )
                if result.get("ok"):
                    ml_id = result.get("ml_item_id", "—")
                    link  = result.get("permalink", "")
                    self.after(0, lambda: (
                        messagebox.showinfo(
                            "¡Publicado!",
                            f"✅ Publicación creada correctamente.\n\n"
                            f"ID MercadoLibre: {ml_id}\n"
                            f"Link: {link or '(disponible en unos minutos)'}"),
                        self._on_done(),
                        self.destroy(),
                    ))
                else:
                    err = result.get("error", "Error desconocido")
                    self.after(0, lambda e=err: self._err_lbl.configure(
                        text=f"Error ML: {e}", text_color=theme.C_RED))
            except Exception as e:
                self.after(0, lambda err=str(e): self._err_lbl.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))

        import threading
        threading.Thread(target=_run, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  Diálogo: mapeo ML
# ══════════════════════════════════════════════════════════════

class MLMappingDialog(ctk.CTkToplevel):
    """
    Mapea un listing de ML a un producto local.
    Muestra los listings de ML en un combo (no pide ID a mano).
    """
    def __init__(self, parent, id_product: int, product_name: str,
                 ml_info: dict | None, on_save):
        super().__init__(parent)
        self._id_product   = id_product
        self._product_name = product_name
        self._ml_info      = ml_info or {}
        self._on_save      = on_save
        self._listings     = []       # lista de rows de get_listings_local
        self._selected_item_id = ""   # ml_item_id elegido

        self.title(f"ML Sync — {product_name[:40]}")
        self.geometry("560x500")
        self.resizable(False, True)
        self.grab_set()
        self.focus()
        self._build()
        self._load_listings()

    def _build(self):
        import theme

        hdr_f = ctk.CTkFrame(self, fg_color="#1e3a5f", height=58, corner_radius=0)
        hdr_f.pack(fill="x"); hdr_f.pack_propagate(False)
        hi = ctk.CTkFrame(hdr_f, fg_color="transparent")
        hi.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(hi, text="ML", fg_color="#3483fa", corner_radius=6,
                     width=32, height=32, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="white").pack(side="left")
        ctk.CTkLabel(hi, text="  Sincronización MercadoLibre",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#e2e8f0").pack(side="left")

        # Info del vínculo actual
        info_f = ctk.CTkFrame(self, fg_color=theme.CARD2, corner_radius=10)
        info_f.pack(fill="x", padx=20, pady=(16, 8))
        if self._ml_info and self._ml_info.get("ml_item_id"):
            ml_item_id = self._ml_info.get("ml_item_id", "—")
            status     = self._ml_info.get("status", "—")
            qty_ml     = self._ml_info.get("available_qty", 0)
            sync_on    = self._ml_info.get("sync_stock", False)
            status_color = {"active": theme.C_GREEN, "paused": theme.C_ORANGE}.get(
                status, theme.TEXT_DIM)
            ctk.CTkLabel(info_f, text=f"Vínculo actual: {ml_item_id}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#3483fa").pack(anchor="w", padx=14, pady=(10, 2))
            r1 = ctk.CTkFrame(info_f, fg_color="transparent")
            r1.pack(fill="x", padx=14, pady=(0, 10))
            ctk.CTkLabel(r1, text=f"Estado: {status}",
                         text_color=status_color, font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(r1, text=f"  |  Stock ML: {qty_ml}",
                         text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(side="left")
            sync_txt = "  |  Sync: ACTIVO 🔄" if sync_on else "  |  Sync: pausado"
            ctk.CTkLabel(r1, text=sync_txt,
                         text_color="#3483fa" if sync_on else theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(side="left")
        else:
            ctk.CTkLabel(info_f, text="Sin listing vinculado a este producto.",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=12)).pack(padx=14, pady=14)

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=20)

        # Producto a vincular (info de solo lectura)
        prod_card = ctk.CTkFrame(frm, fg_color=theme.CARD, corner_radius=8,
                                  border_width=1, border_color=theme.SEP)
        prod_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(prod_card,
                     text=f"Producto: {self._product_name}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=12, pady=10)

        # ── Selector de listing ML ───────────────────────────
        ctk.CTkLabel(frm, text="Seleccioná la publicación de ML a vincular:",
                     anchor="w", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x", pady=(4, 0))

        # Buscador para filtrar listings
        search_row = ctk.CTkFrame(frm, fg_color="transparent")
        search_row.pack(fill="x", pady=(4, 0))
        self._listing_search = ctk.CTkEntry(search_row, height=32,
                                             placeholder_text="Buscar en mis publicaciones ML…")
        self._listing_search.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._listing_search.bind("<KeyRelease>", self._filter_listings)
        ctk.CTkButton(search_row, text="↻", width=36, height=32,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self._load_listings).pack(side="left")

        self._loading_lbl = ctk.CTkLabel(frm, text="Cargando publicaciones ML…",
                                          text_color=theme.TEXT_DIM,
                                          font=ctk.CTkFont(size=11))
        self._loading_lbl.pack(anchor="w", pady=(4, 0))

        # Lista scrollable de listings
        self._listing_frame = ctk.CTkScrollableFrame(frm, height=160,
                                                      fg_color=theme.CARD,
                                                      corner_radius=8,
                                                      border_width=1,
                                                      border_color=theme.SEP)
        self._listing_frame.pack(fill="x", pady=(4, 0))

        # Selección actual
        self._sel_card = ctk.CTkFrame(frm, fg_color="#1e3a5f", corner_radius=8)
        self._sel_lbl = ctk.CTkLabel(self._sel_card,
                                      text="Sin publicación seleccionada",
                                      text_color="#93c5fd",
                                      font=ctk.CTkFont(size=11))
        self._sel_lbl.pack(padx=12, pady=8)
        self._sel_card.pack(fill="x", pady=(6, 0))

        # Sync switch
        sw_row = ctk.CTkFrame(frm, fg_color="transparent")
        sw_row.pack(fill="x", pady=(10, 0))
        self._sync_var = ctk.BooleanVar(value=self._ml_info.get("sync_stock", False))
        ctk.CTkSwitch(sw_row, text="Sincronizar stock automáticamente",
                      variable=self._sync_var,
                      font=ctk.CTkFont(size=12)).pack(side="left")

        self._status_lbl = ctk.CTkLabel(frm, text="", font=ctk.CTkFont(size=11))
        self._status_lbl.pack(anchor="w", pady=(6, 0))

        # Botones
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(fill="x", padx=20, pady=(12, 16))
        ctk.CTkButton(btn_f, text="Guardar vínculo", height=38,
                      fg_color="#3483fa", hover_color="#2563eb",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(btn_f, text="Forzar push stock", height=38,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._force_push).pack(side="left")

    def _load_listings(self):
        """Carga los listings ML locales en background."""
        import threading
        self._loading_lbl.configure(text="Cargando publicaciones ML…",
                                     text_color=theme.TEXT_DIM)
        threading.Thread(target=self._fetch_listings, daemon=True).start()

    def _fetch_listings(self):
        try:
            from ml_api import get_listings_local, get_all_ml_accounts
            accounts = get_all_ml_accounts()
            active   = next((a for a in accounts if a[3]), None)
            uid      = str(active[0]) if active else ""
            rows     = get_listings_local(ml_user_id=uid) if uid else []
            self.after(0, lambda r=rows: self._apply_listings(r))
        except Exception as e:
            self.after(0, lambda err=str(e): self._loading_lbl.configure(
                text=f"Error: {err}", text_color=theme.C_RED))

    def _apply_listings(self, rows: list):
        import theme as th
        self._listings = rows
        self._loading_lbl.configure(
            text=f"{len(rows)} publicaciones disponibles",
            text_color=th.C_GREEN)
        self._render_listings(rows)

    def _filter_listings(self, _=None):
        q = self._listing_search.get().strip().lower()
        filtered = [r for r in self._listings
                    if q in (r[2] or "").lower() or q in (r[1] or "").lower()]
        self._render_listings(filtered)

    def _render_listings(self, rows: list):
        import theme as th
        for w in self._listing_frame.winfo_children():
            w.destroy()

        if not rows:
            ctk.CTkLabel(self._listing_frame,
                         text="Sin publicaciones. Importá el catálogo desde MercadoLibre → Catálogo.",
                         text_color=th.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(pady=14)
            return

        STATUS_LABELS = {"active": "✅ Activa", "paused": "⏸ Pausada", "closed": "🔒 Cerrada"}
        STATUS_COLORS = {"active": th.C_GREEN, "paused": th.C_ORANGE, "closed": th.TEXT_DIM}

        for row in rows:
            (id_l, ml_item_id, title, price, avail_qty, sold_qty, st,
             listing_type, thumbnail, last_sync, sync_stock,
             product_name, id_prod, permalink) = row

            is_sel = ml_item_id == self._selected_item_id
            bg     = "#1e3a5f" if is_sel else th.CARD2

            card = ctk.CTkFrame(self._listing_frame, fg_color=bg,
                                 corner_radius=6, cursor="hand2")
            card.pack(fill="x", pady=2, padx=2)

            row_f = ctk.CTkFrame(card, fg_color="transparent")
            row_f.pack(fill="x", padx=10, pady=6)

            # Título + precio
            left_f = ctk.CTkFrame(row_f, fg_color="transparent")
            left_f.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(left_f,
                         text=(title or "—")[:48],
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#e2e8f0" if is_sel else th.TEXT,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(left_f,
                         text=f"${float(price or 0):,.0f}  |  stock: {avail_qty}  |  {ml_item_id}",
                         font=ctk.CTkFont(size=10),
                         text_color="#93c5fd" if is_sel else th.TEXT_DIM,
                         anchor="w").pack(anchor="w")

            # Estado
            st_lbl = STATUS_LABELS.get(st, st or "—")
            st_col = STATUS_COLORS.get(st, th.TEXT_DIM)
            ctk.CTkLabel(row_f, text=st_lbl,
                         font=ctk.CTkFont(size=10),
                         text_color=st_col if not is_sel else "#ffffff").pack(side="right")

            # Click
            for w in [card, row_f, left_f]:
                w.bind("<Button-1>",
                       lambda _, mid=ml_item_id, ttl=title: self._select_listing(mid, ttl))

    def _select_listing(self, ml_item_id: str, title: str):
        self._selected_item_id = ml_item_id
        self._sel_lbl.configure(
            text=f"✅ Seleccionada: {(title or '')[:45]}  [{ml_item_id}]",
            text_color="#4ade80")
        # Re-renderizar para resaltar la selección
        q = self._listing_search.get().strip().lower()
        filtered = [r for r in self._listings
                    if not q or q in (r[2] or "").lower() or q in (r[1] or "").lower()]
        self._render_listings(filtered)

    def _save(self):
        ml_item_id = self._selected_item_id
        if not ml_item_id:
            self._status_lbl.configure(
                text="Seleccioná una publicación de la lista.",
                text_color=theme.C_RED)
            return
        self._status_lbl.configure(text="Guardando…", text_color=theme.TEXT_DIM)

        import threading
        def _do():
            try:
                from ml_api import _eq, get_all_ml_accounts
                accounts = get_all_ml_accounts()
                active   = next((a for a in accounts if a[3]), None)
                if not active:
                    self.after(0, lambda: self._status_lbl.configure(
                        text="Sin cuenta ML activa.", text_color=theme.C_RED))
                    return
                ml_user_id = str(active[0])
                existing = _eq(
                    "SELECT id_listing FROM ml_listings WHERE ml_item_id=%s",
                    (ml_item_id,), fetch="one")
                if existing:
                    _eq("UPDATE ml_listings SET id_product=%s, sync_stock=%s "
                        "WHERE id_listing=%s",
                        (self._id_product, int(self._sync_var.get()), existing[0]))
                else:
                    _eq(
                        "INSERT INTO ml_listings "
                        "(ml_item_id, ml_user_id, title, price, available_qty, "
                        " id_product, sync_stock) "
                        "VALUES (%s,%s,%s,0,0,%s,%s) "
                        "ON CONFLICT (ml_item_id) DO UPDATE SET "
                        "  id_product=EXCLUDED.id_product, "
                        "  sync_stock=EXCLUDED.sync_stock",
                        (ml_item_id, ml_user_id, self._product_name,
                         self._id_product, int(self._sync_var.get())))
                self.after(0, lambda: (
                    self._status_lbl.configure(
                        text="Guardado correctamente.", text_color=theme.C_GREEN),
                    self._on_save(),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._status_lbl.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))

        threading.Thread(target=_do, daemon=True).start()

    def _force_push(self):
        self._status_lbl.configure(text="Empujando stock…", text_color=theme.TEXT_DIM)
        import threading
        def _do():
            try:
                stock_row = api.execute_query(
                    "SELECT stock FROM products WHERE idProduct=%s",
                    (self._id_product,), fetch="one")
                if not stock_row:
                    self.after(0, lambda: self._status_lbl.configure(
                        text="Producto no encontrado.", text_color=theme.C_RED))
                    return
                from ml_api import push_stock_after_sale
                result = push_stock_after_sale(self._id_product, int(stock_row[0]))
                msg   = (f"Push OK: {result['synced']} listing(s) actualizado(s)"
                         if result['synced'] > 0
                         else "Sin listings con sync activo para este producto.")
                color = theme.C_GREEN if result['synced'] > 0 else theme.C_ORANGE
                self.after(0, lambda m=msg, c=color: self._status_lbl.configure(
                    text=m, text_color=c))
            except Exception as e:
                self.after(0, lambda err=str(e): self._status_lbl.configure(
                    text=f"Error: {err}", text_color=theme.C_RED))

        threading.Thread(target=_do, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  Diálogo agregar / editar producto (completo)
# ══════════════════════════════════════════════════════════════

class ProductDialog(ctk.CTkToplevel):
    def __init__(self, parent, user: dict, on_save, data=None):
        super().__init__(parent)
        self._user    = user
        self._on_save = on_save
        self._data    = data
        is_edit = data is not None
        self.title("Editar producto" if is_edit else "Agregar producto")
        self.geometry("580x800")
        self.minsize(520, 600)
        self.resizable(True, True)
        self.grab_set()
        self.focus()
        self._build(is_edit)

    def _build(self, is_edit: bool):
        # Header
        hdr_color = theme.BTN_BLUE if is_edit else theme.BTN_GREEN
        hdr = ctk.CTkFrame(self, fg_color=hdr_color, height=56, corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,
                     text="✏  Editar producto" if is_edit else "＋  Nuevo producto",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=16)

        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        frm = ctk.CTkFrame(scroll, fg_color="transparent")
        frm.pack(fill="x", padx=28, pady=(12, 4))

        def sec(title):
            ctk.CTkLabel(frm, text=title,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=theme.TEXT_DIM).pack(anchor="w", pady=(14, 0))
            ctk.CTkFrame(frm, height=1, fg_color=theme.SEP).pack(fill="x", pady=(2, 4))

        def lbl(text):
            ctk.CTkLabel(frm, text=text, anchor="w",
                         text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", pady=(6, 0))

        # ── Info básica ────────────────────────────────────
        sec("INFORMACIÓN BÁSICA")

        lbl("Nombre del producto *")
        self._name = ctk.CTkEntry(frm, placeholder_text="Ej: Coca Cola 500ml", height=34)
        self._name.pack(fill="x", pady=(2, 0))

        lbl("Código de barras (EAN / UPC)")
        self._barcode = ctk.CTkEntry(frm, placeholder_text="EAN / UPC", height=34)
        self._barcode.pack(fill="x", pady=(2, 0))

        # Categoría + Proveedor en fila
        cp_row = ctk.CTkFrame(frm, fg_color="transparent")
        cp_row.pack(fill="x", pady=(6, 0))
        cp_row.columnconfigure(0, weight=1); cp_row.columnconfigure(1, weight=1)

        cl = ctk.CTkFrame(cp_row, fg_color="transparent")
        cl.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(cl, text="Categoría *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        cats = _get_cats()
        self._cat_var = ctk.StringVar(value=cats[0] if cats else "")
        self._cat_menu_dlg = ctk.CTkOptionMenu(cl, variable=self._cat_var,
                                               values=cats, height=32,
                                               command=self._update_preview)
        self._cat_menu_dlg.pack(fill="x", pady=(2, 0))

        cr_f = ctk.CTkFrame(cp_row, fg_color="transparent")
        cr_f.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(cr_f, text="Proveedor *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        suppliers     = api.get_all_suppliers()
        self._sup_map = {s[1]: s[0] for s in suppliers}
        sup_names     = list(self._sup_map.keys())
        self._sup_var = ctk.StringVar(value=sup_names[0] if sup_names else "")
        ctk.CTkOptionMenu(cr_f, variable=self._sup_var,
                          values=sup_names or ["Sin proveedores"],
                          height=32).pack(fill="x", pady=(2, 0))

        # ── Precios ────────────────────────────────────────
        sec("PRECIOS Y MARGEN")

        # Costo y precio en fila
        pr_row = ctk.CTkFrame(frm, fg_color="transparent")
        pr_row.pack(fill="x", pady=(4, 0))
        pr_row.columnconfigure(0, weight=1); pr_row.columnconfigure(1, weight=1)

        pl2 = ctk.CTkFrame(pr_row, fg_color="transparent")
        pl2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(pl2, text="Precio de costo *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._cost = ctk.CTkEntry(pl2, placeholder_text="0.00", height=34)
        self._cost.pack(fill="x", pady=(2, 0))
        self._cost.bind("<KeyRelease>", lambda _: self._update_preview())

        pr2 = ctk.CTkFrame(pr_row, fg_color="transparent")
        pr2.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(pr2, text="Precio de venta (dejar vacío = auto)", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._price_override = ctk.CTkEntry(pr2, placeholder_text="auto", height=34)
        self._price_override.pack(fill="x", pady=(2, 0))
        self._price_override.bind("<KeyRelease>", lambda _: self._update_preview())

        lbl("Margen personalizado (%) — vacío = jerarquía automática")
        self._margin = ctk.CTkEntry(frm, placeholder_text="vacío = usar jerarquía",
                                     width=200, height=34)
        self._margin.pack(anchor="w", pady=(2, 0))
        self._margin.bind("<KeyRelease>", lambda _: self._update_preview())

        # Preview de precio
        self._preview_frame = ctk.CTkFrame(frm, fg_color=theme.CARD2, corner_radius=8)
        self._preview_frame.pack(fill="x", pady=(6, 0))
        self._preview_lbl = ctk.CTkLabel(self._preview_frame, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=theme.C_GREEN)
        self._preview_lbl.pack(anchor="w", padx=12, pady=8)

        # ── Stock ──────────────────────────────────────────
        sec("STOCK")

        st_row = ctk.CTkFrame(frm, fg_color="transparent")
        st_row.pack(fill="x", pady=(4, 0))
        st_row.columnconfigure(0, weight=1); st_row.columnconfigure(1, weight=1)

        sl2 = ctk.CTkFrame(st_row, fg_color="transparent")
        sl2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(sl2, text="Stock actual *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._stock = ctk.CTkEntry(sl2, placeholder_text="0", height=34)
        self._stock.pack(fill="x", pady=(2, 0))

        sr2 = ctk.CTkFrame(st_row, fg_color="transparent")
        sr2.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(sr2, text="Costo de reposición (opcional)", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._repl_cost = ctk.CTkEntry(sr2, placeholder_text="0.00", height=34)
        self._repl_cost.pack(fill="x", pady=(2, 0))

        # ── Notas ──────────────────────────────────────────
        sec("NOTAS INTERNAS")

        self._notes = ctk.CTkTextbox(frm, height=70, corner_radius=8,
                                      border_width=1, border_color=theme.SEP,
                                      font=ctk.CTkFont(size=11))
        self._notes.pack(fill="x", pady=(4, 0))

        self._err = ctk.CTkLabel(frm, text="", text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11), wraplength=500)
        self._err.pack(pady=(8, 0))

        btn_color = theme.BTN_BLUE if is_edit else theme.BTN_GREEN
        btn_hover = theme.BTN_BLUEH if is_edit else theme.BTN_GREENH
        ctk.CTkButton(
            frm,
            text="Guardar cambios" if is_edit else "Agregar producto",
            height=44, fg_color=btn_color, hover_color=btn_hover,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save
        ).pack(fill="x", pady=(12, 20))

        # ── Pre-cargar si edición ──
        if is_edit and self._data:
            (id_, name, cat, cost, price, custom_margin, stock, id_supplier, *rest) = self._data
            barcode = rest[0] if rest else None

            self._name.insert(0, name)
            if barcode:
                self._barcode.insert(0, barcode)
            if cat in cats:
                self._cat_var.set(cat)
            self._cost.insert(0, str(cost))
            if custom_margin is not None:
                self._margin.insert(0, str(custom_margin))
            self._stock.insert(0, str(stock))
            # Precio override: valor actual
            self._price_override.insert(0, f"{float(price or 0):.2f}")
            sup_row = api.get_supplier_by_id(id_supplier)
            if sup_row and sup_row[1] in self._sup_map:
                self._sup_var.set(sup_row[1])
            # Costo de reposición
            try:
                from db import execute_query
                repl = execute_query(
                    "SELECT replacement_cost FROM products WHERE idProduct=%s",
                    (id_,), fetch="one")
                if repl and repl[0]:
                    self._repl_cost.insert(0, str(repl[0]))
            except Exception:
                pass

            self._update_preview()

    def _update_preview(self, _=None):
        try:
            cost = float(self._cost.get())
        except Exception:
            self._preview_lbl.configure(text="")
            return

        ov = self._price_override.get().strip()
        if ov:
            try:
                prc  = float(ov)
                gain = prc - cost
                m    = round((gain / cost * 100), 1) if cost > 0 else 0
                self._preview_lbl.configure(
                    text=f"Precio manual: ${prc:,.2f}  |  Ganancia: ${gain:,.2f}  ({m}%)")
                return
            except Exception:
                pass

        m_txt = self._margin.get().strip()
        if m_txt:
            try:
                m   = float(m_txt)
                prc = round(cost * (1 + m / 100), 2)
                self._preview_lbl.configure(
                    text=f"Precio: ${prc:,.2f}  |  Margen propio: {m}%")
            except Exception:
                pass
        else:
            try:
                prc, src, m = api.calculate_sell_price_hierarchy(cost, self._cat_var.get())
                self._preview_lbl.configure(
                    text=f"Precio: ${prc:,.2f}  |  Fuente: {src}  ({m:.1f}%)")
            except Exception:
                pass

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._err.configure(text="El nombre es obligatorio."); return
        try:
            cost = float(self._cost.get()); assert cost >= 0
        except Exception:
            self._err.configure(text="Costo inválido."); return
        try:
            stock = int(self._stock.get()); assert stock >= 0
        except Exception:
            self._err.configure(text="Stock inválido."); return

        m_txt = self._margin.get().strip()
        custom_margin = None
        if m_txt:
            try:
                custom_margin = float(m_txt)
            except ValueError:
                self._err.configure(text="Margen inválido."); return

        # Precio: override manual > jerarquía calculada
        ov = self._price_override.get().strip()
        if ov:
            try:
                price = float(ov); assert price > 0
            except Exception:
                self._err.configure(text="Precio de venta inválido."); return
        else:
            _, __, margin = api.calculate_sell_price_hierarchy(cost, self._cat_var.get(), None)
            eff_margin = custom_margin if custom_margin is not None else margin
            price = round(cost * (1 + eff_margin / 100), 2)

        barcode     = self._barcode.get().strip() or None
        cat         = self._cat_var.get()
        id_supplier = self._sup_map.get(self._sup_var.get())
        if not id_supplier:
            self._err.configure(text="Seleccioná un proveedor."); return

        repl_cost = None
        repl_txt  = self._repl_cost.get().strip()
        if repl_txt:
            try:
                repl_cost = float(repl_txt); assert repl_cost >= 0
            except Exception:
                self._err.configure(text="Costo de reposición inválido."); return

        try:
            if self._data:
                api.update_product(self._data[0], name, cat, cost, price,
                                   custom_margin, stock, id_supplier)
                api.update_product_barcode(self._data[0], barcode)
                if repl_cost is not None:
                    api.update_product_replacement_cost(self._data[0], repl_cost)
            else:
                id_p = api.add_product(name, cat, cost, price,
                                       custom_margin, stock, id_supplier)
                if barcode:
                    api.update_product_barcode(id_p, barcode)
                if repl_cost is not None:
                    api.update_product_replacement_cost(id_p, repl_cost)
        except Exception as e:
            self._err.configure(text=f"{e}"); return

        self._on_save()
        self.destroy()
