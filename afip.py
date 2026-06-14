"""
afip.py – Integración con AFIP WSFEv1 para CoreStack Pro.

Requisitos:
  pip install zeep cryptography

Pasos para obtener el certificado:
  1. Generá un par de claves:
       openssl genrsa -out private.key 2048
       openssl req -new -key private.key -subj "/C=AR/CN=CUIT-TU_CUIT" -out csr.csr
  2. En https://auth.afip.gob.ar → Administrador de Relaciones
       → Adherir Servicio → wsfe (Facturación Electrónica)
       → Cargá el .csr y descargá el .crt resultante
  3. Guardá private.key y el .crt en rutas accesibles y configurá
       en CoreStack: Configuración → AFIP

Modos:
  homologacion  → https://wsaahomo.afip.gov.ar  (pruebas)
  produccion    → https://wsaa.afip.gov.ar       (real)
"""

import os
import base64
import hashlib
import datetime
from pathlib import Path


# ── Verificación de dependencias ───────────────────────────────

def verificar_instalacion() -> tuple[bool, str]:
    """
    Verifica que zeep y cryptography estén instalados.
    Retorna (ok: bool, mensaje: str).
    Usado desde config.py → _check_afip_deps().
    """
    missing = []
    try:
        import zeep  # noqa: F401
    except ImportError:
        missing.append("zeep")
    try:
        from cryptography import x509  # noqa: F401
    except ImportError:
        missing.append("cryptography")

    if missing:
        return False, f"Falta instalar: {', '.join(missing)}"
    return True, "zeep y cryptography instalados"


# ── URLs por entorno ───────────────────────────────────────────

_WSAA_URLS = {
    "homologacion": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl",
    "produccion":   "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl",
}

_WSFE_URLS = {
    "homologacion": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    "produccion":   "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
}

# Tiempo de vida del ticket de acceso (10 horas menos buffer)
_TICKET_TTL_SECONDS = 35000


# ── LoginTicket (WSAA) ─────────────────────────────────────────

def _build_tra(service: str = "wsfe", ttl: int = _TICKET_TTL_SECONDS) -> str:
    """Construye el TRA (Ticket de Requerimiento de Acceso) en XML."""
    now        = datetime.datetime.utcnow()
    generation = (now - datetime.timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration = (now + datetime.timedelta(seconds=ttl)).strftime("%Y-%m-%dT%H:%M:%S")
    unique_id  = hashlib.md5(
        (service + generation).encode()
    ).hexdigest()[:8]

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<loginTicketRequest version=\"1.0\">"
        f"  <header>"
        f"    <uniqueId>{unique_id}</uniqueId>"
        f"    <generationTime>{generation}</generationTime>"
        f"    <expirationTime>{expiration}</expirationTime>"
        f"  </header>"
        f"  <service>{service}</service>"
        "</loginTicketRequest>"
    )


def _sign_tra(tra_xml: str, cert_path: str, key_path: str) -> str:
    """
    Firma el TRA con el certificado y clave privada usando CMS/PKCS#7.
    Retorna el CMS en base64.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs7

    # Leer certificado
    cert_path = Path(cert_path)
    key_path  = Path(key_path)

    if not cert_path.exists():
        raise FileNotFoundError(f"Certificado no encontrado: {cert_path}")
    if not key_path.exists():
        raise FileNotFoundError(f"Clave privada no encontrada: {key_path}")

    cert_data = cert_path.read_bytes()
    key_data  = key_path.read_bytes()

    # Cargar certificado (PEM o DER)
    try:
        cert = x509.load_pem_x509_certificate(cert_data)
    except Exception:
        cert = x509.load_der_x509_certificate(cert_data)

    # Cargar clave privada
    try:
        private_key = serialization.load_pem_private_key(key_data, password=None)
    except Exception:
        private_key = serialization.load_der_private_key(key_data, password=None)

    # Firmar
    data    = tra_xml.encode("utf-8")
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(data)
        .add_signer(cert, private_key, hashes.SHA256())
    )
    signed = builder.sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    return base64.b64encode(signed).decode("utf-8")


def _parse_ticket(ticket_xml: str) -> dict:
    """Parsea el TA (Ticket de Acceso) devuelto por WSAA."""
    import xml.etree.ElementTree as ET
    root  = ET.fromstring(ticket_xml)
    token = root.findtext(".//token") or ""
    sign  = root.findtext(".//sign")  or ""
    exp   = root.findtext(".//expirationTime") or ""
    return {"token": token, "sign": sign, "expiration": exp}


# ── Cliente principal ──────────────────────────────────────────

class WSFEClient:
    """
    Cliente para el Web Service de Facturación Electrónica v1 (WSFEv1).

    Uso básico:
        client = WSFEClient.from_settings()
        nro, cae, vto = client.autorizar(
            tipo_cbte=11, concepto=1,
            total=1210.00, neto=1000.00, iva=210.00
        )
    """

    def __init__(
        self,
        cuit:       str,
        cert_path:  str,
        key_path:   str,
        punto_venta: int  = 1,
        modo:       str   = "homologacion",
    ):
        self.cuit         = str(cuit).replace("-", "")
        self.cert_path    = cert_path
        self.key_path     = key_path
        self.punto_venta  = int(punto_venta)
        self.modo         = modo
        self._token: str  = ""
        self._sign:  str  = ""
        self._ticket_exp: datetime.datetime | None = None

    # ── Constructor desde settings de CoreStack ────────────────

    @classmethod
    def from_settings(cls) -> "WSFEClient":
        """
        Crea un WSFEClient leyendo la configuración guardada en la BD
        (via api.get_setting).
        """
        import api  # importación local para evitar circularidad
        cuit        = api.get_setting("company_cuit", "").replace("-", "")
        cert_path   = api.get_setting("afip_cert_path",   "")
        key_path    = api.get_setting("afip_key_path",    "")
        punto_venta = int(api.get_setting("afip_punto_venta", "1") or 1)
        modo        = api.get_setting("afip_modo", "homologacion")

        if not cuit:
            raise ValueError(
                "CUIT no configurado. "
                "Completá Configuración → Empresa → CUIT/CUIL."
            )
        if not cert_path or not key_path:
            raise ValueError(
                "Certificado o clave privada no configurados. "
                "Completá Configuración → AFIP."
            )
        return cls(
            cuit=cuit,
            cert_path=cert_path,
            key_path=key_path,
            punto_venta=punto_venta,
            modo=modo,
        )

    # ── Autenticación (WSAA) ───────────────────────────────────

    def _ticket_vigente(self) -> bool:
        if not self._token or not self._ticket_exp:
            return False
        return datetime.datetime.utcnow() < self._ticket_exp

    def _autenticar(self):
        """Obtiene un nuevo Ticket de Acceso de WSAA."""
        import zeep

        tra_xml = _build_tra(service="wsfe")
        cms     = _sign_tra(tra_xml, self.cert_path, self.key_path)

        wsaa_url = _WSAA_URLS.get(self.modo, _WSAA_URLS["homologacion"])
        client   = zeep.Client(wsdl=wsaa_url)
        response = client.service.loginCms(in0=cms)

        ticket = _parse_ticket(response)
        self._token = ticket["token"]
        self._sign  = ticket["sign"]

        # Parsear expiración
        try:
            exp_str = ticket["expiration"][:19]  # "2024-01-01T12:00:00"
            self._ticket_exp = datetime.datetime.strptime(
                exp_str, "%Y-%m-%dT%H:%M:%S"
            ) - datetime.timedelta(minutes=5)
        except Exception:
            self._ticket_exp = datetime.datetime.utcnow() + datetime.timedelta(hours=9)

    def _get_auth(self) -> dict:
        """Retorna el bloque de autenticación para las llamadas a WSFE."""
        if not self._ticket_vigente():
            self._autenticar()
        return {
            "Token": self._token,
            "Sign":  self._sign,
            "Cuit":  self.cuit,
        }

    # ── Helpers WSFE ──────────────────────────────────────────

    def _wsfe_client(self):
        import zeep
        wsfe_url = _WSFE_URLS.get(self.modo, _WSFE_URLS["homologacion"])
        return zeep.Client(wsdl=wsfe_url)

    # ── Último comprobante autorizado ──────────────────────────

    def ultimo_comprobante(self, tipo_cbte: int) -> int:
        """
        Retorna el último número de comprobante autorizado para el
        tipo y punto de venta configurados.
        Útil para testear la conexión desde config.py.
        """
        client = self._wsfe_client()
        auth   = self._get_auth()
        result = client.service.FECompUltimoAutorizado(
            Auth=auth,
            PtoVta=self.punto_venta,
            CbteTipo=tipo_cbte,
        )
        if result.Errors:
            err = result.Errors.Err[0]
            raise RuntimeError(f"AFIP error {err.Code}: {err.Msg}")
        return int(result.CbteNro)

    # ── Autorización de comprobante ────────────────────────────

    def autorizar(
        self,
        tipo_cbte:  int,
        concepto:   int,
        total:      float,
        neto:       float,
        iva:        float,
        cuit_receptor: str = "0",
        doc_tipo:   int   = 99,   # 99 = Consumidor final
        doc_nro:    str   = "0",
        condicion_iva_receptor: int = 5,  # 5 = Consumidor Final
    ) -> tuple[int, str, str]:
        """
        Autoriza un comprobante ante AFIP.

        Args:
            tipo_cbte:  Tipo de comprobante (1=FA, 6=FB, 11=FC, etc.)
            concepto:   1=Productos, 2=Servicios, 3=Productos y Servicios
            total:      Importe total del comprobante
            neto:       Importe neto gravado
            iva:        Importe de IVA
            cuit_receptor: CUIT del comprador (0 para consumidor final)
            doc_tipo:   Tipo de documento del receptor (99 = sin especificar)
            doc_nro:    Número de documento del receptor

        Returns:
            (nro_comprobante, cae, cae_vencimiento_str)
        """
        client = self._wsfe_client()
        auth   = self._get_auth()

        # Obtener próximo número
        ultimo = self.ultimo_comprobante(tipo_cbte)
        nro    = ultimo + 1

        fecha_hoy = datetime.date.today().strftime("%Y%m%d")

        # Alícuotas IVA según tipo de comprobante
        # Para Monotributo (FC tipo 11) no va desglose de IVA
        iva_array = None
        if tipo_cbte in (1, 2, 3, 6, 7, 8):  # FA, FB y sus ND/NC
            # Alícuota 5 = 21%
            iva_array = {
                "AlicIva": [{
                    "Id":     5,
                    "BaseImp": round(neto, 2),
                    "Importe": round(iva, 2),
                }]
            }
            neto_no_gravado = 0.0
            iva_total       = round(iva, 2)
        else:
            # FC (Monotributo): neto = total, sin IVA discriminado
            neto            = round(total, 2)
            iva_total       = 0.0
            neto_no_gravado = 0.0

        fe_det_req = {
            "FECAEDetRequest": [{
                "Concepto":    concepto,
                "DocTipo":     doc_tipo,
                "DocNro":      doc_nro,
                "CbteDesde":   nro,
                "CbteHasta":   nro,
                "CbteFch":     fecha_hoy,
                "ImpTotal":    round(total, 2),
                "ImpTotConc":  0.0,
                "ImpNeto":     round(neto, 2),
                "ImpOpEx":     0.0,
                "ImpIVA":      iva_total,
                "ImpTrib":     0.0,
                "MonId":       "PES",
                "MonCotiz":    1.0,
                **({"Iva": iva_array} if iva_array else {}),
            }]
        }

        # Para conceptos 2 y 3 (servicios) se requieren fechas de servicio
        if concepto in (2, 3):
            fe_det_req["FECAEDetRequest"][0]["FchServDesde"] = fecha_hoy
            fe_det_req["FECAEDetRequest"][0]["FchServHasta"] = fecha_hoy
            fe_det_req["FECAEDetRequest"][0]["FchVtoPago"]   = fecha_hoy

        result = client.service.FECAESolicitar(
            Auth=auth,
            FeCAEReq={
                "FeCabReq": {
                    "CantReg":  1,
                    "PtoVta":   self.punto_venta,
                    "CbteTipo": tipo_cbte,
                },
                "FeDetReq": fe_det_req,
            }
        )

        # Verificar errores globales
        if result.Errors:
            err = result.Errors.Err[0]
            raise RuntimeError(f"AFIP error {err.Code}: {err.Msg}")

        det = result.FeDetResp.FECAEDetResponse[0]

        if det.Resultado != "A":
            obs = ""
            if det.Observaciones:
                obs = " | ".join(
                    f"{o.Code}: {o.Msg}"
                    for o in det.Observaciones.Obs
                )
            raise RuntimeError(
                f"Comprobante rechazado por AFIP. "
                f"Resultado: {det.Resultado}. {obs}"
            )

        cae     = det.CAE
        cae_vto = det.CAEFchVto  # formato "AAAAMMDD"

        # Formatear vencimiento como "DD/MM/AAAA"
        try:
            cae_vto_fmt = datetime.datetime.strptime(
                str(cae_vto), "%Y%m%d"
            ).strftime("%d/%m/%Y")
        except Exception:
            cae_vto_fmt = str(cae_vto)

        return nro, cae, cae_vto_fmt

    # ── Consulta de comprobante ya autorizado ──────────────────

    def consultar_comprobante(
        self,
        tipo_cbte: int,
        nro: int,
    ) -> dict:
        """
        Consulta los datos de un comprobante ya autorizado.
        Retorna un dict con los campos devueltos por AFIP.
        """
        client = self._wsfe_client()
        auth   = self._get_auth()
        result = client.service.FECompConsultar(
            Auth=auth,
            FeCompConsReq={
                "CbteTipo": tipo_cbte,
                "CbteNro":  nro,
                "PtoVta":   self.punto_venta,
            }
        )
        if result.Errors:
            err = result.Errors.Err[0]
            raise RuntimeError(f"AFIP error {err.Code}: {err.Msg}")

        det = result.ResultGet
        return {
            "nro":         int(det.CbteDesde),
            "fecha":       str(det.CbteFch),
            "total":       float(det.ImpTotal),
            "neto":        float(det.ImpNeto),
            "iva":         float(det.ImpIVA),
            "cae":         str(det.CodAutorizacion),
            "cae_vto":     str(det.FchVtoCAE),
            "resultado":   str(det.Resultado),
        }

    # ── Tipos de comprobante disponibles ──────────────────────

    def get_tipos_comprobante(self) -> list[dict]:
        """Retorna los tipos de comprobante habilitados para el CUIT."""
        client = self._wsfe_client()
        auth   = self._get_auth()
        result = client.service.FEParamGetTiposCbte(Auth=auth)
        if result.Errors:
            err = result.Errors.Err[0]
            raise RuntimeError(f"AFIP error {err.Code}: {err.Msg}")
        return [
            {"id": int(t.Id), "desc": str(t.Desc)}
            for t in result.ResultGet.CbteTipo
        ]

    # ── Puntos de venta activos ────────────────────────────────

    def get_puntos_venta(self) -> list[dict]:
        """Retorna los puntos de venta habilitados para el CUIT."""
        client = self._wsfe_client()
        auth   = self._get_auth()
        result = client.service.FEParamGetPtosVenta(Auth=auth)
        if result.Errors:
            err = result.Errors.Err[0]
            raise RuntimeError(f"AFIP error {err.Code}: {err.Msg}")
        puntos = []
        if result.ResultGet and result.ResultGet.PtoVenta:
            for pv in result.ResultGet.PtoVenta:
                puntos.append({
                    "nro":    int(pv.Nro),
                    "tipo":   str(pv.EmisionTipo),
                    "activo": bool(pv.Bloqueado == "N"),
                })
        return puntos
