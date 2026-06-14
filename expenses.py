"""
expenses.py - Modulo de Gastos Fijos y Variables.
Permite registrar, editar y eliminar gastos operativos
que se usan en el calculo de rendimiento real.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import date
import api, theme
import widgets as W


EXPENSE_CATEGORIES = [
    "General", "Alquiler", "Sueldos", "Servicios",
    "Packaging", "Envios", "Mantenimiento", "Publicidad",
    "Impuestos fijos", "Roturas / Merma", "Faltante de caja", "Otro",
]


class ExpensesFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user  = user
        self.perms = user.get("permissions", {})
        self._sel_id: int | None = None
        self._rows: list = []
        self._build_ui()

    def _build_ui(self):
        can_edit = self.perms.get("ver_configuracion", True)

        extra = []
        if can_edit:
            extra = [
                dict(text="Eliminar", width=90, fg_color=theme.BTN_RED,
                     hover_color=theme.BTN_REDH, command=self._delete),
                dict(text="Editar", width=80, fg_color=theme.BTN_BLUE,
                     hover_color=theme.BTN_BLUEH, command=self._edit),
                dict(text="Nuevo gasto", width=110, fg_color=theme.BTN_GREEN,
                     hover_color=theme.BTN_GREENH, command=self._add),
            ]
        W.page_header(self, "Gastos Operativos", extra_btns=extra)

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
        ctk.CTkLabel(bar, text="Tipo:", text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 4))
        self._type_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(bar, variable=self._type_var,
                          values=["Todos", "fijo", "variable"],
                          width=110, height=32,
                          command=lambda _: self._load()).pack(side="left")

        self._total_lbl = ctk.CTkLabel(bar, text="", text_color=theme.TEXT_DIM,
                                        font=ctk.CTkFont(size=11))
        self._total_lbl.pack(side="right", padx=16)

        # Tabla
        cols    = ("ID", "Descripcion", "Categoria", "Tipo", "Monto", "Fecha", "Registrado por")
        widths  = [50, 260, 130, 90, 120, 110, 140]
        anchors = ["center", "w", "center", "center", "e", "center", "center"]
        self._tf, self._tree = W.make_tree(self, cols, widths, anchors, height=18)
        self._tree.tag_configure("fijo",     foreground=theme.C_BLUE)
        self._tree.tag_configure("variable", foreground=theme.C_ORANGE)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit())
        self._tf.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    def _refresh_treeview_style(self):
        self._tree.configure(style="Cs.Treeview")

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        try:
            month = int(self._month_var.get())
            year  = int(self._year_var.get())
        except ValueError:
            return

        type_f = self._type_var.get()
        if type_f == "Todos":
            type_f = ""
        self._rows = api.get_expenses(month=month, year=year, type_filter=type_f)
        total = 0.0
        for row in self._rows:
            (id_e, desc, amount, type_, cat, pm, py, edate, username, notes) = row
            total += float(amount)
            self._tree.insert("", "end", iid=str(id_e), values=(
                id_e, desc[:60], cat or "General",
                type_.capitalize(), f"${float(amount):,.2f}",
                str(edate)[:10], username,
            ), tags=(type_,))
        self._total_lbl.configure(
            text=f"{len(self._rows)} registros | Total: ${total:,.2f}")
        self._refresh_kpis(month, year)

    def _refresh_kpis(self, month: int, year: int):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        totals = api.get_expense_total_month(month, year)
        for col, (label, val, color) in enumerate([
            ("Gastos fijos",     totals["fixed"],    theme.C_BLUE),
            ("Gastos variables", totals["variable"], theme.C_ORANGE),
            ("Total del mes",    totals["total"],    theme.C_RED),
        ]):
            W.kpi_card(self._kpi_row, "", label, f"${val:,.2f}", "", color, col)

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._sel_id = int(sel[0]) if sel else None

    def _add(self):
        ExpenseDialog(self, user=self.user, on_save=self._load)

    def _edit(self):
        if not self._sel_id:
            messagebox.showwarning("Sin seleccion", "Selecciona un gasto primero.")
            return
        row = next((r for r in self._rows if r[0] == self._sel_id), None)
        if row:
            ExpenseDialog(self, user=self.user, data=row, on_save=self._load)

    def _delete(self):
        if not self._sel_id:
            messagebox.showwarning("Sin seleccion", "Selecciona un gasto primero.")
            return
        if messagebox.askyesno("Eliminar gasto", "Confirmar eliminacion?"):
            api.delete_expense(self._sel_id)
            self._sel_id = None
            self._load()

    def on_show(self):
        self._load()


class ExpenseDialog(ctk.CTkToplevel):
    def __init__(self, parent, user: dict, on_save, data=None):
        super().__init__(parent)
        self._user    = user
        self._on_save = on_save
        self._data    = data
        is_edit = data is not None
        self.title("Editar gasto" if is_edit else "Registrar gasto")
        self.geometry("460x500")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build(is_edit)

    def _build(self, is_edit: bool):
        ctk.CTkLabel(self, text="Editar gasto" if is_edit else "Registrar gasto",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 2))
        ctk.CTkFrame(self, height=1, fg_color=theme.DIV).pack(fill="x", padx=20, pady=(0, 12))

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28)

        def lbl(t):
            ctk.CTkLabel(frm, text=t, anchor="w", text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(8, 0))

        lbl("Descripcion *")
        self._desc = ctk.CTkEntry(frm, placeholder_text="Ej: Alquiler enero", height=36)
        self._desc.pack(fill="x", pady=(2, 0))

        lbl("Monto *")
        self._amount = ctk.CTkEntry(frm, placeholder_text="0.00", width=160, height=36)
        self._amount.pack(anchor="w", pady=(2, 0))

        lbl("Tipo")
        self._type_var = ctk.StringVar(value="variable")
        type_row = ctk.CTkFrame(frm, fg_color="transparent")
        type_row.pack(anchor="w", pady=(4, 0))
        ctk.CTkRadioButton(type_row, text="Fijo (mensual recurrente)",
                            variable=self._type_var, value="fijo",
                            font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkRadioButton(type_row, text="Variable",
                            variable=self._type_var, value="variable",
                            font=ctk.CTkFont(size=12)).pack(side="left", padx=16)

        lbl("Categoria")
        self._cat_var = ctk.StringVar(value="General")
        ctk.CTkOptionMenu(frm, variable=self._cat_var,
                          values=EXPENSE_CATEGORIES, width=240, height=32,
                          ).pack(anchor="w", pady=(2, 0))

        lbl("Fecha")
        self._date_e = ctk.CTkEntry(frm, placeholder_text="AAAA-MM-DD",
                                     width=160, height=36)
        self._date_e.insert(0, str(date.today()))
        self._date_e.pack(anchor="w", pady=(2, 0))

        lbl("Notas")
        self._notes = ctk.CTkEntry(frm, placeholder_text="Opcional", height=36)
        self._notes.pack(fill="x", pady=(2, 0))

        self._err = ctk.CTkLabel(self, text="", text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(10, 0))
        ctk.CTkButton(
            self,
            text="Guardar cambios" if is_edit else "Registrar gasto",
            height=40, fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
            command=self._save,
        ).pack(fill="x", padx=28, pady=(6, 20))

        if is_edit and self._data:
            (id_e, desc, amount, type_, cat, pm, py, edate, username, notes) = self._data
            self._desc.insert(0, desc)
            self._amount.insert(0, str(float(amount)))
            self._type_var.set(type_)
            if cat in EXPENSE_CATEGORIES:
                self._cat_var.set(cat)
            self._date_e.delete(0, "end")
            self._date_e.insert(0, str(edate)[:10])
            if notes:
                self._notes.insert(0, notes)

    def _save(self):
        desc = self._desc.get().strip()
        if not desc:
            self._err.configure(text="La descripcion es obligatoria."); return
        try:
            amount = float(self._amount.get()); assert amount > 0
        except Exception:
            self._err.configure(text="Monto invalido."); return
        edate = self._date_e.get().strip()
        if not edate:
            self._err.configure(text="La fecha es obligatoria."); return
        try:
            from datetime import datetime
            dt = datetime.strptime(edate, "%Y-%m-%d")
        except ValueError:
            self._err.configure(text="Formato de fecha: AAAA-MM-DD"); return

        if self._data:
            api.update_expense(
                self._data[0], desc, amount,
                self._type_var.get(), self._cat_var.get(), edate,
                dt.month, dt.year, self._notes.get().strip(),
            )
        else:
            api.add_expense(
                description=desc, amount=amount,
                type_=self._type_var.get(), category=self._cat_var.get(),
                expense_date=edate, period_month=dt.month, period_year=dt.year,
                notes=self._notes.get().strip(), id_user=self._user.get("id"),
            )
        self._on_save()
        self.destroy()
