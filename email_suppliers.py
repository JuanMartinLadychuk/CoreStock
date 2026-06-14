"""email_suppliers.py – Compositor de emails a proveedores. Rediseño v0.9
Paleta:
  PRIMARIO  #0f172a  (fondo paneles / superficies profundas)
  SECUNDARIO #1e293b (cards, inputs, hover neutro)
  ACENTO    #6366f1  (botón principal, highlights, badges)
"""
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import smtplib, ssl, threading, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import api, theme
import widgets as W

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff")

# ── Paleta propia del módulo ───────────────────────────────────
_PRI  = ("#f8fafc", "#0f172a")   # fondo de paneles
_SEC  = ("#f1f5f9", "#1e293b")   # cards / inputs
_ACC  = "#6366f1"                # indigo — botón principal / activo
_ACC_H = "#4f46e5"               # hover del acento
_ACC_DIM = ("#e0e7ff", "#312e81") # fondo suave para badges de acento
_TXT  = ("#0f172a", "#f1f5f9")   # texto principal
_DIM  = ("#64748b", "#94a3b8")   # texto secundario
_SEP  = ("#e2e8f0", "#334155")   # separadores
_DANGER = "#ef4444"
_WARN   = "#f59e0b"
_OK     = "#22c55e"


class EmailFrame(ctk.CTkFrame):
    def __init__(self, parent, user: dict):
        super().__init__(parent, fg_color="transparent")
        self.user        = user
        self._suppliers  = []
        self._attachments: list[str] = []
        self._sel_supplier: dict | None = None
        self._build_ui()

    # ══════════════════════════════════════════════════════════
    #  Layout principal
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Cabecera ──────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(22, 0))

        left_hdr = ctk.CTkFrame(hdr, fg_color="transparent")
        left_hdr.pack(side="left")

        ctk.CTkLabel(left_hdr, text="Emails",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=_TXT).pack(side="left")

        badge = ctk.CTkFrame(left_hdr, fg_color=_ACC_DIM,
                              corner_radius=6, width=80, height=22)
        badge.pack(side="left", padx=(10, 0))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="Proveedores",
                     font=ctk.CTkFont(size=10),
                     text_color=_ACC).pack(expand=True)

        # ── Stock bajo banner (si aplica) ─────────────────────
        try:
            low = api.get_low_stock_products()
        except Exception:
            low = []

        if low:
            banner = ctk.CTkFrame(self, fg_color=_SEC,
                                   corner_radius=10, border_width=1,
                                   border_color=_SEP)
            banner.pack(fill="x", padx=24, pady=(14, 0))
            bi = ctk.CTkFrame(banner, fg_color="transparent")
            bi.pack(fill="x", padx=16, pady=10)

            dot = ctk.CTkFrame(bi, fg_color=_WARN,
                                corner_radius=12, width=8, height=8)
            dot.pack(side="left")
            dot.pack_propagate(False)

            ctk.CTkLabel(bi,
                         text=f"  {len(low)} productos con stock bajo",
                         font=ctk.CTkFont(size=12),
                         text_color=_WARN).pack(side="left")

            ctk.CTkButton(bi, text="Generar alerta →",
                          width=140, height=28, corner_radius=6,
                          fg_color=_WARN, hover_color="#d97706",
                          text_color="white",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._load_low_stock_template
                          ).pack(side="right")

        # ── Cuerpo split ──────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=16)
        body.columnconfigure(0, weight=1, minsize=260)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        self._build_sidebar_panel(body)
        self._build_compose_panel(body)

    # ══════════════════════════════════════════════════════════
    #  Panel izquierdo — lista de proveedores
    # ══════════════════════════════════════════════════════════
    def _build_sidebar_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=_PRI,
                              corner_radius=14, border_width=1,
                              border_color=_SEP)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel.rowconfigure(2, weight=1)
        panel.columnconfigure(0, weight=1)

        # Header del panel
        ph = ctk.CTkFrame(panel, fg_color="transparent")
        ph.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))

        ctk.CTkLabel(ph, text="Proveedores",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=_TXT).pack(side="left")

        self._sup_count_lbl = ctk.CTkLabel(ph, text="",
                                            font=ctk.CTkFont(size=10),
                                            text_color=_DIM)
        self._sup_count_lbl.pack(side="right")

        # Buscador — fila 1
        search_wrap = ctk.CTkFrame(panel, fg_color=_SEC,
                                    corner_radius=8, border_width=1,
                                    border_color=_SEP)
        search_wrap.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_suppliers())
        ctk.CTkEntry(search_wrap,
                     textvariable=self._search_var,
                     placeholder_text="Buscar proveedor…",
                     border_width=0, fg_color="transparent",
                     height=32,
                     font=ctk.CTkFont(size=12)
                     ).pack(fill="x", padx=8)

        # Lista scrollable — fila 2
        self._sup_list = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                                 scrollbar_button_color=_SEP)
        self._sup_list.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 12))
        panel.rowconfigure(2, weight=1)

    def _render_supplier_list(self):
        for w in self._sup_list.winfo_children():
            w.destroy()
        q = self._search_var.get().lower() if hasattr(self, "_search_var") else ""
        shown = [s for s in self._suppliers
                 if q in s[1].lower() or q in (s[3] or "").lower()]
        self._sup_count_lbl.configure(text=f"{len(shown)} contactos")

        for s in shown:
            sup_id, name, city, mail, tel = s[0], s[1], s[2] or "", s[3] or "", s[4] or ""
            is_sel = self._sel_supplier and self._sel_supplier[0] == sup_id

            card = ctk.CTkFrame(self._sup_list,
                                 fg_color=_ACC if is_sel else _SEC,
                                 corner_radius=10, border_width=1,
                                 border_color=_ACC if is_sel else _SEP,
                                 cursor="hand2")
            card.pack(fill="x", padx=4, pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)

            # Avatar inicial
            av = ctk.CTkFrame(inner,
                               fg_color="white" if is_sel else _ACC,
                               corner_radius=16, width=32, height=32)
            av.pack(side="left")
            av.pack_propagate(False)
            ctk.CTkLabel(av, text=name[0].upper(),
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=_ACC if is_sel else "white").pack(expand=True)

            txt = ctk.CTkFrame(inner, fg_color="transparent")
            txt.pack(side="left", padx=(10, 0), fill="x", expand=True)
            ctk.CTkLabel(txt, text=name,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="white" if is_sel else _TXT,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(txt, text=mail or "Sin email",
                         font=ctk.CTkFont(size=10),
                         text_color="white" if is_sel else _DIM,
                         anchor="w").pack(anchor="w")

            # click handler
            for w in [card, inner, txt, av]:
                w.bind("<Button-1>",
                       lambda e, sup=s: self._select_supplier(sup))

    def _select_supplier(self, sup):
        self._sel_supplier = sup
        self.to_e.delete(0, "end")
        if sup[3]:
            self.to_e.insert(0, sup[3])
        self._render_supplier_list()

    def _filter_suppliers(self):
        self._render_supplier_list()

    # ══════════════════════════════════════════════════════════
    #  Panel derecho — redactar
    # ══════════════════════════════════════════════════════════
    def _build_compose_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=_PRI,
                              corner_radius=14, border_width=1,
                              border_color=_SEP)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.rowconfigure(3, weight=1)
        panel.columnconfigure(0, weight=1)

        # ── Top bar del compositor ─────────────────────────
        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 0))

        ctk.CTkLabel(top, text="Nuevo mensaje",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=_TXT).pack(side="left")

        # Botón limpiar — texto plano, sin relleno
        ctk.CTkButton(top, text="Limpiar",
                      width=70, height=28, corner_radius=6,
                      fg_color="transparent", hover_color=_SEC,
                      text_color=_DIM, border_width=1,
                      border_color=_SEP,
                      font=ctk.CTkFont(size=11),
                      command=self._clear).pack(side="right")

        ctk.CTkFrame(panel, height=1, fg_color=_SEP).grid(
            row=1, column=0, sticky="ew", padx=20, pady=(14, 0))

        # ── Campos Para / Asunto ──────────────────────────
        fields = ctk.CTkFrame(panel, fg_color="transparent")
        fields.grid(row=2, column=0, sticky="ew", padx=20, pady=(14, 0))
        fields.columnconfigure(1, weight=1)

        for row_i, (lbl_txt, attr, ph) in enumerate([
            ("Para",   "to_e",      "email@proveedor.com"),
            ("Asunto", "subject_e", "Asunto del mensaje"),
        ]):
            ctk.CTkLabel(fields, text=lbl_txt,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=_DIM,
                         width=56, anchor="w").grid(
                row=row_i, column=0, sticky="w", pady=5)

            e = ctk.CTkEntry(fields,
                             placeholder_text=ph,
                             height=36, corner_radius=8,
                             fg_color=_SEC,
                             border_color=_SEP,
                             border_width=1,
                             text_color=_TXT,
                             font=ctk.CTkFont(size=12))
            e.grid(row=row_i, column=1, sticky="ew", padx=(10, 0), pady=5)
            setattr(self, attr, e)

        # ── Área de texto ─────────────────────────────────
        body_wrap = ctk.CTkFrame(panel, fg_color="transparent")
        body_wrap.grid(row=3, column=0, sticky="nsew", padx=20, pady=(12, 0))
        body_wrap.rowconfigure(0, weight=1)
        body_wrap.columnconfigure(0, weight=1)

        self.body_t = ctk.CTkTextbox(
            body_wrap,
            corner_radius=10,
            border_color=_SEP,
            border_width=1,
            fg_color=_SEC,
            text_color=_TXT,
            font=ctk.CTkFont(size=12),
            wrap="word")
        self.body_t.grid(row=0, column=0, sticky="nsew")

        # ── Adjuntos ──────────────────────────────────────
        att_section = ctk.CTkFrame(panel, fg_color="transparent")
        att_section.grid(row=4, column=0, sticky="ew",
                          padx=20, pady=(10, 0))

        att_top = ctk.CTkFrame(att_section, fg_color="transparent")
        att_top.pack(fill="x")

        ctk.CTkLabel(att_top, text="Adjuntos",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=_DIM).pack(side="left")

        ctk.CTkButton(att_top, text="+ Imagen",
                      width=82, height=26, corner_radius=6,
                      fg_color="transparent", hover_color=_SEC,
                      text_color=_ACC, border_width=1,
                      border_color=_ACC,
                      font=ctk.CTkFont(size=11),
                      command=self._add_attachment).pack(side="right")

        self._att_frame = ctk.CTkFrame(att_section,
                                        fg_color=_SEC,
                                        corner_radius=8,
                                        border_width=1,
                                        border_color=_SEP,
                                        height=52)
        self._att_frame.pack(fill="x", pady=(6, 0))
        self._att_frame.pack_propagate(False)
        self._att_listbox_items: list = []
        self._render_attachments()

        # ── Footer: estado + botón enviar ─────────────────
        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=5, column=0, sticky="ew",
                     padx=20, pady=(12, 18))

        self.status_lbl = ctk.CTkLabel(footer, text="",
                                        font=ctk.CTkFont(size=11),
                                        text_color=_DIM,
                                        anchor="w")
        self.status_lbl.pack(side="left", fill="x", expand=True)

        # Botón Enviar — acento indigo, llamativo pero no chillón
        self._send_btn = ctk.CTkButton(
            footer,
            text="Enviar mensaje",
            width=148, height=40,
            corner_radius=10,
            fg_color=_ACC,
            hover_color=_ACC_H,
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._send_email)
        self._send_btn.pack(side="right")

    # ══════════════════════════════════════════════════════════
    #  Adjuntos
    # ══════════════════════════════════════════════════════════
    def _render_attachments(self):
        for w in self._att_frame.winfo_children():
            w.destroy()
        self._att_listbox_items.clear()

        if not self._attachments:
            ctk.CTkLabel(self._att_frame,
                         text="Sin archivos adjuntos",
                         font=ctk.CTkFont(size=11),
                         text_color=_DIM).pack(expand=True)
            return

        self._att_frame.configure(height=max(52, len(self._attachments) * 30 + 10))

        for idx, path in enumerate(self._attachments):
            fname   = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024

            row = ctk.CTkFrame(self._att_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)

            # Chip de nombre
            chip = ctk.CTkFrame(row, fg_color=_ACC_DIM,
                                 corner_radius=6)
            chip.pack(side="left")
            ctk.CTkLabel(chip,
                         text=f"  {fname[:28]}  {size_kb:.0f}KB",
                         font=ctk.CTkFont(size=10),
                         text_color=_ACC).pack(padx=4, pady=2)

            # Botón quitar
            ctk.CTkButton(row, text="×",
                          width=22, height=22, corner_radius=4,
                          fg_color="transparent",
                          hover_color=_SEC,
                          text_color=_DIM,
                          font=ctk.CTkFont(size=13),
                          command=lambda i=idx: self._remove_at(i)
                          ).pack(side="left", padx=(4, 0))

            self._att_listbox_items.append(row)

    def _add_attachment(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff"),
                       ("Todos", "*.*")])
        for path in paths:
            if path and path not in self._attachments:
                ext = os.path.splitext(path)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    messagebox.showwarning("Formato no soportado",
                                           f"Solo imágenes.\nIgnorado: {os.path.basename(path)}")
                    continue
                self._attachments.append(path)
        self._render_attachments()

    def _remove_at(self, idx: int):
        if 0 <= idx < len(self._attachments):
            self._attachments.pop(idx)
            self._render_attachments()

    def _remove_attachment(self):
        if self._attachments:
            self._attachments.pop()
            self._render_attachments()

    # ══════════════════════════════════════════════════════════
    #  Helpers de datos
    # ══════════════════════════════════════════════════════════
    def _refresh_treeview_style(self):
        pass  # no treeview en este rediseño

    def _load_suppliers(self):
        self._suppliers = api.get_all_suppliers()
        self._render_supplier_list()

    def _load_low_stock_template(self):
        low  = api.get_low_stock_products()
        comp = api.get_setting("company_name", "CoreStack Pro")
        subject = f"Reposición de stock urgente — {comp}"
        body = ("Estimado proveedor,\n\n"
                "Le informamos que los siguientes productos tienen stock bajo "
                "y necesitamos reposición a la brevedad:\n\n")
        for prod, stock, mail, supplier in low:
            body += f"  · {prod}: {stock} unidades en stock\n"
        body += f"\nPor favor contáctenos para coordinar el pedido.\n\nSaludos,\n{comp}"
        self.subject_e.delete(0, "end")
        self.subject_e.insert(0, subject)
        self.body_t.delete("1.0", "end")
        self.body_t.insert("1.0", body)

    # ══════════════════════════════════════════════════════════
    #  Envío
    # ══════════════════════════════════════════════════════════
    def _send_email(self):
        to      = self.to_e.get().strip()
        subject = self.subject_e.get().strip()
        body    = self.body_t.get("1.0", "end").strip()

        if not to or not subject or not body:
            self._set_status("Completá todos los campos.", _DANGER)
            return

        s    = api.get_all_settings()
        host = s.get("smtp_host", "").strip()
        user = s.get("smtp_user", "").strip()
        pw   = s.get("smtp_password", "").strip()
        name = s.get("smtp_from_name", "CoreStack Pro")
        try:
            port = int(s.get("smtp_port", "587"))
        except ValueError:
            port = 587

        if not host or not user:
            self._set_status("Configurá el SMTP en Configuración → Email.", _WARN)
            return

        missing = [p for p in self._attachments if not os.path.isfile(p)]
        if missing:
            messagebox.showerror("Archivos no encontrados",
                                 "No se encontraron:\n" +
                                 "\n".join(os.path.basename(p) for p in missing))
            return

        self._set_status("Enviando…", _DIM)
        self._send_btn.configure(state="disabled", text="Enviando…")
        atts = list(self._attachments)

        def _go():
            try:
                msg = MIMEMultipart("mixed")
                msg["Subject"] = subject
                msg["From"]    = f"{name} <{user}>"
                msg["To"]      = to
                msg.attach(MIMEText(body, "plain", "utf-8"))
                for path in atts:
                    fn  = os.path.basename(path)
                    ext = os.path.splitext(fn)[1].lower().lstrip(".")
                    sub = {"jpg":"jpeg","jpeg":"jpeg","png":"png","gif":"gif",
                           "bmp":"bmp","webp":"webp","tiff":"tiff","tif":"tiff"
                           }.get(ext, "octet-stream")
                    with open(path, "rb") as f:
                        part = MIMEBase("image", sub)
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", "attachment", filename=fn)
                    msg.attach(part)
                with smtplib.SMTP(host, port, timeout=10) as srv:
                    srv.ehlo()
                    srv.starttls(context=ssl.create_default_context())
                    if pw:
                        srv.login(user, pw)
                    srv.sendmail(user, [to], msg.as_string())
                n = len(atts)
                txt = f" con {n} adjunto(s)" if n else ""
                self.after(0, lambda: (
                    self._set_status(f"Enviado a {to}{txt}", _OK),
                    self._send_btn.configure(state="normal", text="Enviar mensaje"),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): (
                    self._set_status(f"Error: {err}", _DANGER),
                    self._send_btn.configure(state="normal", text="Enviar mensaje"),
                ))

        threading.Thread(target=_go, daemon=True).start()

    def _set_status(self, text: str, color):
        self.status_lbl.configure(text=text, text_color=color)

    def _clear(self):
        self.to_e.delete(0, "end")
        self.subject_e.delete(0, "end")
        self.body_t.delete("1.0", "end")
        self._sel_supplier = None
        self._attachments.clear()
        self._render_attachments()
        self._render_supplier_list()
        self._set_status("", _DIM)

    def on_show(self):
        self._load_suppliers()
