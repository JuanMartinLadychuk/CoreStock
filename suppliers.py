"""suppliers.py – CRUD de proveedores."""
import customtkinter as ctk
from tkinter import ttk, messagebox
import api, theme
import widgets as W


class SuppliersFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user     = user
        self.perms    = user.get("permissions", {})
        self._sel_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        extra = []
        if self.perms.get("agregar_proveedor"):
            extra.append(dict(text="Agregar", width=110, fg_color=theme.BTN_GREEN,
                              hover_color=theme.BTN_GREENH, command=self._add))
        if self.perms.get("editar_proveedor"):
            extra.append(dict(text="Editar", width=100, fg_color=theme.BTN_BLUE,
                              hover_color=theme.BTN_BLUEH, command=self._edit))
        if self.perms.get("eliminar_proveedor"):
            extra.append(dict(text="Eliminar", width=110, fg_color=theme.BTN_RED,
                              hover_color=theme.BTN_REDH, command=self._delete))
        W.page_header(self, "Proveedores", extra_btns=extra)

        bar = W.filter_bar(self)
        ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=15)).pack(
            side="left", padx=(12, 4), pady=8)
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._load())
        ctk.CTkEntry(bar, textvariable=self._search_var, placeholder_text="Buscar proveedor…",
                     width=280, height=34, border_width=0,
                     fg_color="transparent").pack(side="left")

        cols    = ("ID", "Proveedor", "Ciudad", "Email", "Teléfono")
        widths  = [55, 270, 160, 210, 150]
        anchors = ["center", "w", "center", "w", "center"]
        self._tf, self.tree = W.make_tree(self, cols, widths, anchors, height=20)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _: self._edit())
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._status = ctk.CTkLabel(self, text="", text_color=theme.TEXT_DIM,
                                     font=ctk.CTkFont(size=11))
        self._status.pack(anchor="w", padx=28, pady=(0, 8))

    def _refresh_treeview_style(self):
        self.tree.configure(style="Cs.Treeview")

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        rows = api.get_all_suppliers(search=self._search_var.get().strip()) or []
        for row in rows:
            self.tree.insert("", "end", values=row)
        self._status.configure(text=f"{len(rows)} proveedor(es)")

    def _on_select(self, _=None):
        sel = self.tree.selection()
        self._sel_id = int(self.tree.item(sel[0])["values"][0]) if sel else None

    def _add(self):
        SupplierDialog(self, title="Agregar Proveedor",
                       on_save=lambda d: (api.add_supplier(**d), self._load()))

    def _edit(self):
        if not self._sel_id:
            messagebox.showwarning("Sin selección", "Seleccioná un proveedor primero."); return
        data = api.get_supplier_by_id(self._sel_id)
        if data:
            SupplierDialog(self, title="Editar Proveedor", data=data,
                           on_save=lambda d: (api.update_supplier(self._sel_id, **d), self._load()))

    def _delete(self):
        if not self._sel_id:
            messagebox.showwarning("Sin selección", "Seleccioná un proveedor primero."); return
        if messagebox.askyesno("Eliminar", "¿Eliminar el proveedor seleccionado?"):
            try:
                api.delete_supplier(self._sel_id)
                self._sel_id = None
                self._load()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def on_show(self):
        self._load()


class SupplierDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, on_save, data=None):
        super().__init__(parent)
        self._on_save = on_save
        self._data    = data
        self.title(title)
        self.geometry("440x420")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 2))
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=(0, 12))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28)

        self._fields = {}
        for label, key, placeholder in [
            ("Proveedor *",    "supplier", "Nombre del proveedor"),
            ("Dirección",      "address",  "Calle 123"),
            ("Ciudad",         "city",     "Ciudad"),
            ("Email",          "email",    "email@proveedor.com"),
            ("Teléfono",       "phone",    "+54 11 1234-5678"),
            ("Descripción",    "description", "Descripción breve"),
        ]:
            ctk.CTkLabel(frm, text=label, anchor="w", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(8, 0))
            e = ctk.CTkEntry(frm, placeholder_text=placeholder, height=36, corner_radius=7)
            e.pack(fill="x", pady=(2, 0))
            self._fields[key] = e

        self._err = ctk.CTkLabel(self, text="", text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(10, 0))
        ctk.CTkButton(self, text="Guardar", height=40,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      command=self._save).pack(fill="x", padx=28, pady=(6, 20))

        if data:
            vals = {
                "supplier": data[1], "address": data[2] or "",
                "city": data[5] if len(data) > 5 else "",
                "email": data[3] or "", "phone": data[4] or "",
                "description": data[6] if len(data) > 6 else "",
            }
            for key, val in vals.items():
                if key in self._fields:
                    self._fields[key].insert(0, val)

    def _save(self):
        d = {k: e.get().strip() for k, e in self._fields.items()}
        if not d["supplier"]:
            self._err.configure(text="El nombre es obligatorio."); return
        try:
            self._on_save(d)
            self.destroy()
        except Exception as e:
            self._err.configure(text=f"{e}")
