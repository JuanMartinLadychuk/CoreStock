"""roles.py – Gestion de roles y permisos granulares.
Diseno modernizado: split card layout, igual que email_suppliers / about.
"""
import customtkinter as ctk
from tkinter import messagebox
import api, theme
import widgets as W

# Grupos de permisos para mostrar agrupados visualmente
PERM_GROUPS = {
    "Ventas y Caja": [
        "registrar_venta", "eliminar_venta", "aplicar_descuento",
    ],
    "Inventario": [
        "ver_inventario", "agregar_producto", "editar_producto",
        "eliminar_producto", "ver_precio_costo", "editar_stock",
    ],
    "Proveedores": [
        "ver_proveedores", "agregar_proveedor", "editar_proveedor",
        "eliminar_proveedor",
    ],
    "Reportes y Finanzas": [
        "ver_dashboard", "ver_ventas", "ver_movimientos",
        "ver_rendimientos", "cargar_egresos",
    ],
    "Canales": [
        "ver_mercadolibre", "editar_mercadolibre",
    ],
    "Administracion": [
        "ver_configuracion", "editar_impuestos",
        "gestionar_usuarios", "gestionar_roles", "ver_emails",
    ],
}

# Colores por tipo de rol sistema
ROLE_COLORS = {
    "Administrador": "#3b82f6",
    "Empleado":      "#22c55e",
    "Cajero":        "#f97316",
    "Supervisor":    "#8b5cf6",
}


class RolesFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict, app=None):
        super().__init__(parent, fg_color="transparent")
        self.user        = user
        self._sel_id: int | None = None
        self._sel_name:  str     = ""
        self._sel_system: bool   = False
        self._perm_vars: dict    = {}
        self._role_btns: dict    = {}
        self._build_ui()

    # ══════════════════════════════════════════════════════
    #  Layout principal
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        # Header con botones
        W.page_header(self, "Roles y Permisos")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        content.columnconfigure(0, weight=1, minsize=240)
        content.columnconfigure(1, weight=3)
        content.rowconfigure(0, weight=1)

        # ── Panel izquierdo: lista de roles ───────────────
        left = ctk.CTkFrame(content, fg_color=theme.CARD, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Header del panel izquierdo
        lh = ctk.CTkFrame(left, fg_color="transparent")
        lh.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkLabel(lh, text="Roles",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(side="left")
        ctk.CTkButton(lh, text="+ Nuevo", width=70, height=28,
                      corner_radius=6,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      font=ctk.CTkFont(size=11),
                      command=self._add_role).pack(side="right")

        ctk.CTkFrame(left, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=14, pady=(0, 8))

        self._role_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color=theme.SEP,
            scrollbar_button_hover_color=theme.ACCENT_H)
        self._role_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Boton eliminar al fondo del panel izq
        ctk.CTkFrame(left, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=14, pady=(0, 6))
        self._del_btn = ctk.CTkButton(
            left, text="Eliminar rol", height=30,
            corner_radius=6, fg_color="transparent",
            hover_color=theme.BTN_RED,
            text_color=theme.C_RED,
            font=ctk.CTkFont(size=11),
            command=self._delete_role)
        self._del_btn.pack(fill="x", padx=10, pady=(0, 10))

        # ── Panel derecho: editor de permisos ────────────
        right = ctk.CTkFrame(content, fg_color=theme.CARD, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")

        # Header del panel derecho
        rh = ctk.CTkFrame(right, fg_color="transparent")
        rh.pack(fill="x", padx=14, pady=(14, 8))

        self._role_title = ctk.CTkLabel(
            rh, text="Selecciona un rol",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.TEXT_HDR)
        self._role_title.pack(side="left")

        self._save_btn = ctk.CTkButton(
            rh, text="Guardar permisos", width=150, height=34,
            corner_radius=8,
            fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
            command=self._save_permissions)
        self._save_btn.pack(side="right")

        ctk.CTkFrame(right, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=14, pady=(0, 0))

        # Info del rol seleccionado
        self._role_info = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM)
        self._role_info.pack(anchor="w", padx=16, pady=(8, 4))

        # Area scrollable de permisos
        self._perm_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent",
            scrollbar_button_color=theme.SEP,
            scrollbar_button_hover_color=theme.ACCENT_H)
        self._perm_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Placeholder inicial
        ctk.CTkLabel(
            self._perm_scroll,
            text="Selecciona un rol de la lista para\nver y editar sus permisos.",
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=12),
            justify="center").pack(expand=True, pady=60)

    # ══════════════════════════════════════════════════════
    #  Carga de roles
    # ══════════════════════════════════════════════════════
    def _load_roles(self):
        for w in self._role_list.winfo_children():
            w.destroy()
        self._role_btns = {}

        roles = api.get_all_roles()
        for id_role, name, desc, is_system, *_ in roles:
            self._render_role_card(id_role, name, desc, bool(is_system))

        # Reseleccionar el rol activo si lo habia
        if self._sel_id and self._sel_id in self._role_btns:
            self._highlight_role(self._sel_id)

    def _render_role_card(self, id_role, name, desc, is_system):
        color = ROLE_COLORS.get(name, theme.ACCENT[1]
                                if isinstance(theme.ACCENT, tuple) else theme.ACCENT)

        card = ctk.CTkFrame(
            self._role_list, fg_color=theme.CARD2,
            corner_radius=10, cursor="hand2")
        card.pack(fill="x", pady=3, padx=2)

        # Barra lateral de color
        bar = ctk.CTkFrame(card, width=4, fg_color=color, corner_radius=2)
        bar.pack(side="left", fill="y", padx=(0, 10))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, pady=10)

        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="x")

        ctk.CTkLabel(top_row, text=name,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT).pack(side="left")

        if is_system:
            ctk.CTkLabel(top_row, text="Sistema",
                         fg_color=color, corner_radius=4,
                         font=ctk.CTkFont(size=8, weight="bold"),
                         text_color="#ffffff", padx=5, pady=1).pack(
                side="left", padx=(6, 0))

        if desc:
            ctk.CTkLabel(body, text=desc,
                         font=ctk.CTkFont(size=10),
                         text_color=theme.TEXT_DIM,
                         anchor="w").pack(anchor="w", pady=(2, 0))

        # Permisos count badge
        try:
            perms      = api.get_role_permissions(id_role)
            n_active   = sum(1 for v in perms.values() if v)
            n_total    = len(perms)
            badge_color = theme.C_GREEN if n_active == n_total else theme.C_ORANGE
            ctk.CTkLabel(body,
                         text=f"{n_active}/{n_total} permisos activos",
                         font=ctk.CTkFont(size=9),
                         text_color=badge_color).pack(anchor="w", pady=(1, 0))
        except Exception:
            pass

        # Hacer clickeable toda la card
        for w in [card, bar, body, top_row]:
            w.bind("<Button-1>",
                   lambda _, r=id_role, n=name, s=is_system: self._select_role(r, n, s))

        self._role_btns[id_role] = card

    def _highlight_role(self, id_role):
        for rid, card in self._role_btns.items():
            card.configure(
                fg_color=theme.ACCENT if rid == id_role else theme.CARD2,
                border_width=0)
        if id_role in self._role_btns:
            self._role_btns[id_role].configure(
                fg_color=theme.ACCENT,
                border_width=2,
                border_color=theme.ACCENT_H)

    def _select_role(self, id_role: int, name: str, is_system: bool):
        self._sel_id     = id_role
        self._sel_name   = name
        self._sel_system = is_system
        self._highlight_role(id_role)
        self._load_permissions(id_role, name, is_system)

    # ══════════════════════════════════════════════════════
    #  Editor de permisos
    # ══════════════════════════════════════════════════════
    def _load_permissions(self, id_role: int, name: str, is_system: bool):
        for w in self._perm_scroll.winfo_children():
            w.destroy()
        self._perm_vars = {}

        is_admin = is_system and name == "Administrador"
        color    = ROLE_COLORS.get(name, theme.ACCENT[1]
                                   if isinstance(theme.ACCENT, tuple) else theme.ACCENT)

        # Titulo y estado
        self._role_title.configure(text=name, text_color=color)
        status_txt = "Rol del sistema — permisos fijos" if is_admin else \
                     "Rol del sistema — editable" if is_system else \
                     "Rol personalizado — editable"
        self._role_info.configure(text=status_txt)

        perms = api.get_role_permissions(id_role)

        # Acciones rapidas (solo si no es admin)
        if not is_admin:
            quick = ctk.CTkFrame(self._perm_scroll, fg_color=theme.CARD2,
                                 corner_radius=10)
            quick.pack(fill="x", pady=(4, 12), padx=4)
            qi = ctk.CTkFrame(quick, fg_color="transparent")
            qi.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(qi, text="Acciones rapidas:",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkButton(qi, text="Activar todos", width=110, height=28,
                          corner_radius=6,
                          fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                          font=ctk.CTkFont(size=10),
                          command=self._select_all).pack(side="left", padx=(10, 4))
            ctk.CTkButton(qi, text="Desactivar todos", width=120, height=28,
                          corner_radius=6,
                          fg_color=theme.BTN_RED, hover_color=theme.BTN_REDH,
                          font=ctk.CTkFont(size=10),
                          command=self._deselect_all).pack(side="left")

        # Renderizar grupos de permisos
        for group_name, group_keys in PERM_GROUPS.items():
            group_keys_exist = [k for k in group_keys if k in api.ALL_PERMISSIONS]
            if not group_keys_exist:
                continue

            # Card del grupo
            group_card = ctk.CTkFrame(
                self._perm_scroll, fg_color=theme.CARD2,
                corner_radius=10, border_width=1, border_color=theme.SEP)
            group_card.pack(fill="x", pady=(0, 8), padx=4)

            # Header del grupo
            gh = ctk.CTkFrame(group_card, fg_color="transparent")
            gh.pack(fill="x", padx=14, pady=(12, 4))

            n_on  = sum(1 for k in group_keys_exist if perms.get(k))
            n_tot = len(group_keys_exist)
            g_color = theme.C_GREEN if n_on == n_tot else (
                      theme.C_ORANGE if n_on > 0 else theme.TEXT_DIM[1]
                      if isinstance(theme.TEXT_DIM, tuple) else theme.TEXT_DIM)

            ctk.CTkLabel(gh, text=group_name,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.TEXT).pack(side="left")
            ctk.CTkLabel(gh, text=f"{n_on}/{n_tot}",
                         font=ctk.CTkFont(size=10),
                         text_color=g_color).pack(side="left", padx=(8, 0))

            ctk.CTkFrame(group_card, height=1, fg_color=theme.SEP).pack(
                fill="x", padx=14, pady=(4, 8))

            # Grid de checkboxes 2 columnas
            grid_f = ctk.CTkFrame(group_card, fg_color="transparent")
            grid_f.pack(fill="x", padx=14, pady=(0, 12))
            grid_f.columnconfigure((0, 1), weight=1)

            for idx, key in enumerate(group_keys_exist):
                label = api.ALL_PERMISSIONS.get(key, key)
                var   = ctk.BooleanVar(value=perms.get(key, False))

                cb_frame = ctk.CTkFrame(grid_f, fg_color="transparent")
                cb_frame.grid(row=idx // 2, column=idx % 2,
                              sticky="w", padx=8, pady=4)

                cb = ctk.CTkCheckBox(
                    cb_frame, text=label, variable=var,
                    font=ctk.CTkFont(size=11),
                    checkbox_width=18, checkbox_height=18,
                    corner_radius=4)
                cb.pack(anchor="w")

                if is_admin:
                    cb.configure(state="disabled")

                self._perm_vars[key] = var

        can_edit = not is_admin
        self._save_btn.configure(state="normal" if can_edit else "disabled")

    def _select_all(self):
        for var in self._perm_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self._perm_vars.values():
            var.set(False)

    # ══════════════════════════════════════════════════════
    #  Acciones CRUD
    # ══════════════════════════════════════════════════════
    def _save_permissions(self):
        if not self._sel_id:
            return
        api.save_role_permissions(
            self._sel_id,
            {k: v.get() for k, v in self._perm_vars.items()})
        # Feedback visual
        orig = self._save_btn.cget("text")
        self._save_btn.configure(text="Guardado", fg_color=theme.BTN_GREEN)
        self.after(1500, lambda: self._save_btn.configure(
            text=orig, fg_color=theme.BTN_GREEN))
        self._load_roles()

    def _add_role(self):
        _RoleDialog(self, on_save=self._load_roles)

    def _delete_role(self):
        if not self._sel_id:
            messagebox.showwarning("Sin seleccion", "Selecciona un rol primero.")
            return
        role = api.get_role_by_id(self._sel_id)
        if role and role["system"]:
            messagebox.showerror("Error", "No se puede eliminar un rol del sistema.")
            return
        if messagebox.askyesno("Eliminar rol",
                               f"Eliminar el rol '{role['name']}'?\nEsta accion no se puede deshacer."):
            try:
                api.delete_role(self._sel_id)
                self._sel_id     = None
                self._sel_name   = ""
                self._sel_system = False
                self._role_title.configure(text="Selecciona un rol",
                                           text_color=theme.TEXT_HDR)
                self._role_info.configure(text="")
                for w in self._perm_scroll.winfo_children():
                    w.destroy()
                self._save_btn.configure(state="disabled")
                ctk.CTkLabel(
                    self._perm_scroll,
                    text="Selecciona un rol de la lista para\nver y editar sus permisos.",
                    text_color=theme.TEXT_DIM,
                    font=ctk.CTkFont(size=12),
                    justify="center").pack(expand=True, pady=60)
                self._load_roles()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def on_show(self):
        self._load_roles()


# ══════════════════════════════════════════════════════════════
#  Dialogo: nuevo rol
# ══════════════════════════════════════════════════════════════

class _RoleDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Nuevo rol")
        self.geometry("420x300")
        self.minsize(400, 260)
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="Crear nuevo rol",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(
            padx=24, pady=(20, 16), anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(fill="x")

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="x", padx=28, pady=(20, 0))

        ctk.CTkLabel(frm, text="Nombre *", anchor="w",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x")
        self._name = ctk.CTkEntry(
            frm, placeholder_text="Ej: Supervisor de turno",
            height=38, corner_radius=8)
        self._name.pack(fill="x", pady=(4, 14))
        self._name.bind("<Return>", lambda _: self._save())

        ctk.CTkLabel(frm, text="Descripcion", anchor="w",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x")
        self._desc = ctk.CTkEntry(
            frm, placeholder_text="Descripcion breve del rol",
            height=38, corner_radius=8)
        self._desc.pack(fill="x", pady=(4, 0))

        self._err = ctk.CTkLabel(frm, text="",
                                  text_color=theme.C_RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(pady=(10, 0))

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
            fill="x", pady=(16, 0))

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=24, pady=12)
        ctk.CTkButton(foot, text="Cancelar", width=100, height=38,
                      corner_radius=8,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT_DIM,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(foot, text="Crear rol", width=120, height=38,
                      corner_radius=8,
                      fg_color=theme.BTN_GREEN, hover_color=theme.BTN_GREENH,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._err.configure(text="El nombre es obligatorio.")
            return
        api.add_role(name, self._desc.get().strip())
        self._on_save()
        self.destroy()
