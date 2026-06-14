"""categories.py – CRUD de categorías dinámicas."""
import customtkinter as ctk
from tkinter import ttk, messagebox, colorchooser
import api, theme
import widgets as W

PRESET_COLORS = ["#4fc3f7","#4caf50","#ffa726","#ef5350",
                  "#ab47bc","#26c6da","#ff7043","#66bb6a"]


class CategoriesFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, embedded: bool = False):
        super().__init__(parent, fg_color="transparent")
        self.user     = user
        self.perms    = user.get("permissions", {})
        self.embedded = embedded
        self._selected: str | None = None
        self._build_ui()

    def _build_ui(self):
        if not self.embedded:
            W.page_header(self, "Categorias")

        can_edit = self.perms.get("ver_configuracion") or self.perms.get("editar_producto")
        pad_x = 0 if self.embedded else 24

        cols    = ("Nombre", "Descripción", "Color", "Productos")
        widths  = [180, 280, 80, 100]
        self._tf, self._tree = W.make_tree(self, cols, widths, height=14)
        self._tree.bind("<<TreeviewSelect>>",
                        lambda _: setattr(self, "_selected",
                                          self._tree.selection()[0] if self._tree.selection() else None))
        self._tree.bind("<Double-1>", lambda _: self._edit())
        self._tf.pack(fill="both", expand=True, padx=pad_x, pady=(0, 8))

        if can_edit:
            btn_row = ctk.CTkFrame(self, fg_color="transparent")
            btn_row.pack(fill="x", padx=pad_x, pady=(0, 8))
            W.action_btn(btn_row, "Nueva", theme.BTN_GREEN, theme.BTN_GREENH,
                         width=140, command=self._add).pack(side="left", padx=(0, 6))
            W.action_btn(btn_row, "Editar", theme.BTN_BLUE, theme.BTN_BLUEH,
                         width=100, command=self._edit).pack(side="left", padx=(0, 6))
            W.action_btn(btn_row, "Eliminar", theme.BTN_RED, theme.BTN_REDH,
                         width=110, command=self._delete).pack(side="left")

        self._load()

    def _refresh_treeview_style(self):
        self._tree.configure(style="Cs.Treeview")

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        for name, desc, color, count in api.get_category_details():
            self._tree.insert("", "end", iid=name,
                              values=(name, desc or "—", color or "—", count))

    def _add(self):
        CategoryDialog(self, on_save=self._load)

    def _edit(self):
        if not self._selected:
            messagebox.showwarning("Sin selección", "Seleccioná una categoría."); return
        rows = api.get_category_details()
        data = next((r for r in rows if r[0] == self._selected), None)
        if data:
            CategoryDialog(self, data=data, on_save=self._load)

    def _delete(self):
        if not self._selected:
            messagebox.showwarning("Sin selección", "Seleccioná una categoría."); return
        rows = api.get_category_details()
        data = next((r for r in rows if r[0] == self._selected), None)
        if data and data[3] > 0:
            messagebox.showerror("No se puede eliminar",
                                 f"La categoría tiene {data[3]} productos activos.")
            return
        if messagebox.askyesno("Eliminar", f"¿Eliminar '{self._selected}'?"):
            api.delete_category(self._selected)
            self._selected = None
            self._load()

    def on_show(self):
        self._load()


class CategoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save, data=None):
        super().__init__(parent)
        self._on_save = on_save
        self._data    = data
        is_edit = data is not None
        self.title("Editar categoría" if is_edit else "Nueva categoría")
        self.geometry("420x320")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._color = data[2] if data and data[2] else "#4fc3f7"
        self._build(is_edit)

    def _build(self, is_edit: bool):
        ctk.CTkLabel(self, text="Editar categoría" if is_edit else "Nueva categoría",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 2))
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=(0, 12))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28)

        ctk.CTkLabel(frm, text="Nombre *", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(fill="x")
        self._name = ctk.CTkEntry(frm, placeholder_text="Ej: Bebidas", height=36)
        self._name.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(frm, text="Descripción", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(fill="x")
        self._desc = ctk.CTkEntry(frm, placeholder_text="Opcional", height=36)
        self._desc.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(frm, text="Color de etiqueta", anchor="w",
                     text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11)).pack(fill="x")
        cr = ctk.CTkFrame(frm, fg_color="transparent")
        cr.pack(fill="x", pady=(4, 0))
        self._preview = ctk.CTkFrame(cr, width=32, height=32, corner_radius=6,
                                      fg_color=self._color)
        self._preview.pack(side="left", padx=(0, 8))
        for clr in PRESET_COLORS:
            dot = ctk.CTkFrame(cr, width=22, height=22, corner_radius=11,
                               fg_color=clr, cursor="hand2")
            dot.pack(side="left", padx=2)
            dot.bind("<Button-1>", lambda e, c=clr: self._set_color(c))
        ctk.CTkButton(cr, text="…", width=32, height=28,
                      command=self._pick_color).pack(side="left", padx=6)

        self._err = ctk.CTkLabel(self, text="", text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(10, 0))
        ctk.CTkButton(self, text="Guardar" if is_edit else "Crear",
                      height=40, fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._save).pack(fill="x", padx=28, pady=(6, 20))

        if is_edit and self._data:
            self._name.insert(0, self._data[0])
            if self._data[1]:
                self._desc.insert(0, self._data[1])
            self._name.configure(state="disabled")

    def _set_color(self, c: str):
        self._color = c
        self._preview.configure(fg_color=c)

    def _pick_color(self):
        res = colorchooser.askcolor(color=self._color, title="Elegí un color")
        if res and res[1]:
            self._set_color(res[1])

    def _save(self):
        name = self._data[0] if self._data else self._name.get().strip()
        if not name:
            self._err.configure(text="El nombre es obligatorio."); return
        desc = self._desc.get().strip()
        if self._data:
            from db import execute_query
            execute_query("UPDATE categories SET description=%s,color=%s WHERE name=%s",
                          (desc, self._color, name))
        else:
            try:
                api.add_category(name, desc, self._color)
            except Exception as e:
                self._err.configure(text=f"{e}"); return
        self._on_save()
        self.destroy()
