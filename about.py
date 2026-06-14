"""about.py – Pantalla Acerca de CoreStack Pro — rediseño v0.9"""
import customtkinter as ctk
import platform, sys
from datetime import datetime
import theme

try:
    import mysql.connector
    _MYSQL_VERSION = mysql.connector.__version__
except Exception:
    _MYSQL_VERSION = "—"

try:
    _CTK_VERSION = ctk.__version__
except Exception:
    _CTK_VERSION = "—"


class AboutFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user = user
        self._build_ui()

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # ── Banner hero ────────────────────────────────────────
        hero = ctk.CTkFrame(scroll, fg_color="#1a56db",
                             corner_radius=16, height=140)
        hero.pack(fill="x", padx=24, pady=(20, 0))
        hero.pack_propagate(False)

        hero_inner = ctk.CTkFrame(hero, fg_color="transparent")
        hero_inner.pack(side="left", padx=28, pady=20)

        icon_bg = ctk.CTkFrame(hero_inner, fg_color="#2563eb",
                                corner_radius=14, width=52, height=52)
        icon_bg.pack(side="left")
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="ℹ",
                     font=ctk.CTkFont(size=24),
                     text_color="white").pack(expand=True)

        title_f = ctk.CTkFrame(hero_inner, fg_color="transparent")
        title_f.pack(side="left", padx=(16, 0))
        ctk.CTkLabel(title_f,
                     text="Sistema de Gestión de Inventario y Ventas para PyMEs",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="white", anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_f, text="CoreStack Pro v0.9",
                     font=ctk.CTkFont(size=12),
                     text_color="#93c5fd", anchor="w").pack(anchor="w", pady=(4, 0))

        # Chart decoration (lado derecho del banner)
        deco = ctk.CTkFrame(hero, fg_color="transparent")
        deco.pack(side="right", padx=24, pady=16)
        ctk.CTkLabel(deco, text="📊",
                     font=ctk.CTkFont(size=42),
                     text_color="#3b82f6").pack()

        # ── ¿Qué es CoreStack Pro? ─────────────────────────────
        self._section_title(scroll, "¿Qué es CoreStack Pro?")

        desc_card = ctk.CTkFrame(scroll, fg_color=theme.CARD,
                                  corner_radius=12, border_width=1,
                                  border_color=theme.SEP)
        desc_card.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(desc_card,
                     text="CoreStack Pro es un software de gestión de inventario y ventas "
                          "diseñado para PyMEs y comercios. Desarrollado en Python con "
                          "CustomTkinter y base de datos MySQL centralizada, profesionaliza "
                          "el comercio local mediante automatización financiera y "
                          "escalabilidad multiusuario en red local.",
                     font=ctk.CTkFont(size=12),
                     text_color=theme.TEXT_DIM,
                     justify="left", wraplength=820,
                     anchor="w").pack(padx=20, pady=16, anchor="w")

        # ── Características ────────────────────────────────────
        self._section_title(scroll, "★  Características del sistema")

        features = [
            ("🖥", "Infraestructura Cliente-Servidor",
             "Opera sobre MySQL en una PC principal. Las terminales se conectan por red local "
             "(TCP/IP) al puerto 3306. Todas las operaciones impactan en tiempo real en la base central.",
             "#1a56db"),
            ("🔒", "Seguridad con SHA-256",
             "Las contraseñas se almacenan como huellas digitales irreversibles (SHA-256 + salt). "
             "Sin dependencias externas, compatible con todas las versiones de Python 3.x.",
             "#16a34a"),
            ("👤", "Roles y Permisos Granulares",
             "El Administrador construye perfiles a medida: Cajero, Supervisor, Auditor. "
             "Para cada rol activa funciones específicas. Los botones desaparecen para usuarios sin permiso.",
             "#7c3aed"),
            ("📊", "Gestión Dinámica de Impuestos",
             "Creá, nombrá y ajustá tributos (IVA, IIBB, Tasa Municipal) libremente. Cada venta "
             "registra el desglose exacto por impuesto para auditorías sin errores manuales.",
             "#ea580c"),
            ("⬡", "Jerarquía de Márgenes (3 Niveles)",
             "Nivel 1: margen del producto (prioridad máxima). "
             "Nivel 2: margen de categoría (herencia). "
             "Nivel 3: margen global (red de seguridad).",
             "#0891b2"),
            ("✉", "Emails a Proveedores",
             "Compositor integrado con plantillas rápidas, envío real vía SMTP en hilo separado "
             "(no congela la UI). Soporta Gmail, Outlook y cualquier servidor compatible.",
             "#1a56db"),
            ("📈", "Dashboard y Reportes",
             "KPIs en tiempo real, gráficas ASCII integradas. "
             "Exportación a Excel (pandas) y PDF (reportlab) con desglose fiscal completo.",
             "#16a34a"),
            ("🎨", "Tema Dark / Light",
             "Cambio de tema en tiempo real sin reiniciar la aplicación. Todos los frames "
             "se actualizan automáticamente gracias al sistema de colores CTK tuple.",
             "#7c3aed"),
        ]

        feat_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        feat_grid.pack(fill="x", padx=24, pady=(0, 16))
        feat_grid.columnconfigure(0, weight=1)
        feat_grid.columnconfigure(1, weight=1)

        for idx, (icon, title, desc, color) in enumerate(features):
            row_n = idx // 2
            col_n = idx % 2
            pad_l = (0, 6) if col_n == 0 else (6, 0)

            card = ctk.CTkFrame(feat_grid, fg_color=theme.CARD,
                                 corner_radius=12, border_width=1,
                                 border_color=theme.SEP)
            card.grid(row=row_n, column=col_n, sticky="nsew",
                      padx=pad_l, pady=6)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=16)

            icon_c = ctk.CTkFrame(inner, fg_color=theme.CARD2,
                                   corner_radius=10, width=42, height=42)
            icon_c.pack(side="left", anchor="nw")
            icon_c.pack_propagate(False)
            ctk.CTkLabel(icon_c, text=icon,
                         font=ctk.CTkFont(size=18)).pack(expand=True)

            text_f = ctk.CTkFrame(inner, fg_color="transparent")
            text_f.pack(side="left", padx=(12, 0), fill="both", expand=True)
            ctk.CTkLabel(text_f, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.TEXT, anchor="w",
                         justify="left").pack(anchor="w")
            ctk.CTkLabel(text_f, text=desc,
                         font=ctk.CTkFont(size=11),
                         text_color=theme.TEXT_DIM,
                         justify="left", wraplength=320,
                         anchor="w").pack(anchor="w", pady=(4, 0))

        # ── Tagline ────────────────────────────────────────────
        tag_card = ctk.CTkFrame(scroll, fg_color=theme.CARD2,
                                 corner_radius=12, border_width=1,
                                 border_color=theme.SEP)
        tag_card.pack(fill="x", padx=24, pady=(0, 20))
        tag_inner = ctk.CTkFrame(tag_card, fg_color="transparent")
        tag_inner.pack(fill="x", padx=20, pady=16)

        star_bg = ctk.CTkFrame(tag_inner, fg_color=theme.CARD2,
                                corner_radius=10, width=38, height=38)
        star_bg.pack(side="left")
        star_bg.pack_propagate(False)
        ctk.CTkLabel(star_bg, text="★",
                     font=ctk.CTkFont(size=16),
                     text_color="#1a56db").pack(expand=True)

        tag_txt = ctk.CTkFrame(tag_inner, fg_color="transparent")
        tag_txt.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(tag_txt, text="Hecho para hacer crecer tu negocio",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(tag_txt,
                     text="CoreStack Pro combina potencia, seguridad y simplicidad para que puedas "
                          "enfocarte en lo más importante: hacer crecer tu empresa.",
                     font=ctk.CTkFont(size=11),
                     text_color=theme.TEXT_DIM, anchor="w",
                     wraplength=700).pack(anchor="w", pady=(3, 0))

        # Flecha decorativa
        ctk.CTkLabel(tag_inner, text="↗",
                     font=ctk.CTkFont(size=28),
                     text_color="#1a56db").pack(side="right", padx=(0, 4))

        # ── Info del sistema ───────────────────────────────────
        self._section_title(scroll, "Información del sistema")

        sys_card = ctk.CTkFrame(scroll, fg_color=theme.CARD,
                                 corner_radius=12, border_width=1,
                                 border_color=theme.SEP)
        sys_card.pack(fill="x", padx=24, pady=(0, 20))

        sg = ctk.CTkFrame(sys_card, fg_color="transparent")
        sg.pack(fill="x", padx=20, pady=16)
        sg.columnconfigure((1, 3), weight=1)

        for i, (label, value) in enumerate([
            ("Python:", f"{sys.version.split()[0]}"),
            ("CustomTkinter:", _CTK_VERSION),
            ("MySQL Connector:", _MYSQL_VERSION),
            ("Sistema operativo:", f"{platform.system()} {platform.release()}"),
            ("Arquitectura:", platform.machine()),
            ("Fecha y hora:", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ]):
            r, c = divmod(i, 2)
            ctk.CTkLabel(sg, text=label, anchor="e",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=12),
                         width=160).grid(row=r, column=c*2,
                                          sticky="e", padx=(0, 8), pady=4)
            ctk.CTkLabel(sg, text=value, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=theme.TEXT).grid(row=r, column=c*2+1,
                                                       sticky="w",
                                                       padx=(0, 30), pady=4)

        # ── Stack tecnológico ──────────────────────────────────
        self._section_title(scroll, "Stack tecnológico")

        stack_row = ctk.CTkFrame(scroll, fg_color="transparent")
        stack_row.pack(fill="x", padx=24, pady=(0, 28))

        for name, desc, color in [
            ("Python 3.11+", "Lenguaje base", "#3572A5"),
            ("CustomTkinter", "Interfaz gráfica", "#ab47bc"),
            ("MySQL 8+", "Base de datos", "#F29111"),
            ("SHA-256", "Criptografía", "#ef5350"),
            ("reportlab", "PDF", "#4caf50"),
            ("pandas", "Excel / datos", "#ffa726"),
            ("smtplib", "Emails SMTP", "#26c6da"),
            ("ttk.Treeview", "Tablas", "#4fc3f7"),
        ]:
            cell = ctk.CTkFrame(stack_row, fg_color=theme.CARD2,
                                 corner_radius=10, border_width=1,
                                 border_color=theme.SEP)
            cell.pack(side="left", padx=3, pady=4, fill="x", expand=True)
            ctk.CTkLabel(cell, text=name,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=color).pack(pady=(10, 2), padx=8)
            ctk.CTkLabel(cell, text=desc,
                         font=ctk.CTkFont(size=10),
                         text_color=theme.TEXT_DIM).pack(pady=(0, 10))

    def _section_title(self, parent, text: str):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=theme.TEXT,
                     anchor="w").pack(anchor="w", padx=24,
                                       pady=(16, 8))

    def on_show(self):
        pass
