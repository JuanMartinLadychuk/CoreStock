"""
server.py – CoreStack Pro v0.9  |  Render.com deployment
Endpoints:
  GET  /                    → health check
  GET  /oauth/callback      → intercepts ML OAuth redirect
  POST /webhook-mp          → MercadoPago notifications
  POST /ml/exchange         → exchange OAuth code for token
  GET  /ml/accounts         → list connected ML accounts
  GET  /ml/dashboard/<uid>  → KPIs for a ML user
"""

import os
import json
from flask import Flask, request, jsonify, redirect

# ml_api usa neon_db internamente; mercadolibre.py es sólo UI desktop → no se importa
import ml_api

app = Flask(__name__)


# ──────────────────────────────────────────────────────────────
#  Health check
# ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return "CoreStack Pro v0.9 — online", 200


# ──────────────────────────────────────────────────────────────
#  OAuth callback  →  ML redirige a https://coresstack.onrender.com/oauth/callback?code=TG-xxx
# ──────────────────────────────────────────────────────────────
@app.route("/oauth/callback")
def oauth_callback():
    code  = request.args.get("code", "")
    error = request.args.get("error", "")

    if error:
        return f"<h2>Error OAuth: {error}</h2>", 400

    if not code:
        return "<h2>Sin código de autorización.</h2>", 400

    try:
        resp = ml_api.exchange_code_for_token(code)
        uid  = resp.get("user_id", "—")
        nick = ""
        try:
            info = ml_api._get(
                f"{ml_api.ML_BASE}/users/{uid}",
                token=resp.get("access_token", ""))
            nick = info.get("nickname", "")
        except Exception:
            pass
        return (
            f"<h2>✅ Cuenta vinculada</h2>"
            f"<p>Usuario: <b>{nick or uid}</b></p>"
            f"<p>Podés cerrar esta ventana y volver a CoreStack Pro.</p>"
        ), 200
    except Exception as e:
        return f"<h2>❌ Error al vincular cuenta</h2><pre>{e}</pre>", 500


# ──────────────────────────────────────────────────────────────
#  Webhook MercadoPago
# ──────────────────────────────────────────────────────────────
@app.route("/webhook-mp", methods=["POST"])
def webhook_mp():
    data = request.get_json(silent=True) or {}
    print(f"[webhook-mp] {json.dumps(data)[:500]}")

    topic   = data.get("topic") or request.args.get("topic", "")
    res_id  = data.get("resource") or request.args.get("id", "")

    # Notificación de orden de ML
    if topic in ("orders_v2", "orders", "merchant_orders"):
        try:
            # Refrescar la orden en Neon si tenemos el id
            order_id = str(res_id).split("/")[-1]
            # Sin ML user_id en el webhook firmado genérico,
            # iteramos cuentas activas
            accounts = ml_api.get_all_ml_accounts()
            for acc in accounts:
                ml_uid = str(acc[0])
                try:
                    token = ml_api.get_valid_token(ml_uid)
                    order = ml_api._get(
                        f"{ml_api.ML_BASE}/orders/{order_id}", token=token)
                    ml_api._upsert_order(order, ml_uid)
                    break
                except Exception:
                    continue
        except Exception as e:
            print(f"[webhook-mp] error procesando orden: {e}")

    return jsonify({"status": "received"}), 200


# ──────────────────────────────────────────────────────────────
#  API REST helpers (opcionales, para integración futura)
# ──────────────────────────────────────────────────────────────

@app.route("/ml/exchange", methods=["POST"])
def ml_exchange():
    """Canjea un código OAuth por token. Body JSON: {"code": "TG-..."}"""
    body = request.get_json(silent=True) or {}
    code = body.get("code", "")
    if not code:
        return jsonify({"error": "missing code"}), 400
    try:
        resp = ml_api.exchange_code_for_token(code)
        return jsonify({"user_id": resp.get("user_id"),
                        "nickname": resp.get("nickname", "")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ml/accounts")
def ml_accounts():
    try:
        rows = ml_api.get_all_ml_accounts()
        return jsonify([
            {"ml_user_id": r[0], "nickname": r[1],
             "expires_at": str(r[2]) if r[2] else None,
             "active": bool(r[3])}
            for r in rows
        ]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ml/dashboard/<ml_user_id>")
def ml_dashboard(ml_user_id):
    try:
        stats = ml_api.get_ml_dashboard_stats(ml_user_id)
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
