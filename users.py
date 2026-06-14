"""users.py – Gestion de usuarios.
Diseno modernizado: cards con avatar, split panel, igual estilo email/about.
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import hashlib
import api, theme
import widgets as W


# Colores de avatar por rol
ROLE_COLORS = {
    "Administrador": "#3b82f6",
    "Empleado":      "#22c55e",
    "Cajero":        "#f97316",
    "Supervisor":    "#8b5cf6",
}

def _role_color(role_name: str) -> str:
    return ROLE_COLORS.get(role_name, theme.ACCENT[1]
                           if isinstance(theme.ACCENT, tuple) else theme.ACCENT)

def _initials(full_name: str, username: str) -> str:
    name = (full_name or username or "?").strip()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


class UsersFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user      = user
        self._app      = app
        self._all_rows = []
        self._sel_id: int | None = None
        self._search_var = ctk.StringVar()
        self._filter_role = ctk.StringVar(value="Todos")
        self._filter_status = ctk.StringVar(value="Activos")
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  Layout principal
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        W.page_header(self, "Usuarios")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        content.columnconfigure(0, weight=1, minsize=300)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        # ── Panel izquierdo: lista de usuarios ────────────
        left = ctk.CTkFrame(content, fg_color=theme.CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Header panel izq
        lh = ctk.CTkFrame(left, fg_color="transparent")
        lh.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkLabel(lh, text="Usuarios",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(side="left")
        ctk.CTkButton(lh, text="+ Nuevo", width=70, height=28,
                      corner_radius=6,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      font=ctk.CTkFont(size=11),
                      command=self._add).pack(side="right")

        # Buscador
        search_f = ctk.CTkFrame(left, fg_color=theme.CARD2,
                                corner_radius=8)
        search_f.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkEntry(search_f,
                     textvariable=self._search_var,
                     placeholder_text="Buscar usuario...",
                     height=32, border_width=0,
                     fg_color="transparent",
                     font=ctk.CTkFont(size=11)).pack(
            fill="x", padx=10, pady=6)
        self._search_var.trace_add("write", lambda *_: self._filter_list())

        # Filtros
        filter_f = ctk.CTkFrame(left, fg_color="transparent")
        filter_f.pack(fill="x", padx=10, pady=(0, 6))

        roles = ["Todos"] + [r[1] for r in api.get_all_roles()]
        ctk.CTkOptionMenu(filter_f, variable=self._filter_role,
                          values=roles, width=130, height=28,
                          font=ctk.CTkFont(size=10),
                          command=lambda _: self._filter_list()).pack(
            side="left", padx=(0, 4))
        ctk.CTkOptionMenu(filter_f, variable=self._filter_status,
                          values=["Todos", "Activos", "Inactivos"],
                          width=110, height=28,
                          font=ctk.CTkFont(size=10),
                          command=lambda _: self._filter_list()).pack(side="left")

        ctk.CTkFrame(left, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=14, pady=(4, 0))

        # Lista scrollable de cards
        self._user_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color=theme.SEP,
            scrollbar_button_hover_color=theme.ACCENT_H)
        self._user_list.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        # KPI al fondo izq
        ctk.CTkFrame(left, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=14, pady=(0, 6))
        self._kpi_row = ctk.CTkFrame(left, fg_color="transparent")
        self._kpi_row.pack(fill="x", padx=10, pady=(0, 10))

        # ── Panel derecho: detalle / editor ──────────────
        right = ctk.CTkFrame(content, fg_color=theme.CARD, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")

        # Placeholder inicial
        self._right_panel = right
        self._show_placeholder()

    # ══════════════════════════════════════════════════════
    #  Panel derecho — placeholder
    # ══════════════════════════════════════════════════════
    def _show_placeholder(self):
        for w in self._right_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._right_panel,
            text="Selecciona un usuario\npara ver su detalle.",
            font=ctk.CTkFont(size=13),
            text_color=theme.TEXT_DIM,
            justify="center").place(relx=0.5, rely=0.4, anchor="center")

    # ══════════════════════════════════════════════════════
    #  Panel derecho — detalle del usuario
    # ══════════════════════════════════════════════════════
    def _show_user_detail(self, row: tuple):
        for w in self._right_panel.winfo_children():
            w.destroy()

        (id_u, username, role_name, full_name,
         active, created_at, id_role, salary) = row

        color    = _role_color(role_name)
        initials = _initials(full_name, username)

        sc = ctk.CTkScrollableFrame(
            self._right_panel, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Tarjeta de perfil ────────────────────────────
        profile_card = ctk.CTkFrame(sc, fg_color=theme.CARD2,
                                     corner_radius=12)
        profile_card.pack(fill="x", padx=16, pady=(16, 10))

        pc_inner = ctk.CTkFrame(profile_card, fg_color="transparent")
        pc_inner.pack(fill="x", padx=16, pady=16)

        # Avatar circular con iniciales
        avatar = ctk.CTkFrame(pc_inner, width=64, height=64,
                               fg_color=color, corner_radius=32)
        avatar.pack(side="left")
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=initials,
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#ffffff").pack(expand=True)

        # Info basica
        info = ctk.CTkFrame(pc_inner, fg_color="transparent")
        info.pack(side="left", padx=(14, 0), fill="x", expand=True)

        ctk.CTkLabel(info, text=full_name or username,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=theme.TEXT_HDR,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=f"@{username}",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM,
                     anchor="w").pack(anchor="w", pady=(1, 4))

        badges = ctk.CTkFrame(info, fg_color="transparent")
        badges.pack(anchor="w")

        # Badge rol
        ctk.CTkLabel(badges, text=role_name or "—",
                     fg_color=color, corner_radius=6,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#ffffff", padx=8, pady=2).pack(
            side="left", padx=(0, 4))

        # Badge estado
        s_color = theme.C_GREEN if active else theme.C_RED
        s_text  = "Activo" if active else "Inactivo"
        ctk.CTkLabel(badges, text=s_text,
                     fg_color=s_color, corner_radius=6,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#ffffff", padx=8, pady=2).pack(side="left")

        # ── Stats en fila ────────────────────────────────
        stats_row = ctk.CTkFrame(sc, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=(0, 10))
        stats_row.columnconfigure((0, 1, 2), weight=1)

        for col, (lbl, val, c) in enumerate([
            ("Salario mensual", f"${float(salary or 0):,.2f}", theme.C_GREEN),
            ("Miembro desde", str(created_at)[:10] if created_at else "—", theme.C_BLUE),
            ("ID de usuario", f"#{id_u}", theme.TEXT_DIM[1]
             if isinstance(theme.TEXT_DIM, tuple) else theme.TEXT_DIM),
        ]):
            stats_row.columnconfigure(col, weight=1)
            sc_card = ctk.CTkFrame(stats_row, fg_color=theme.CARD2,
                                   corner_radius=10)
            sc_card.grid(row=0, column=col, sticky="nsew",
                         padx=(0 if col == 0 else 4, 0), pady=2)
            ctk.CTkLabel(sc_card, text=val,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=c).pack(pady=(10, 2))
            ctk.CTkLabel(sc_card, text=lbl,
                         font=ctk.CTkFont(size=9),
                         text_color=theme.TEXT_DIM).pack(pady=(0, 10))

        # ── Acciones ─────────────────────────────────────
        ctk.CTkLabel(sc, text="Acciones",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(
            anchor="w", padx=18, pady=(4, 6))

        act_card = ctk.CTkFrame(sc, fg_color=theme.CARD2, corner_radius=12)
        act_card.pack(fill="x", padx=16, pady=(0, 10))
        ac = ctk.CTkFrame(act_card, fg_color="transparent")
        ac.pack(fill="x", padx=14, pady=14)

        ctk.CTkButton(ac, text="Editar usuario", height=36,
                      corner_radius=8,
                      fg_color=theme.BTN_BLUE, hover_color=theme.BTN_BLUEH,
                      font=ctk.CTkFont(size=12),
                      command=lambda: self._edit_user(row)).pack(
            fill="x", pady=(0, 6))
        ctk.CTkButton(ac, text="Cambiar contrasena", height=36,
                      corner_radius=8,
                      fg_color=theme.BTN_PURPLE, hover_color=theme.BTN_PURPLEH,
                      font=ctk.CTkFont(size=12),
                      command=lambda: _PasswordDialog(self, id_u)).pack(
            fill="x", pady=(0, 6))

        # Toggle activar/desactivar
        toggle_text  = "Desactivar usuario" if active else "Activar usuario"
        toggle_color = theme.BTN_ORANGE if active else theme.BTN_GREEN
        toggle_hover = theme.BTN_ORANGEH if active else theme.BTN_GREENH
        ctk.CTkButton(ac, text=toggle_text, height=36,
                      corner_radius=8,
                      fg_color=toggle_color, hover_color=toggle_hover,
                      font=ctk.CTkFont(size=12),
                      command=lambda: self._toggle_active(id_u, id_role,
                                                          full_name, not active)
                      ).pack(fill="x")

        # ── Editar salario ───────────────────────────────
        ctk.CTkLabel(sc, text="Salario mensual",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT_DIM).pack(
            anchor="w", padx=18, pady=(4, 6))

        sal_card = ctk.CTkFrame(sc, fg_color=theme.CARD2, corner_radius=12)
        sal_card.pack(fill="x", padx=16, pady=(0, 16))
        si = ctk.CTkFrame(sal_card, fg_color="transparent")
        si.pack(fill="x", padx=14, pady=14)

        ctk.CTkLabel(si, text="Monto ($):",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        sal_e = ctk.CTkEntry(si, width=140, height=36,
                              justify="center",
                              font=ctk.CTkFont(size=14))
        sal_e.insert(0, f"{float(salary or 0):.2f}")
        sal_e.pack(side="left", padx=(10, 10))
        ctk.CTkButton(si, text="Guardar", width=90, height=36,
                      corner_radius=8,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      font=ctk.CTkFont(size=11),
                      command=lambda e=sal_e, uid=id_u: self._save_salary(uid, e)
                      ).pack(side="left")

    # ══════════════════════════════════════════════════════
    #  Carga y filtrado de lista
    # ══════════════════════════════════════════════════════
    def _load_users(self):
        self._all_rows = api.get_all_users_with_salary() or []
        self._filter_list()
        self._update_kpis()

    def _filter_list(self):
        for w in self._user_list.winfo_children():
            w.destroy()

        q      = self._search_var.get().strip().lower()
        role_f = self._filter_role.get()
        st_f   = self._filter_status.get()

        shown = 0
        for row in self._all_rows:
            (id_u, username, role_name, full_name,
             active, created_at, id_role, salary) = row

            if q and q not in (username or "").lower() \
                  and q not in (full_name or "").lower():
                continue
            if role_f != "Todos" and role_name != role_f:
                continue
            if st_f == "Activos"   and not active: continue
            if st_f == "Inactivos" and active:     continue

            self._render_user_card(row)
            shown += 1

        if shown == 0:
            ctk.CTkLabel(self._user_list,
                         text="Sin resultados.",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(pady=20)

    def _render_user_card(self, row: tuple):
        (id_u, username, role_name, full_name,
         active, created_at, id_role, salary) = row

        color    = _role_color(role_name)
        initials = _initials(full_name, username)
        is_me    = (id_u == self.user.get("id"))

        card = ctk.CTkFrame(
            self._user_list, fg_color=theme.CARD2,
            corner_radius=10, cursor="hand2")
        card.pack(fill="x", pady=3, padx=2)

        # Barra lateral + avatar mini
        left_bar = ctk.CTkFrame(card, fg_color="transparent")
        left_bar.pack(side="left", fill="y", padx=(8, 10), pady=8)

        ctk.CTkFrame(left_bar, width=3, fg_color=color,
                     corner_radius=2).pack(side="left", fill="y", padx=(0, 8))

        av = ctk.CTkFrame(left_bar, width=36, height=36,
                          fg_color=color, corner_radius=18)
        av.pack(side="left")
        av.pack_propagate(False)
        ctk.CTkLabel(av, text=initials,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#ffffff").pack(expand=True)

        # Info
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=8)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")
        ctk.CTkLabel(name_row,
                     text=full_name or username,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")
        if is_me:
            ctk.CTkLabel(name_row, text="Yo",
                         fg_color=theme.C_BLUE, corner_radius=4,
                         font=ctk.CTkFont(size=8, weight="bold"),
                         text_color="#ffffff", padx=4, pady=1).pack(
                side="left", padx=(5, 0))
        if not active:
            ctk.CTkLabel(name_row, text="Inactivo",
                         fg_color=theme.C_RED, corner_radius=4,
                         font=ctk.CTkFont(size=8),
                         text_color="#ffffff", padx=4, pady=1).pack(
                side="left", padx=(4, 0))

        ctk.CTkLabel(info, text=f"@{username}  •  {role_name}",
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(info, text=f"Salario: ${float(salary or 0):,.2f}/mes",
                     font=ctk.CTkFont(size=9),
                     text_color=theme.TEXT_DIM).pack(anchor="w")

        # Click en cualquier parte de la card
        for w in [card, left_bar, av, info, name_row]:
            w.bind("<Button-1>",
                   lambda _, r=row: self._select_user(r))
        for w in left_bar.winfo_children() + info.winfo_children() + name_row.winfo_children():
            try:
                w.bind("<Button-1>", lambda _, r=row: self._select_user(r))
            except Exception:
                pass

    def _select_user(self, row: tuple):
        self._sel_id = row[0]
        self._show_user_detail(row)

    # ══════════════════════════════════════════════════════
    #  KPIs al pie de la lista
    # ══════════════════════════════════════════════════════
    def _update_kpis(self):
        for w in self._kpi_row.winfo_children():
            w.destroy()
        self._kpi_row.columnconfigure((0, 1), weight=1)

        activos   = sum(1 for r in self._all_rows if r[4])
        total_sal = sum(float(r[7] or 0) for r in self._all_rows if r[4])

        for col, (lbl, val, c) in enumerate([
            ("Activos",  str(activos),         theme.C_GREEN),
            ("Nomina",   f"${total_sal:,.0f}", theme.C_ORANGE),
        ]):
            f = ctk.CTkFrame(self._kpi_row, fg_color=theme.CARD2,
                             corner_radius=8)
            f.grid(row=0, column=col, sticky="nsew",
                   padx=(0 if col == 0 else 4, 0), pady=2)
            ctk.CTkLabel(f, text=val,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=c).pack(pady=(8, 1))
            ctk.CTkLabel(f, text=lbl,
                         font=ctk.CTkFont(size=9),
                         text_color=theme.TEXT_DIM).pack(pady=(0, 8))

    # ══════════════════════════════════════════════════════
    #  Acciones
    # ══════════════════════════════════════════════════════
    def _add(self):
        _UserDialog(self, on_save=self._reload_and_refresh)

    def _edit_user(self, row: tuple):
        _UserDialog(self, data=row, on_save=self._reload_and_refresh)

    def _toggle_active(self, id_u: int, id_role: int,
                       full_name: str, new_state: bool):
        action = "activar" if new_state else "desactivar"
        if messagebox.askyesno("Confirmar",
                               f"Confirmas {action} el usuario?"):
            api.update_user(id_u, id_role, full_name, new_state)
            self._reload_and_refresh()

    def _save_salary(self, id_u: int, entry: ctk.CTkEntry):
        try:
            val = float(entry.get())
            assert val >= 0
        except Exception:
            messagebox.showerror("Error", "Monto invalido.")
            return
        api.update_user_salary(id_u, val)
        # Feedback
        orig = entry.get()
        entry.configure(border_color=theme.C_GREEN)
        self.after(1500, lambda: entry.configure(border_color=theme.SEP))
        self._reload_and_refresh()

    def _reload_and_refresh(self):
        self._load_users()
        # Reseleccionar usuario activo
        if self._sel_id:
            row = next((r for r in self._all_rows if r[0] == self._sel_id), None)
            if row:
                self._show_user_detail(row)

    def _refresh_treeview_style(self):
        pass  # sin treeview en este modulo

    def on_show(self):
        self._load_users()


# ══════════════════════════════════════════════════════════════
#  Dialogo: crear / editar usuario
# ══════════════════════════════════════════════════════════════

class _UserDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save, data=None):
        super().__init__(parent)
        self._on_save = on_save
        self._data    = data
        is_edit       = data is not None
        self.title("Editar usuario" if is_edit else "Nuevo usuario")
        self.geometry("460x560")
        self.resizable(False, True)
        self.grab_set()
        self.focus()
        self._build(is_edit)

    def _build(self, is_edit: bool):
        # Header con color
        hdr = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text="Editar usuario" if is_edit else "Nuevo usuario",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(
            padx=24, pady=(20, 16), anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x")

        sc = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sc.pack(fill="both", expand=True)
        frm = ctk.CTkFrame(sc, fg_color="transparent")
        frm.pack(fill="x", padx=28, pady=(16, 0))

        def lbl(t):
            ctk.CTkLabel(frm, text=t, anchor="w",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(10, 0))

        lbl("Usuario *")
        self._uname = ctk.CTkEntry(frm, height=38, corner_radius=8)
        self._uname.pack(fill="x", pady=(4, 0))

        lbl("Nombre completo")
        self._fname = ctk.CTkEntry(
            frm, placeholder_text="Nombre Apellido",
            height=38, corner_radius=8)
        self._fname.pack(fill="x", pady=(4, 0))

        lbl("Rol *")
        roles = api.get_all_roles()
        self._role_map  = {r[1]: r[0] for r in roles}
        self._role_var  = ctk.StringVar(
            value=list(self._role_map)[0] if self._role_map else "")
        ctk.CTkOptionMenu(frm, variable=self._role_var,
                          values=list(self._role_map),
                          height=38, corner_radius=8).pack(
            fill="x", pady=(4, 0))

        lbl("Salario mensual ($)")
        self._salary = ctk.CTkEntry(
            frm, placeholder_text="0.00", width=160,
            height=38, corner_radius=8)
        self._salary.pack(anchor="w", pady=(4, 0))

        if not is_edit:
            lbl("Contrasena *")
            self._pw = ctk.CTkEntry(
                frm, show="*", height=38, corner_radius=8,
                placeholder_text="Minimo 4 caracteres")
            self._pw.pack(fill="x", pady=(4, 0))

        if is_edit:
            self._active_var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(frm, text="Usuario activo",
                                  variable=self._active_var,
                                  font=ctk.CTkFont(size=12))
            cb.pack(anchor="w", pady=(14, 0))

        self._err = ctk.CTkLabel(frm, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11),
                                  wraplength=380)
        self._err.pack(pady=(12, 0))

        # Botones al pie
        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
            fill="x", pady=(0, 0))
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=24, pady=12)
        ctk.CTkButton(foot, text="Cancelar", width=100, height=38,
                      corner_radius=8,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(foot,
                      text="Guardar cambios" if is_edit else "Crear usuario",
                      width=150, height=38, corner_radius=8,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

        # Pre-cargar si edicion
        if is_edit and self._data:
            (id_, username, role_name, full_name,
             active, created_at, id_role, salary) = self._data
            self._uname.insert(0, username)
            self._uname.configure(state="disabled")
            self._fname.insert(0, full_name or "")
            if role_name in self._role_map:
                self._role_var.set(role_name)
            self._salary.insert(0, f"{float(salary or 0):.2f}")
            self._active_var.set(bool(active))

    def _save(self):
        uname = self._uname.get().strip()
        if not uname:
            self._err.configure(text="El usuario es obligatorio."); return
        id_role = self._role_map.get(self._role_var.get())
        if not id_role:
            self._err.configure(text="Selecciona un rol."); return
        try:
            salary = float(self._salary.get() or "0")
            assert salary >= 0
        except Exception:
            self._err.configure(text="Salario invalido."); return

        if self._data:
            api.update_user(self._data[0], id_role,
                            self._fname.get().strip(),
                            self._active_var.get())
            api.update_user_salary(self._data[0], salary)
        else:
            pw = self._pw.get()
            if len(pw) < 4:
                self._err.configure(text="Contrasena minima 4 caracteres."); return
            uid = api.add_user(
                uname,
                hashlib.sha256(pw.encode()).hexdigest(),
                id_role,
                self._fname.get().strip())
            api.update_user_salary(uid, salary)

        self._on_save()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  Dialogo: cambiar contrasena
# ══════════════════════════════════════════════════════════════

class _PasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, id_user: int):
        super().__init__(parent)
        self._id_user = id_user
        self.title("Cambiar contrasena")
        self.geometry("400x320")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=theme.BTN_PURPLE, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="Cambiar contrasena",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#ffffff").pack(
            padx=24, pady=(16, 14), anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x")

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28, pady=20)

        for label, attr in [
            ("Nueva contrasena *", "_pw1"),
            ("Repetir contrasena *", "_pw2"),
        ]:
            ctk.CTkLabel(frm, text=label, anchor="w",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            e = ctk.CTkEntry(frm, show="*", height=38, corner_radius=8)
            e.pack(fill="x", pady=(4, 12))
            setattr(self, attr, e)

        self._err = ctk.CTkLabel(self, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(0, 4))

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x")
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=24, pady=12)
        ctk.CTkButton(foot, text="Cancelar", width=100, height=38,
                      corner_radius=8,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(foot, text="Cambiar", width=130, height=38,
                      corner_radius=8,
                      fg_color=theme.BTN_PURPLE, hover_color=theme.BTN_PURPLEH,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

    def _save(self):
        p1, p2 = self._pw1.get(), self._pw2.get()
        if p1 != p2:
            self._err.configure(text="Las contrasenas no coinciden."); return
        if len(p1) < 4:
            self._err.configure(text="Minimo 4 caracteres."); return
        api.update_user_password(
            self._id_user,
            hashlib.sha256(p1.encode()).hexdigest())
        messagebox.showinfo("Listo", "Contrasena actualizada correctamente.")
        self.destroy()
