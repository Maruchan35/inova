"""Piezas compartidas del recolector de fuentes oficiales (catálogo, sitios, rastreo y descarga)."""

import asyncio
import csv
import itertools
import re
import struct
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCUMENTOS = RAIZ / "documentos"            # aquí se guarda todo, por estado, municipio y sección
FUENTES = DOCUMENTOS / "_catalogo"          # catálogos, sitios oficiales y enlaces encontrados
DATOS = RAIZ / "datos"                      # solo se lee datos/documentos.csv para no repetir documentos

# Nos identificamos siempre: son sitios públicos, pero que sepan quién consulta y para qué.
AGENTE = "CabildoAbiertoAI-recolector/0.1 (Hackaton TecNM, consulta de informacion publica)"

# Las 5 secciones fijas de la plataforma (datos/seed.sql), con las palabras que las delatan en un
# enlace o en su texto. El orden importa: gana la primera sección que coincide.
SECCIONES = {
    "informes": [
        "informe de gobierno", "informe de labores", "informe anual", "informe municipal",
        "primer informe", "segundo informe", "tercer informe", "cuarto informe", "quinto informe",
        "sexto informe", "informe de actividades", "informe", "plan municipal de desarrollo",
        "plan estatal de desarrollo", "plan de desarrollo",
    ],
    "presupuesto": [
        "presupuesto de egresos", "presupuesto ciudadano", "ley de ingresos", "presupuesto",
        "cuenta publica", "egresos", "ingresos", "armonizacion contable", "conac", "ldf",
        "estados financieros", "informacion financiera", "deuda publica", "disciplina financiera",
        "avance de gestion", "situacion financiera", "finanzas", "tesoreria", "paquete economico",
        "informe analitico", "estado analitico", "balance presupuestario", "objeto del gasto",
        "clasificacion administrativa", "clasificacion funcional", "clasificacion programatica", "endeudamiento",
        "calendario de ingresos", "calendario de egresos", "notas a los estados financieros",
        "estado de actividades", "flujo de efectivo", "informe sobre la situacion economica",
        "gasto federalizado", "participaciones", "aportaciones", "fortamun", "recursos federales",
        "obligaciones diferentes de financiamientos", "proyecto de presupuesto", "tabulador",
    ],
    "obras": [
        "obra publica", "obras publicas", "programa de obra", "programa anual de obra", "fais",
        "fism", "ramo 33", "infraestructura", "obra", "obras",
    ],
    "actas": [
        "actas de cabildo", "acta de cabildo", "sesiones de cabildo", "sesion de cabildo", "cabildo",
        "gaceta municipal", "gaceta", "acuerdos del ayuntamiento", "actas", "acta", "sesion ordinaria",
        "sesion extraordinaria", "sesion solemne", "orden del dia", "acuerdos de cabildo", "acta de sesion",
        "diario de los debates",
    ],
    "contratos": [
        "licitaciones", "licitacion", "contratos", "contrato", "adjudicacion", "adjudicaciones",
        "compras", "adquisiciones", "proveedores", "padron de proveedores", "invitacion restringida",
        "concurso", "fallo", "acta de fallo", "junta de aclaraciones", "apertura de propuestas",
        "bases de licitacion", "adjudicacion directa", "invitacion a cuando menos tres",
    ],
}

EXTENSIONES_DOC = (".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip")


def normalizar(texto: str) -> str:
    """'  León ' → 'leon': para comparar nombres sin importar acentos, mayúsculas ni espacios."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sin_acentos.casefold().split())


def palabras(texto: str) -> str:
    """Texto normalizado y sin signos, para buscar frases clave: 'Cuenta_Pública-2025.pdf' → 'cuenta publica 2025 pdf'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).split())


def clasificar(texto: str) -> str | None:
    """Sección de la plataforma a la que pertenece un enlace, según su texto y su dirección.

    Gana la frase más específica: 'Informe de avance de gestión financiera' es presupuesto
    ('avance de gestion') y no informes ('informe')."""
    t = f" {palabras(texto)} "
    mejor, largo = None, 0
    for seccion, claves in SECCIONES.items():
        for clave in claves:
            if len(clave) > largo and f" {clave} " in t:
                mejor, largo = seccion, len(clave)
    return mejor


def anio(texto: str) -> str:
    """El año más reciente que aparezca en el texto (2000-2029), o '' si no hay."""
    anios = [int(a) for a in re.findall(r"(?<!\d)(20[0-2]\d)(?!\d)", texto)]
    return str(max(anios)) if anios else ""


def escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    """CSV en UTF-8 con BOM: Excel en español lo abre con acentos y cargar.py lo lee igual."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class DNS(asyncio.DatagramProtocol):
    """¿Existe este dominio? Pregunta directo a 1.1.1.1 y 8.8.8.8.

    El resolvedor de Windows se atora con miles de consultas (12 s cada una) y responde "no existe"
    a dominios que sí existen; preguntando directo tarda ~0.1 s.

        async with DNS() as dns:
            await dns.existe("irapuato.gob.mx")   # True
    """

    def __init__(self, servidores=("1.1.1.1", "8.8.8.8"), simultaneas=200, espera=2.5, intentos=3):
        self.servidores, self.espera, self.intentos = servidores, espera, intentos
        self.limite = asyncio.Semaphore(simultaneas)
        self.pendientes: dict[int, asyncio.Future] = {}
        self.ids = itertools.cycle(range(1, 65536))

    async def __aenter__(self):
        self.transporte, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: self, local_addr=("0.0.0.0", 0))
        return self

    async def __aexit__(self, *_):
        self.transporte.close()

    def datagram_received(self, datos, origen):
        futuro = self.pendientes.pop(struct.unpack(">H", datos[:2])[0], None)
        if futuro and not futuro.done():
            futuro.set_result(datos)

    def error_received(self, exc):
        pass

    async def existe(self, nombre: str) -> bool:
        try:
            etiquetas = b"".join(bytes([len(p)]) + p.encode("ascii") for p in nombre.strip(".").split("."))
        except (UnicodeEncodeError, ValueError):
            return False
        async with self.limite:
            for intento in range(self.intentos):
                ident = next(self.ids)
                while ident in self.pendientes:
                    ident = next(self.ids)
                paquete = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0) + etiquetas + b"\0" + struct.pack(">HH", 1, 1)
                futuro = asyncio.get_running_loop().create_future()
                self.pendientes[ident] = futuro
                self.transporte.sendto(paquete, (self.servidores[intento % len(self.servidores)], 53))
                try:
                    datos = await asyncio.wait_for(futuro, self.espera)
                except asyncio.TimeoutError:
                    self.pendientes.pop(ident, None)
                    continue
                codigo, respuestas = datos[3] & 0x0F, struct.unpack(">H", datos[6:8])[0]
                if codigo == 0:
                    return respuestas > 0
                if codigo == 3:  # NXDOMAIN: no existe
                    return False
            return False

    async def alguno_existe(self, dominio: str) -> bool:
        """El dominio o su versión con www (hay sitios que solo responden en www)."""
        return await self.existe(dominio) or await self.existe(f"www.{dominio}")
