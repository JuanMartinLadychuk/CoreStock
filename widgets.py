"""widgets.py - Componentes UI reutilizables para CoreStack Pro.
Diseno limpio, sin emojis, tipografia Segoe UI."""
import customtkinter as ctk
from tkinter import ttk
import theme


def page_header(parent, title: str, refresh_cmd=None, extra_btns: list = None) -> ctk.CTkFrame:
    """Encabezado de pagina con titulo y botones opcionales."""
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=24, pady=(20, 12))

    ctk.CTkLabel(
        hdr, text=title,
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=theme.TEXT,
    ).pack(side="left")

    if extra_btns:
        for btn_cfg in reversed(extra_btns):
            ctk.CTkButton(
                hdr,
                height=32,
                corner_radius=6,
                font=ctk.CTkFont(size=12),
                **btn_cfg,
            ).pack(side="right", padx=(4, 0))

    if refresh_cmd:
        ctk.CTkButton(
            hdr, text="Actualizar", width=90, height=32,
            corner_radius=6,
            fg_color=theme.CARD2,
            hover_color=theme.ACCENT_H,
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=12),
            command=refresh_cmd,
        ).pack(side="right", padx=(4, 0))

    return hdr


def divider(parent, padx=0, pady=6):
    """Linea divisora horizontal."""
    ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(
        fill="x", padx=padx, pady=pady
    )


def card(parent, **kw) -> ctk.CTkFrame:
    """Tarjeta con fondo CARD."""
    return ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=10, **kw)


def card2(parent, **kw) -> ctk.CTkFrame:
    """Tarjeta secundaria."""
    return ctk.CTkFrame(parent, fg_color=theme.CARD2, corner_radius=8, **kw)


def label_dim(parent, text, **kw) -> ctk.CTkLabel:
    """Etiqueta de texto atenuado."""
    return ctk.CTkLabel(
        parent, text=text,
        text_color=theme.TEXT_DIM,
        font=ctk.CTkFont(size=11),
        **kw,
    )


def kpi_card(parent, icon, title, value, subtitle, color, col) -> ctk.CTkFrame:
    """Tarjeta KPI en un grid."""
    card_f = ctk.CTkFrame(
        parent, fg_color=theme.CARD, corner_radius=10,
        border_width=1, border_color=theme.SEP,
    )
    card_f.grid(
        row=0, column=col, sticky="nsew",
        padx=(0 if col == 0 else 8, 0), pady=2,
    )

    # Indicador de color lateral
    accent_bar = ctk.CTkFrame(card_f, width=3, corner_radius=2, fg_color=color)
    accent_bar.pack(side="left", fill="y", padx=(12, 0), pady=14)

    body = ctk.CTkFrame(card_f, fg_color="transparent")
    body.pack(side="left", fill="both", expand=True, padx=12, pady=14)

    ctk.CTkLabel(
        body, text=value,
        font=ctk.CTkFont(size=22, weight="bold"),
        text_color=color,
        anchor="w",
    ).pack(anchor="w")

    ctk.CTkLabel(
        body, text=title,
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=theme.TEXT,
        anchor="w",
    ).pack(anchor="w", pady=(1, 0))

    ctk.CTkLabel(
        body, text=subtitle,
        font=ctk.CTkFont(size=10),
        text_color=theme.TEXT_DIM,
        anchor="w",
    ).pack(anchor="w")

    return card_f


def make_tree(
    parent,
    cols: list,
    widths: list,
    anchors: list = None,
    height: int = 10,
    sortable: bool = False,
) -> tuple:
    """Treeview + Scrollbar envuelto en un frame card.
 Retorna (tree_frame, tree)."""
    frame = ctk.CTkFrame(
        parent, fg_color=theme.CARD, corner_radius=10,
        border_width=1, border_color=theme.SEP,
    )
    anchors = anchors or ["center"] * len(cols)

    tree = ttk.Treeview(
        frame, columns=cols, show="headings",
        style="Cs.Treeview", selectmode="browse", height=height,
    )
    for col, w, anc in zip(cols, widths, anchors):
        tree.heading(col, text=col)
        tree.column(col, width=w, anchor=anc, minwidth=40)

    sc = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sc.set)
    tree.pack(side="left", fill="both", expand=True, padx=0, pady=0)
    sc.pack(side="right", fill="y")
    return frame, tree


def action_btn(parent, text, color, hover, **kw) -> ctk.CTkButton:
    """Boton de accion estandar."""
    return ctk.CTkButton(
        parent, text=text,
        fg_color=color, hover_color=hover,
        height=32, corner_radius=6,
        font=ctk.CTkFont(size=12),
        **kw,
    )


def filter_bar(parent) -> ctk.CTkFrame:
    """Barra de filtros horizontal."""
    bar = ctk.CTkFrame(
        parent, fg_color=theme.CARD,
        corner_radius=8,
        border_width=1, border_color=theme.SEP,
    )
    bar.pack(fill="x", padx=24, pady=(0, 10))
    return bar


def search_entry(parent, placeholder="Buscar...", width=220, on_change=None) -> ctk.CTkEntry:
    """Campo de busqueda estandar."""
    e = ctk.CTkEntry(
        parent, width=width,
        placeholder_text=placeholder,
        height=32, corner_radius=6,
        border_color=theme.SEP,
    )
    if on_change:
        e.bind("<KeyRelease>", lambda _: on_change())
    return e


def section_title(parent, text: str):
    """Titulo de seccion con linea inferior."""
    ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=theme.TEXT_DIM,
    ).pack(anchor="w", pady=(14, 2))
    ctk.CTkFrame(parent, height=1, fg_color=theme.SEP).pack(fill="x", pady=(0, 8))
