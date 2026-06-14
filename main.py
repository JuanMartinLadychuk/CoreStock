"""main.py - CoreStack Pro v0.9
Sidebar modernizada con grupos, iconos, avatar y badge.
SQLite + LAN server via ensure_db().
"""

from tkinter import messagebox
import customtkinter as ctk
import hashlib, importlib, traceback, threading
import api, theme

# ── Inicializar DB SQLite (solo en modo server, primera vez) ───
from init_db import ensure_db
ensure_db()

from mercadolibre import MercadolibreFrame

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Registro de frames ─────────────────────────────────────────
FRAME_REGISTRY = [
    ("dashboard",      "ver_dashboard",        "dashboard",       "DashboardFrame",      "Dashboard",     "🏠"),
    ("pos",            "registrar_venta",       "pos",             "POSFrame",            "POS / Caja",    "🛒"),
    ("inventory",      "ver_inventario",        "inventory",       "InventoryFrame",      "Inventario",    "📦"),
    ("sales",          "ver_ventas",            "sales",           "SalesFrame",          "Ventas",        "🧾"),
    ("dispatch",       "ver_ventas",            "dispatch",        "DispatchFrame",       "Despacho",      "📦"),
    ("suppliers",      "ver_proveedores",       "suppliers",       "SuppliersFrame",      "Proveedores",   "🚚"),
    ("plans", "ver_configuracion", "plans", "PlansFrame", "Planes", "💎"),
    ("analytics",      None,                    "analytics",       "AnalyticsFrame",      "Rendimiento",   "📊"),
    ("mercadolibre",   "ver_mercadolibre",      None,              None,                  "MercadoLibre",  "🛍"),
    ("categories",     "ver_configuracion",     "categories",      "CategoriesFrame",     "Categorías",    "🏷"),
    ("config",         "ver_configuracion",     "config",          "ConfigFrame",         "Configuración", "⚙"),
    ("users",          "gestionar_usuarios",    "users",           "UsersFrame",          "Usuarios",      "👥"),
    ("roles",          "gestionar_roles",       "roles",           "RolesFrame",          "Roles",         "🛡"),
    ("emails",         "ver_emails",            "email_suppliers", "EmailFrame",          "Emails",        "✉"),
    ("about",          None,                    "about",           "AboutFrame",          "Acerca de",     "ℹ"),
]

NAV_GROUPS = {
    "GESTIÓN":        ["dashboard", "pos"],
    "INVENTARIO":     ["inventory", "sales", "suppliers"],
    "LOGÍSTICA":      ["dispatch"],
    "ANÁLISIS":       ["analytics"],
    "CANALES":        ["mercadolibre"],
    "ADMINISTRACIÓN": ["categories", "config", "users", "roles", "emails", "plans"],
    "SISTEMA":        ["about"],
}

def _has_perm(perms: dict, perm: str | None) -> bool:
    if perm is None:
        return True
    return perms.get(perm, True)


# ══════════════════════════════════════════════════════════════
#  SPINNER
# ══════════════════════════════════════════════════════════════

class LoadingFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.45, anchor="center")
        self._chars = ["|", "/", "-", "\\"]
        self._idx = 0
        self._lbl = ctk.CTkLabel(inner, text="|",
                                  font=ctk.CTkFont(size=28),
                                  text_color=theme.TEXT_DIM)
        self._lbl.pack()
        ctk.CTkLabel(inner, text="Cargando...",
                     font=ctk.CTkFont(size=13),
                     text_color=theme.TEXT_DIM).pack(pady=(6, 0))
        self._tick()

    def _tick(self):
        try:
            self._lbl.configure(text=self._chars[self._idx % len(self._chars)])
            self._idx += 1
            self._after_id = self.after(120, self._tick)
        except Exception:
            pass

    def destroy(self):
        try:
            self.after_cancel(self._after_id)
        except Exception:
            pass
        super().destroy()


# ══════════════════════════════════════════════════════════════
#  ERROR FRAME
# ══════════════════════════════════════════════════════════════

class ErrorFrame(ctk.CTkFrame):
    def __init__(self, parent, name: str, error: str):
        super().__init__(parent, fg_color="transparent")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(inner, text="Error",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=theme.C_ORANGE).pack(pady=(0, 6))
        ctk.CTkLabel(inner, text=f"No se pudo cargar '{name}'",
                     font=ctk.CTkFont(size=13),
                     text_color=theme.TEXT_DIM).pack()
        ctk.CTkLabel(inner, text=error,
                     font=ctk.CTkFont(size=10, family="Courier New"),
                     text_color=theme.C_RED, wraplength=600,
                     justify="left").pack(pady=(8, 0))

    def on_show(self): pass
    def on_hide(self): pass


# ══════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════

class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, on_login):
        super().__init__(parent, fg_color=theme.BG)
        self.pack(fill="both", expand=True)
        self._on_login = on_login
        self._build()

    def _build(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=theme.CARD,
                             corner_radius=16,
                             border_width=1, border_color=theme.SEP,
                             width=420)
        card.grid(row=0, column=0)
        card.grid_propagate(False)

        # ── Header azul con logo ───────────────────────────
        top = ctk.CTkFrame(card, fg_color="#1a56db",
                            corner_radius=16, height=120)
        top.pack(fill="x")
        top.pack_propagate(False)

        brand_inner = ctk.CTkFrame(top, fg_color="transparent")
        brand_inner.pack(expand=True)

        logo_box = ctk.CTkFrame(brand_inner, fg_color="white",
                                 corner_radius=12, width=52, height=52)
        logo_box.pack(pady=(18, 6))
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="CS",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#1a56db").pack(expand=True)
        ctk.CTkLabel(brand_inner, text="CoreStack Pro",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="white").pack()

        # ── Formulario ────────────────────────────────────
        frm = ctk.CTkFrame(card, fg_color="transparent")
        frm.pack(fill="x", padx=32, pady=(20, 0))

        ctk.CTkLabel(frm, text="Iniciar sesión",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=theme.TEXT).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frm, text="Accedé con tus credenciales",
                     font=ctk.CTkFont(size=12),
                     text_color=theme.TEXT_DIM).pack(anchor="w", pady=(0, 20))

        ctk.CTkLabel(frm, text="Usuario", anchor="w",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x")
        self.user_e = ctk.CTkEntry(frm, height=40, corner_radius=8,
                                    placeholder_text="Nombre de usuario",
                                    border_color=theme.SEP)
        self.user_e.pack(fill="x", pady=(3, 14))

        ctk.CTkLabel(frm, text="Contraseña", anchor="w",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(fill="x")
        self.pass_e = ctk.CTkEntry(frm, height=40, corner_radius=8,
                                    show="*",
                                    placeholder_text="Contraseña",
                                    border_color=theme.SEP)
        self.pass_e.pack(fill="x", pady=(3, 0))
        self.pass_e.bind("<Return>", lambda _: self._do_login())

        self.err_lbl = ctk.CTkLabel(frm, text="",
                                     text_color=theme.C_RED,
                                     font=ctk.CTkFont(size=11))
        self.err_lbl.pack(pady=(8, 0))

        ctk.CTkButton(card, text="Iniciar sesión",
                      height=44, corner_radius=8,
                      fg_color="#1a56db", hover_color="#1648c0",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._do_login).pack(fill="x", padx=32,
                                                    pady=(14, 28))
        self.user_e.focus()

    def _do_login(self):
        u = self.user_e.get().strip()
        p = self.pass_e.get()
        if not u or not p:
            self.err_lbl.configure(text="Completá usuario y contraseña.")
            return
        try:
            user = api.authenticate_user(u, hashlib.sha256(p.encode()).hexdigest())
        except Exception as e:
            self.err_lbl.configure(text=f"Sin conexión a la base de datos.\n{e}")
            return
        if user is None:
            self.err_lbl.configure(text="Usuario o contraseña incorrectos.")
            return
        if not user.get("active"):
            self.err_lbl.configure(text="Cuenta desactivada.")
            return
        self._on_login(user)


# ══════════════════════════════════════════════════════════════
#  APP PRINCIPAL
# ══════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CoreStack Pro v0.9")
        self.geometry("1400x860")
        self.minsize(1100, 680)
        self.configure(fg_color=theme.BG)
        theme.apply_ttk_style(self)

        try:
            saved_mode = api.get_setting("ui_theme", "dark")
            ctk.set_appearance_mode(saved_mode)
        except Exception:
            pass

        self._user: dict | None = None
        self._frames: dict[str, ctk.CTkFrame | None] = {}
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._active_btn: ctk.CTkButton | None = None
        self._active_key: str | None = None
        self._content: ctk.CTkFrame | None = None
        self._sidebar: ctk.CTkFrame | None = None

        self._show_login()

    # ── Login ──────────────────────────────────────────────────
    def _show_login(self):
        for w in self.winfo_children():
            w.destroy()
        self._frames = {}
        self._nav_btns = {}
        self._active_btn = None
        self._active_key = None
        self._content = None
        LoginScreen(self, on_login=self._on_login)

    def _on_login(self, user: dict):
        self._user = user
        self._show_main()

    # ── Layout principal ───────────────────────────────────────
    def _show_main(self):
        for w in self.winfo_children():
            w.destroy()

        perms = self._user.get("permissions", {})
        visible_keys = [
            key for key, perm, *_ in FRAME_REGISTRY
            if _has_perm(perms, perm)
        ]
        self._frames = {k: None for k in visible_keys}

        root = ctk.CTkFrame(self, fg_color=theme.BG)
        root.pack(fill="both", expand=True)

        self._sidebar = ctk.CTkFrame(root, fg_color=theme.PANEL,
                                      width=220, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        border = ctk.CTkFrame(root, width=1, fg_color=theme.SEP, corner_radius=0)
        border.pack(side="left", fill="y")

        self._content = ctk.CTkFrame(root, fg_color=theme.BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()

        first = visible_keys[0] if visible_keys else None
        if first:
            self._navigate(first)
            self.after(300, lambda: self._prebuild_remaining(visible_keys, first))

    def _prebuild_remaining(self, keys: list, skip: str):
        remaining = [k for k in keys if k != skip and self._frames.get(k) is None]
        if not remaining:
            return
        key = remaining[0]
        self._frames[key] = self._build_frame(key)
        self.after(50, lambda: self._prebuild_remaining(keys, skip))

    # ── Sidebar ────────────────────────────────────────────────
    def _build_sidebar(self):
        u  = self._user
        sb = self._sidebar

        # ── Header azul con logo ───────────────────────────
        hdr = ctk.CTkFrame(sb, fg_color="#1a56db", height=64, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(side="left", fill="y", padx=14)

        logo_box = ctk.CTkFrame(hdr_inner, fg_color="white",
                                 corner_radius=8, width=32, height=32)
        logo_box.pack(side="left", pady=16)
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="CS",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#1a56db").pack(expand=True)

        txt_f = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        txt_f.pack(side="left", padx=(10, 0), pady=14)
        ctk.CTkLabel(txt_f, text="CoreStack",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white", anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt_f, text="Pro v0.9",
                     font=ctk.CTkFont(size=9),
                     text_color="#93c5fd", anchor="w").pack(anchor="w")

        # ── Perfil de usuario ──────────────────────────────
        user_card = ctk.CTkFrame(sb, fg_color=theme.CARD2,
                                  corner_radius=10, border_width=1,
                                  border_color=theme.SEP)
        user_card.pack(fill="x", padx=12, pady=(14, 4))

        uc_inner = ctk.CTkFrame(user_card, fg_color="transparent")
        uc_inner.pack(fill="x", padx=10, pady=10)

        # Avatar con inicial del usuario
        avatar = ctk.CTkFrame(uc_inner, fg_color="#1a56db",
                               corner_radius=20, width=36, height=36)
        avatar.pack(side="left")
        avatar.pack_propagate(False)
        initial = (u.get("username", "?")[0]).upper()
        ctk.CTkLabel(avatar, text=initial,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").pack(expand=True)

        uinfo = ctk.CTkFrame(uc_inner, fg_color="transparent")
        uinfo.pack(side="left", padx=(8, 0), fill="x", expand=True)
        ctk.CTkLabel(uinfo, text=u.get("username", ""),
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(uinfo, text=u.get("role", ""),
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM, anchor="w").pack(anchor="w")

        # Badge "En línea"
        badge = ctk.CTkFrame(uc_inner, fg_color="#1a3a1a",
                              corner_radius=10, width=60, height=20)
        badge.pack(side="right")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="● En línea",
                     font=ctk.CTkFont(size=9),
                     text_color="#4ade80").pack(expand=True)

        ctk.CTkFrame(sb, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=12, pady=(10, 4))

        # ── Navegación agrupada con iconos ─────────────────
        nav_scroll = ctk.CTkScrollableFrame(
            sb, fg_color="transparent",
            scrollbar_button_color=theme.SEP,
            scrollbar_button_hover_color=theme.ACCENT_H)
        nav_scroll.pack(fill="both", expand=True, padx=4)

        self._nav_btns = {}

        for group_name, group_keys in NAV_GROUPS.items():
            group_visible = [k for k in group_keys if k in self._frames]
            if not group_visible:
                continue

            ctk.CTkLabel(nav_scroll, text=group_name,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=theme.TEXT_DIM,
                         anchor="w").pack(fill="x", padx=12, pady=(12, 2))

            for key in group_visible:
                reg = next((r for r in FRAME_REGISTRY if r[0] == key), None)
                if not reg:
                    continue
                label   = reg[4]
                icon    = reg[5] if len(reg) > 5 else "·"
                is_meli = key == "mercadolibre"

                btn = ctk.CTkButton(
                    nav_scroll,
                    text=f" {icon}  {label}",
                    anchor="w",
                    height=36,
                    corner_radius=8,
                    fg_color="transparent",
                    hover_color="#3483fa" if is_meli else theme.CARD2,
                    text_color="#3483fa" if is_meli else theme.TEXT_NAV,
                    font=ctk.CTkFont(size=12,
                                     weight="bold" if is_meli else "normal"),
                    command=lambda k=key: self._navigate(k),
                )
                btn.pack(fill="x", padx=6, pady=1)
                self._nav_btns[key] = btn

        # ── Pie del sidebar ────────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=12, pady=(4, 6))
        ctk.CTkButton(sb, text="  Cerrar sesión",
                      anchor="w", height=34, corner_radius=8,
                      fg_color="transparent",
                      hover_color=theme.BTN_RED,
                      text_color=theme.TEXT_DIM,
                      font=ctk.CTkFont(size=11),
                      command=self._logout).pack(fill="x", padx=10, pady=(0, 14))

    # ── Tema ───────────────────────────────────────────────────
    def apply_theme(self, mode: str):
        ctk.set_appearance_mode(mode)
        try:
            api.set_setting("ui_theme", mode)
        except Exception:
            pass
        theme.apply_ttk_style(self)

        if self._sidebar:
            self._sidebar.configure(fg_color=theme.PANEL)
        if self._content:
            self._content.configure(fg_color=theme.BG)
        self.configure(fg_color=theme.BG)

        for key, frame in self._frames.items():
            if frame and hasattr(frame, "_refresh_treeview_style"):
                try:
                    frame._refresh_treeview_style()
                except Exception:
                    pass

    # ── Frame builder ──────────────────────────────────────────
    def _build_frame(self, key: str) -> ctk.CTkFrame:
        if key == "mercadolibre":
            try:
                return MercadolibreFrame(self._content, self._user, app=self)
            except Exception as e:
                traceback.print_exc()
                return ErrorFrame(self._content, key, str(e))

        reg = next((r for r in FRAME_REGISTRY if r[0] == key), None)
        if not reg:
            return ErrorFrame(self._content, key, "Frame no registrado")
        _, perm, mod_name, class_name, label, *_ = reg
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, class_name)
            try:
                return cls(self._content, self._user, app=self)
            except TypeError:
                return cls(self._content, self._user)
        except Exception as e:
            traceback.print_exc()
            return ErrorFrame(self._content, key, str(e))

    # ── Navegación ─────────────────────────────────────────────
    def _navigate(self, key: str):
        if key not in self._frames:
            return

        if self._active_key and self._active_key != key:
            prev = self._frames.get(self._active_key)
            if prev:
                if hasattr(prev, "on_hide"):
                    try:
                        prev.on_hide()
                    except Exception:
                        pass
                prev.pack_forget()

        if self._frames[key] is None:
            spinner = LoadingFrame(self._content)
            spinner.pack(fill="both", expand=True)
            self.update()
            self._frames[key] = self._build_frame(key)
            spinner.destroy()

        frame = self._frames[key]
        frame.pack(fill="both", expand=True)

        if hasattr(frame, "on_show"):
            try:
                frame.on_show()
            except Exception as e:
                traceback.print_exc()
                frame.pack_forget()
                err = ErrorFrame(self._content, key, str(e))
                err.pack(fill="both", expand=True)
                self._frames[key] = err
                return

        self._active_key = key

        # Reset todos los botones
        for k, b in self._nav_btns.items():
            is_meli_k = k == "mercadolibre"
            b.configure(
                fg_color="transparent",
                text_color="#3483fa" if is_meli_k else theme.TEXT_NAV,
            )

        # Activar botón seleccionado
        btn = self._nav_btns.get(key)
        if btn:
            is_meli = key == "mercadolibre"
            btn.configure(
                fg_color="#3483fa" if is_meli else "#1a56db",
                text_color="white",
            )
            self._active_btn = btn

    # ── Logout ─────────────────────────────────────────────────
    def _logout(self):
        if messagebox.askyesno("Cerrar sesión", "Confirmar cierre de sesión?"):
            if self._active_key:
                f = self._frames.get(self._active_key)
                if f and hasattr(f, "on_hide"):
                    try:
                        f.on_hide()
                    except Exception:
                        pass
            self._user = None
            self._show_login()


if __name__ == "__main__":
    App().mainloop()
