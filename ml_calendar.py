"""
ml_calendar.py – Calendario de despachos + Sistema de notificaciones ML
CoreStack Pro v0.9

Widgets exportados:
  - MLCalendarWidget         calendario mensual con eventos de despacho
  - NotificationPanel        lista de alertas agrupadas por tipo
  - NotificationBell         boton con badge para headers
  - MLDashboardCalendarFrame frame completo: calendario + alertas (usar en dashboard)
  - start_notification_daemon hilo de polling en background

Tipos de alerta:
  DESPACHO_URGENTE  SLA < 4hs o vencido
  DESPACHO_HOY      Orden paga sin despachar / SLA < 24hs
  FLEX_PENDIENTE    Envio flex pendiente
  STOCK_BAJO        5 unidades o menos
  PREGUNTA_NUEVA    Pregunta de comprador sin responder
"""

import threading
import time
from datetime import datetime, date, timedelta

import customtkinter as ctk
import theme

# ── Paleta ────────────────────────────────────────────────────
C_MELIA    = "#3483fa"
C_FLEX     = "#00a650"
C_URGENTE  = "#e53935"
C_WARN     = "#fb8c00"
C_INFO     = "#1e88e5"
C_STOCK    = "#8e24aa"
C_PREGUNTA = "#f4511e"

MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
DIAS_ES = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]

# ══════════════════════════════════════════════════════════════
#  Capa de datos
# ══════════════════════════════════════════════════════════════

def _guess_size(total: float, qty: int) -> str:
    """Heuristica de talle basada en importe unitario."""
    u = (total / qty) if qty else total
    if u < 2000:   return "Sobre"
    if u < 8000:   return "Pequeno"
    if u < 25000:  return "Mediano"
    return "Grande"


def _get_events(ml_user_id: str) -> list:
    """Lee ordenes locales y las convierte en eventos de calendario."""
    events = []
    if not ml_user_id:
        return events
    try:
        import ml_api
        rows = ml_api.get_orders_local(ml_user_id=ml_user_id, status="", limit=300)
        now  = datetime.now()
        for row in rows:
            (_, ml_order_id, buyer, qty, unit_price, total,
             st, ship_st, date_cr, sla_limit, afip_sent, afip_cae, title) = row
            if st in ("cancelled", "delivered"):
                continue

            dispatch_date = None
            urgent        = False
            is_flex       = False

            if sla_limit:
                try:
                    sla_dt        = datetime.strptime(str(sla_limit)[:16], "%Y-%m-%d %H:%M")
                    dispatch_date = sla_dt.date()
                    hours_left    = (sla_dt - now).total_seconds() / 3600
                    urgent        = hours_left < 24
                    if date_cr:
                        cr_dt   = datetime.strptime(str(date_cr)[:16], "%Y-%m-%d %H:%M")
                        is_flex = (sla_dt - cr_dt).total_seconds() / 3600 <= 24
                except Exception:
                    pass

            if not dispatch_date:
                if date_cr:
                    try:
                        cr_dt         = datetime.strptime(str(date_cr)[:16], "%Y-%m-%d %H:%M")
                        dispatch_date = (cr_dt + timedelta(days=2)).date()
                    except Exception:
                        pass
                if not dispatch_date:
                    dispatch_date = date.today()

            events.append({
                "date":       dispatch_date,
                "order_id":   ml_order_id,
                "buyer":      buyer or "-",
                "title":      (title or "-")[:40],
                "qty":        qty or 1,
                "is_flex":    is_flex,
                "status":     st,
                "ship_st":    ship_st or "",
                "sla_limit":  sla_limit,
                "urgent":     urgent,
                "total":      float(total or 0),
                "size":       _guess_size(float(total or 0), qty or 1),
            })
    except Exception as e:
        print(f"[ml_calendar] _get_events: {e}")
    return events


def _get_alerts(ml_user_id: str) -> list:
    """Genera lista de alertas activas ordenadas por prioridad."""
    alerts = []
    now    = datetime.now()

    # Ordenes -------------------------------------------------------
    try:
        import ml_api
        if ml_user_id:
            rows = ml_api.get_orders_local(ml_user_id=ml_user_id, status="", limit=200)
            for row in rows:
                (_, ml_order_id, buyer, qty, unit_price, total,
                 st, ship_st, date_cr, sla_limit, afip_sent, afip_cae, title) = row
                if st in ("cancelled", "delivered"):
                    continue
                if st not in ("paid", "payment_in_process"):
                    continue

                is_flex      = False
                hours_to_sla = None

                if sla_limit:
                    try:
                        sla_dt       = datetime.strptime(str(sla_limit)[:16], "%Y-%m-%d %H:%M")
                        hours_to_sla = (sla_dt - now).total_seconds() / 3600
                        if date_cr:
                            cr_dt   = datetime.strptime(str(date_cr)[:16], "%Y-%m-%d %H:%M")
                            is_flex = (sla_dt - cr_dt).total_seconds() / 3600 <= 24
                    except Exception:
                        pass

                short = (title or "-")[:30]
                info  = {"order_id": ml_order_id}

                if hours_to_sla is not None and hours_to_sla < 0:
                    alerts.append({
                        "type":  "DESPACHO_URGENTE",
                        "title": "Despacho VENCIDO",
                        "body":  f"Orden #{ml_order_id}  {buyer} — {short}  x{qty}",
                        "color": C_URGENTE, "icon": "!", "ts": now, "data": info,
                    })
                elif hours_to_sla is not None and hours_to_sla < 4:
                    alerts.append({
                        "type":  "DESPACHO_URGENTE",
                        "title": f"Despachar en {max(0, hours_to_sla):.0f}h",
                        "body":  f"Orden #{ml_order_id}  {buyer} — {short}  x{qty}",
                        "color": C_URGENTE, "icon": "!", "ts": now, "data": info,
                    })
                elif is_flex:
                    alerts.append({
                        "type":  "FLEX_PENDIENTE",
                        "title": "Envio Flex pendiente",
                        "body":  f"Orden #{ml_order_id}  {buyer} — {short}  x{qty}",
                        "color": C_FLEX, "icon": "F", "ts": now, "data": info,
                    })
                elif hours_to_sla is not None and hours_to_sla < 24:
                    alerts.append({
                        "type":  "DESPACHO_HOY",
                        "title": "Despachar hoy",
                        "body":  f"Orden #{ml_order_id}  {buyer} — {short}  x{qty}",
                        "color": C_WARN, "icon": "P", "ts": now, "data": info,
                    })
                elif not ship_st and st == "paid":
                    alerts.append({
                        "type":  "DESPACHO_HOY",
                        "title": "Orden paga sin despachar",
                        "body":  f"Orden #{ml_order_id}  {buyer} — {short}  x{qty}",
                        "color": C_WARN, "icon": "P", "ts": now, "data": info,
                    })
    except Exception as e:
        print(f"[ml_calendar] _get_alerts ordenes: {e}")

    # Stock bajo (XAMPP) --------------------------------------------
    try:
        import api
        low = api.get_low_stock_products(threshold=5)
        for (product, stock, mail, supplier) in low:
            alerts.append({
                "type":  "STOCK_BAJO",
                "title": f"Stock bajo: {product}",
                "body":  f"Quedan {stock} unidades  |  Prov: {supplier or '-'}",
                "color": C_STOCK, "icon": "S", "ts": now,
                "data":  {"product": product, "stock": stock},
            })
    except Exception as e:
        print(f"[ml_calendar] _get_alerts stock: {e}")

    # Preguntas sin responder ---------------------------------------
    try:
        import ml_api
        if ml_user_id:
            msgs = ml_api._eq(
                "SELECT ml_pack_id, text, sent_at FROM ml_messages "
                "WHERE ml_user_id=%s AND from_role='buyer' "
                "  AND sent_at >= NOW() - INTERVAL '24 hours' "
                "ORDER BY sent_at DESC LIMIT 10",
                (ml_user_id,), fetch="all") or []
            seen = set()
            for (pack_id, text, sent_at) in msgs:
                if pack_id in seen:
                    continue
                seen.add(pack_id)
                resp = ml_api._eq(
                    "SELECT COUNT(*) FROM ml_messages "
                    "WHERE ml_pack_id=%s AND from_role='seller' AND sent_at > %s",
                    (pack_id, sent_at), fetch="one")
                if not resp or not resp[0]:
                    alerts.append({
                        "type":  "PREGUNTA_NUEVA",
                        "title": "Pregunta sin responder",
                        "body":  f"Pack #{pack_id} — {(text or '')[:50]}",
                        "color": C_PREGUNTA, "icon": "?", "ts": now,
                        "data":  {"pack_id": pack_id},
                    })
    except Exception:
        pass  # silencioso — preguntas es opcional

    priority = {
        "DESPACHO_URGENTE": 0, "FLEX_PENDIENTE": 1,
        "DESPACHO_HOY": 2, "PREGUNTA_NUEVA": 3,
        "STOCK_BAJO": 4,
    }
    alerts.sort(key=lambda a: priority.get(a["type"], 9))
    return alerts


# ══════════════════════════════════════════════════════════════
#  Daemon de notificaciones en background
# ══════════════════════════════════════════════════════════════

_daemon_running = False
_last_ids: set  = set()


def start_notification_daemon(ml_user_id: str, on_notify, interval: int = 90):
    """
    Lanza hilo que llama on_notify(all_alerts, new_alerts) cada `interval` segundos.
    on_notify se ejecuta en hilo secundario; el caller debe usar .after() para UI.
    """
    global _daemon_running
    _daemon_running = True

    def _loop():
        global _last_ids
        while _daemon_running:
            try:
                alerts  = _get_alerts(ml_user_id)

                def _key(a):
                    d = a["data"]
                    return f"{a['type']}:{d.get('order_id') or d.get('product') or d.get('pack_id', '')}"

                new_ids = {_key(a) for a in alerts}
                new     = [a for a in alerts if _key(a) not in _last_ids]
                _last_ids = new_ids
                on_notify(alerts, new)
            except Exception as e:
                print(f"[notif_daemon] {e}")
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True).start()


def stop_notification_daemon():
    global _daemon_running
    _daemon_running = False


# ══════════════════════════════════════════════════════════════
#  Celda de dia del calendario
# ══════════════════════════════════════════════════════════════

class _DayCell(ctk.CTkFrame):
    def __init__(self, parent, day: int, events: list,
                 is_today: bool, is_selected: bool,
                 compact: bool, on_click):
        self._events   = events
        self._is_today = is_today
        self._is_sel   = is_selected
        self._compact  = compact
        self._on_click = on_click
        self._day      = day

        super().__init__(parent, width=40, height=44,
                         fg_color=self._bg(), corner_radius=6,
                         border_width=2 if is_today else 0,
                         border_color=C_MELIA)
        self.pack_propagate(False)
        self._render()
        self.bind("<Button-1>", self._click)

    def _bg(self):
        if self._is_sel:
            return C_MELIA
        dark = ctk.get_appearance_mode() == "Dark"
        if self._events:
            urg  = any(e["urgent"]  for e in self._events)
            flx  = any(e["is_flex"] for e in self._events)
            if urg:  return "#5a1a1a" if dark else "#fee2e2"
            if flx:  return "#0d3320" if dark else "#dcfce7"
            return   "#1a2a3a" if dark else "#dbeafe"
        return theme.CARD2

    def _render(self):
        for w in self.winfo_children():
            w.destroy()
        tc = "#ffffff" if self._is_sel else theme.TEXT
        ctk.CTkLabel(self, text=str(self._day),
                     font=ctk.CTkFont(size=11,
                                      weight="bold" if self._is_today else "normal"),
                     text_color=tc).pack(pady=(5, 0))
        if self._events:
            n   = len(self._events)
            urg = any(e["urgent"]  for e in self._events)
            flx = any(e["is_flex"] for e in self._events)
            dc  = C_URGENTE if urg else (C_FLEX if flx else C_MELIA)
            dc  = "#ffffff" if self._is_sel else dc
            ctk.CTkLabel(self, text=f"*{n}",
                         font=ctk.CTkFont(size=8),
                         text_color=dc).pack()
        for w in self.winfo_children():
            w.bind("<Button-1>", self._click)

    def _click(self, _=None):
        if self._on_click:
            self._on_click()

    def set_selected(self, v: bool):
        self._is_sel = v
        self.configure(fg_color=self._bg())
        tc = "#ffffff" if v else theme.TEXT
        for w in self.winfo_children():
            try:
                w.configure(text_color=tc)
            except Exception:
                pass


class _EmptyCell(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, width=40, height=44,
                         fg_color="transparent", corner_radius=6)
        self.pack_propagate(False)


# ══════════════════════════════════════════════════════════════
#  Widget: Calendario mensual
# ══════════════════════════════════════════════════════════════

class MLCalendarWidget(ctk.CTkFrame):
    def __init__(self, parent, ml_user_id: str = "", app=None, compact: bool = False):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=12,
                         border_width=1, border_color=theme.SEP)
        self._uid      = ml_user_id
        self._app      = app
        self._compact  = compact
        self._today    = date.today()
        self._year     = self._today.year
        self._month    = self._today.month
        self._events   = []
        self._sel_date = None
        self._cells    = {}
        self._build()
        self.refresh()

    # ── Layout ────────────────────────────────────────────────
    def _build(self):
        # Navegacion mes
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=14, pady=(12, 4))

        ctk.CTkButton(nav, text="<", width=28, height=28,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT, corner_radius=6,
                      command=self._prev).pack(side="left")
        self._nav_lbl = ctk.CTkLabel(nav, text="",
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=theme.TEXT_HDR)
        self._nav_lbl.pack(side="left", expand=True)
        ctk.CTkButton(nav, text=">", width=28, height=28,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
                      text_color=theme.TEXT, corner_radius=6,
                      command=self._next).pack(side="right")

        # Leyenda de colores
        leg = ctk.CTkFrame(self, fg_color="transparent")
        leg.pack(fill="x", padx=14, pady=(0, 4))
        for txt, col in [("Urgente", C_URGENTE), ("Flex", C_FLEX), ("Normal", C_MELIA)]:
            ctk.CTkLabel(leg, text=f" {txt} ", fg_color=col,
                         corner_radius=4, text_color="#ffffff",
                         font=ctk.CTkFont(size=8), padx=4, pady=1).pack(
                side="left", padx=2)

        # Cabecera dias de la semana
        dow = ctk.CTkFrame(self, fg_color="transparent")
        dow.pack(fill="x", padx=10, pady=(0, 2))
        for d in DIAS_ES:
            ctk.CTkLabel(dow, text=d, width=40,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=theme.TEXT_DIM).pack(side="left", expand=True)

        # Grid de dias
        self._grid = ctk.CTkFrame(self, fg_color="transparent")
        self._grid.pack(fill="x", padx=8, pady=(0, 8))

        # Panel de detalle (solo en modo no-compact)
        if not self._compact:
            ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
                fill="x", padx=14, pady=(0, 4))
            self._det_title = ctk.CTkLabel(
                self, text="Pedidos del dia seleccionado",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_DIM)
            self._det_title.pack(anchor="w", padx=14)
            self._detail = ctk.CTkScrollableFrame(
                self, fg_color="transparent", height=200)
            self._detail.pack(fill="both", expand=True, padx=8, pady=(2, 8))
            ctk.CTkLabel(self._detail,
                         text="Selecciona un dia para ver los pedidos.",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(pady=16)

    # ── Grid de dias ──────────────────────────────────────────
    def _draw_grid(self):
        for w in self._grid.winfo_children():
            w.destroy()
        self._cells = {}
        self._nav_lbl.configure(text=f"{MESES_ES[self._month]} {self._year}")

        first   = date(self._year, self._month, 1)
        start_c = first.weekday()
        if self._month == 12:
            last = date(self._year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(self._year, self._month + 1, 1) - timedelta(days=1)

        # Indexar eventos por fecha
        evs_by_date: dict = {}
        for ev in self._events:
            d = ev["date"]
            if d.year == self._year and d.month == self._month:
                evs_by_date.setdefault(d, []).append(ev)

        row_f = None
        col   = 0

        for _ in range(start_c):
            if col % 7 == 0:
                row_f = ctk.CTkFrame(self._grid, fg_color="transparent")
                row_f.pack(fill="x")
            _EmptyCell(row_f).pack(side="left", expand=True, padx=1, pady=1)
            col += 1

        for day_n in range(1, last.day + 1):
            if col % 7 == 0:
                row_f = ctk.CTkFrame(self._grid, fg_color="transparent")
                row_f.pack(fill="x")
            d        = date(self._year, self._month, day_n)
            day_evs  = evs_by_date.get(d, [])
            cell = _DayCell(
                row_f, day_n, day_evs,
                is_today=(d == self._today),
                is_selected=(d == self._sel_date),
                compact=self._compact,
                on_click=lambda dt=d: self._click_day(dt))
            cell.pack(side="left", expand=True, padx=1, pady=1)
            self._cells[d] = cell
            col += 1

        rem = 7 - (col % 7)
        if rem < 7 and row_f:
            for _ in range(rem):
                _EmptyCell(row_f).pack(side="left", expand=True, padx=1, pady=1)

    def _click_day(self, d: date):
        if self._sel_date and self._sel_date in self._cells:
            self._cells[self._sel_date].set_selected(False)
        self._sel_date = d
        if d in self._cells:
            self._cells[d].set_selected(True)
        if not self._compact:
            self._show_detail(d)

    def _show_detail(self, d: date):
        for w in self._detail.winfo_children():
            w.destroy()
        day_evs = [ev for ev in self._events if ev["date"] == d]
        self._det_title.configure(text=f"Pedidos del {d.strftime('%d/%m/%Y')}")
        if not day_evs:
            ctk.CTkLabel(self._detail,
                         text="Sin pedidos para este dia.",
                         text_color=theme.TEXT_DIM,
                         font=ctk.CTkFont(size=11)).pack(pady=16)
            return
        for ev in sorted(day_evs, key=lambda x: (not x["urgent"], not x["is_flex"])):
            self._render_event_card(self._detail, ev)

    def _render_event_card(self, parent, ev: dict):
        dark    = ctk.get_appearance_mode() == "Dark"
        urgent  = ev["urgent"]
        is_flex = ev["is_flex"]
        bg  = ("#3b1212" if dark else "#fff5f5") if urgent else (
              ("#0d3320" if dark else "#f0fdf4") if is_flex else theme.CARD2)
        bdr = C_URGENTE if urgent else (C_FLEX if is_flex else theme.SEP)

        card = ctk.CTkFrame(parent, fg_color=bg, corner_radius=8,
                            border_width=1, border_color=bdr)
        card.pack(fill="x", pady=3, padx=2)

        # Fila superior: badges + talle
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))
        b_text  = "FLEX"   if is_flex  else "Correo"
        b_color = C_FLEX   if is_flex  else C_MELIA
        ctk.CTkLabel(top, text=b_text, fg_color=b_color, corner_radius=4,
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#ffffff", padx=6, pady=2).pack(side="left")
        if urgent:
            ctk.CTkLabel(top, text="URGENTE", fg_color=C_URGENTE, corner_radius=4,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color="#ffffff", padx=6, pady=2).pack(
                side="left", padx=(4, 0))
        ctk.CTkLabel(top, text=f"Talle: {ev['size']}",
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM).pack(side="right")

        # Info del pedido
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(info,
                     text=f"Orden #{ev['order_id']}  |  {ev['buyer']}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(info, text=ev["title"],
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM).pack(anchor="w")
        dr = ctk.CTkFrame(info, fg_color="transparent")
        dr.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(dr,
                     text=f"Cant: {ev['qty']}  |  Total: ${ev['total']:,.0f}",
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM).pack(side="left")
        if ev.get("sla_limit"):
            ctk.CTkLabel(dr,
                         text=f"SLA: {str(ev['sla_limit'])[:16]}",
                         font=ctk.CTkFont(size=10),
                         text_color=C_URGENTE if urgent else theme.TEXT_DIM).pack(
                side="right")

    def _prev(self):
        if self._month == 1:
            self._month = 12; self._year -= 1
        else:
            self._month -= 1
        self._draw_grid()

    def _next(self):
        if self._month == 12:
            self._month = 1; self._year += 1
        else:
            self._month += 1
        self._draw_grid()

    def set_ml_user(self, uid: str):
        self._uid = uid
        self.refresh()

    def refresh(self):
        uid = self._uid
        def _load():
            evs = _get_events(uid)
            self.after(0, lambda e=evs: self._apply(e))
        threading.Thread(target=_load, daemon=True).start()

    def _apply(self, events):
        self._events = events
        self._draw_grid()
        if self._sel_date and not self._compact:
            self._show_detail(self._sel_date)


# ══════════════════════════════════════════════════════════════
#  Widget: Panel de notificaciones
# ══════════════════════════════════════════════════════════════

class NotificationPanel(ctk.CTkFrame):
    def __init__(self, parent, ml_user_id: str = "", app=None):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=12,
                         border_width=1, border_color=theme.SEP)
        self._uid    = ml_user_id
        self._app    = app
        self._alerts = []
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(hdr, text="Alertas activas",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(side="left")
        self._badge = ctk.CTkLabel(
            hdr, text="0", fg_color=C_URGENTE, corner_radius=10,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#ffffff", padx=6, pady=1)
        self._badge.pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            hdr, text="Actualizar", width=80, height=26,
            fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
            text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=10),
            command=self.refresh).pack(side="right")

        ctk.CTkFrame(self, height=1, fg_color=theme.SEP).pack(
            fill="x", padx=12, pady=(4, 0))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=6, pady=(4, 8))

        ctk.CTkLabel(self._scroll,
                     text="Cargando alertas...",
                     text_color=theme.TEXT_DIM,
                     font=ctk.CTkFont(size=11)).pack(pady=20)

    def update_alerts(self, alerts: list):
        self._alerts = alerts
        self._render()

    def _render(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not self._alerts:
            ctk.CTkLabel(self._scroll,
                         text="Sin alertas. Todo en orden.",
                         font=ctk.CTkFont(size=12),
                         text_color=theme.C_GREEN).pack(pady=20)
            self._badge.configure(text="0", fg_color=theme.CARD2,
                                  text_color=theme.TEXT_DIM)
            return

        urgent_n = sum(1 for a in self._alerts if a["type"] == "DESPACHO_URGENTE")
        bc = C_URGENTE if urgent_n else C_WARN
        self._badge.configure(
            text=str(len(self._alerts)), fg_color=bc, text_color="#ffffff")

        # Agrupar por tipo
        GROUPS = [
            ("DESPACHO_URGENTE", "Despachos urgentes",    C_URGENTE),
            ("FLEX_PENDIENTE",   "Envios Flex",            C_FLEX),
            ("DESPACHO_HOY",     "Despachar hoy",          C_WARN),
            ("PREGUNTA_NUEVA",   "Preguntas sin responder", C_PREGUNTA),
            ("STOCK_BAJO",       "Stock bajo",             C_STOCK),
        ]
        for gtype, glabel, gcolor in GROUPS:
            group = [a for a in self._alerts if a["type"] == gtype]
            if not group:
                continue
            # Separador de grupo
            gh = ctk.CTkFrame(self._scroll, fg_color="transparent")
            gh.pack(fill="x", pady=(8, 2), padx=2)
            ctk.CTkFrame(gh, width=3, height=14,
                         fg_color=gcolor, corner_radius=2).pack(side="left", padx=(2, 6))
            ctk.CTkLabel(gh, text=f"{glabel} ({len(group)})",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=gcolor).pack(side="left")
            for a in group:
                self._render_row(a)

    def _render_row(self, a: dict):
        color = a["color"]
        card  = ctk.CTkFrame(self._scroll, fg_color=theme.CARD2,
                             corner_radius=8, border_width=1,
                             border_color=color)
        card.pack(fill="x", pady=2, padx=2)
        # Barra lateral
        ctk.CTkFrame(card, width=4, fg_color=color,
                     corner_radius=2).pack(side="left", fill="y")
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=6)
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill="x")
        ctk.CTkLabel(row1, text=f"[{a['icon']}] {a['title']}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=color).pack(side="left")
        ts = a["ts"].strftime("%H:%M") if hasattr(a["ts"], "strftime") else ""
        ctk.CTkLabel(row1, text=ts,
                     font=ctk.CTkFont(size=9),
                     text_color=theme.TEXT_DIM).pack(side="right")
        ctk.CTkLabel(content, text=a["body"],
                     font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_DIM,
                     wraplength=240, justify="left").pack(anchor="w")

    def refresh(self):
        uid = self._uid
        def _load():
            alerts = _get_alerts(uid)
            self.after(0, lambda a=alerts: self.update_alerts(a))
        threading.Thread(target=_load, daemon=True).start()

    def set_ml_user(self, uid: str):
        self._uid = uid
        self.refresh()


# ══════════════════════════════════════════════════════════════
#  Widget: Campana con badge (para headers)
# ══════════════════════════════════════════════════════════════

class NotificationBell(ctk.CTkFrame):
    def __init__(self, parent, ml_user_id: str = "", app=None):
        super().__init__(parent, fg_color="transparent")
        self._uid    = ml_user_id
        self._app    = app
        self._alerts = []
        self._btn = ctk.CTkButton(
            self, text="Alertas  0", width=100, height=32,
            fg_color=theme.CARD2, hover_color=theme.ACCENT_H,
            text_color=theme.TEXT_DIM, font=ctk.CTkFont(size=11),
            corner_radius=8, command=self._open_popup)
        self._btn.pack()
        self.refresh()

    def _open_popup(self):
        _NotifPopup(self, self._alerts, self._uid, self._app)

    def update_alerts(self, alerts: list):
        self._alerts = alerts
        n   = len(alerts)
        urg = sum(1 for a in alerts if a["type"] == "DESPACHO_URGENTE")
        col = C_URGENTE if urg else (C_WARN if n else theme.TEXT_DIM)
        self._btn.configure(text=f"Alertas  {n}", text_color=col)

    def refresh(self):
        uid = self._uid
        def _load():
            a = _get_alerts(uid)
            self.after(0, lambda x=a: self.update_alerts(x))
        threading.Thread(target=_load, daemon=True).start()

    def set_ml_user(self, uid: str):
        self._uid = uid
        self.refresh()


class _NotifPopup(ctk.CTkToplevel):
    def __init__(self, parent, alerts, uid, app):
        super().__init__(parent)
        self.title("Notificaciones CoreStack")
        self.geometry("440x580")
        self.resizable(False, True)
        self.grab_set()
        self.focus()
        p = NotificationPanel(self, uid, app)
        p.pack(fill="both", expand=True, padx=10, pady=10)
        p.update_alerts(alerts)
        ctk.CTkButton(self, text="Cerrar", height=34,
                      fg_color=theme.CARD2, hover_color=theme.ACCENT,
                      command=self.destroy).pack(fill="x", padx=10, pady=(0, 10))


# ══════════════════════════════════════════════════════════════
#  Frame principal: Calendario + Alertas
#  Insertar en dashboard.py como seccion del scroll
# ══════════════════════════════════════════════════════════════

class MLDashboardCalendarFrame(ctk.CTkFrame):
    """
    Frame todo-en-uno: calendario a la izquierda, alertas a la derecha.
    Uso en dashboard.py:

        from ml_calendar import MLDashboardCalendarFrame

        # En _build_ui(), dentro del scroll:
        self._cal_block = MLDashboardCalendarFrame(self._scroll, app=self)
        self._cal_block.pack(fill="both", expand=True, pady=(0, 16))

        # Cuando se conoce el ml_user_id (desde on_show o al navegar):
        self._cal_block.set_ml_user("123456789")
    """

    def __init__(self, parent, ml_user_id: str = "", app=None):
        super().__init__(parent, fg_color="transparent")
        self._uid  = ml_user_id
        self._app  = app
        self._daemon_started = False
        self._build()

    def _build(self):
        # Header de seccion
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(hdr, text="Calendario de Despachos",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=theme.TEXT_HDR).pack(side="left")

        self._bell = NotificationBell(hdr, self._uid, self._app)
        self._bell.pack(side="right")

        ctk.CTkButton(hdr, text="Actualizar todo", width=120, height=32,
                      fg_color=C_MELIA, hover_color="#2563eb",
                      font=ctk.CTkFont(size=11),
                      command=self.refresh_all).pack(side="right", padx=(0, 8))

        # Cuerpo: split calendario | alertas
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        self._cal = MLCalendarWidget(
            split, ml_user_id=self._uid, app=self._app, compact=False)
        self._cal.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._panel = NotificationPanel(
            split, ml_user_id=self._uid, app=self._app)
        self._panel.grid(row=0, column=1, sticky="nsew")

    def _ensure_daemon(self):
        if self._daemon_started or not self._uid:
            return
        self._daemon_started = True
        def _cb(all_alerts, _new):
            self.after(0, lambda a=all_alerts: self._on_alerts(a))
        start_notification_daemon(self._uid, _cb, interval=90)

    def _on_alerts(self, alerts: list):
        self._panel.update_alerts(alerts)
        self._bell.update_alerts(alerts)

    def set_ml_user(self, uid: str):
        self._uid = uid
        self._cal.set_ml_user(uid)
        self._panel.set_ml_user(uid)
        self._bell.set_ml_user(uid)
        self._ensure_daemon()

    def refresh_all(self):
        self._cal.refresh()
        self._panel.refresh()
        self._bell.refresh()

    def on_show(self):
        self._ensure_daemon()
        self.refresh_all()

    def on_hide(self):
        pass
