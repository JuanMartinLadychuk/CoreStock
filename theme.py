"""theme.py - Paleta de colores centralizada para CoreStack Pro.

Modo claro/oscuro controlado por CTK. Tokens de diseno minimalistas
y consistentes. Sin emojis, sin efectos decorativos."""
import customtkinter as ctk
from tkinter import ttk

# ── Colores (light, dark) ──────────────────────────────────────
BG       = ("#f4f5f7", "#0d1117")
PANEL    = ("#e8eaf0", "#161b22")
CARD     = ("#ffffff", "#1c2128")
CARD2    = ("#f0f2f6", "#21262d")
ACCENT   = ("#2563eb", "#3b82f6")
ACCENT_H = ("#1d4ed8", "#60a5fa")
SEP      = ("#dde1ea", "#30363d")
DIV      = ("#c8cdd8", "#21262d")
TEXT     = ("#111827", "#e6edf3")
TEXT_DIM = ("#6b7280", "#8b949e")
TEXT_NAV = ("#374151", "#c9d1d9")
TEXT_HDR = ("#111827", "#e6edf3")

# Semanticos - identicos en ambos modos
C_GREEN  = "#22c55e"
C_RED    = "#ef4444"
C_ORANGE = "#f97316"
C_BLUE   = "#3b82f6"
C_PURPLE = "#8b5cf6"

# Botones de accion
BTN_GREEN   = ("#16a34a", "#16a34a")
BTN_GREENH  = ("#15803d", "#15803d")
BTN_BLUE    = ("#2563eb", "#2563eb")
BTN_BLUEH   = ("#1d4ed8", "#1d4ed8")
BTN_RED     = ("#dc2626", "#dc2626")
BTN_REDH    = ("#b91c1c", "#b91c1c")
BTN_PURPLE  = ("#7c3aed", "#7c3aed")
BTN_PURPLEH = ("#6d28d9", "#6d28d9")
BTN_ORANGE  = ("#ea580c", "#ea580c")
BTN_ORANGEH = ("#c2410c", "#c2410c")


def is_dark() -> bool:
    return ctk.get_appearance_mode().lower() == "dark"


def get_mode() -> str:
    return ctk.get_appearance_mode().lower()


def set_mode(mode: str):
    """mode: 'dark' o 'light'"""
    ctk.set_appearance_mode(mode)


def apply_ttk_style(root):
    """Actualiza los estilos TTK para el modo activo."""
    dark = is_dark()
    s = ttk.Style(root)
    try:
        s.theme_use("default")
    except Exception:
        pass

    if dark:
        bg   = "#1c2128"
        fg   = "#c9d1d9"
        sel  = "#2d3748"
        hbg  = "#161b22"
        hfg  = "#e6edf3"
        sc   = "#21262d"
        tr   = "#0d1117"
        row2 = "#1f2430"
    else:
        bg   = "#ffffff"
        fg   = "#111827"
        sel  = "#dbeafe"
        hbg  = "#f0f2f6"
        hfg  = "#111827"
        sc   = "#e8eaf0"
        tr   = "#f4f5f7"
        row2 = "#f8f9fc"

    s.configure(
        "Cs.Treeview",
        background=bg,
        foreground=fg,
        fieldbackground=bg,
        rowheight=32,
        font=("Segoe UI", 10),
        borderwidth=0,
        relief="flat",
    )
    s.configure(
        "Cs.Treeview.Heading",
        background=hbg,
        foreground=hfg,
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        borderwidth=0,
    )
    s.map(
        "Cs.Treeview",
        background=[("selected", sel)],
        foreground=[("selected", fg)],
    )
    for ori in ("Vertical", "Horizontal"):
        s.configure(
            f"{ori}.TScrollbar",
            background=sc,
            troughcolor=tr,
            arrowcolor=TEXT_DIM[1] if dark else TEXT_DIM[0],
            bordercolor=tr,
            relief="flat",
            width=6,
        )
