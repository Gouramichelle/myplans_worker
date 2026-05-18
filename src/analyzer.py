"""
Análisis de planos amarillados con Claude Vision.

Flujo:
  1. Convierte páginas del PDF a imágenes JPEG con pymupdf (sin deps del sistema).
  2. Envía las imágenes + lista de TAGs a Claude en un solo request.
  3. Parsea el JSON estructurado que devuelve el modelo.
  4. Retorna sugerencias de cambio de estado por TAG.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Any

import anthropic
import fitz  # pymupdf
from PIL import Image

from src.config import settings
from src.schemas import TagEstado, TagInfo, TagSugerencia

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Eres un asistente experto en ingeniería eléctrica y precomisionamiento industrial.
Tu tarea es analizar páginas de planos eléctricos que han sido marcados ("amarillados") \
por técnicos en terreno durante inspecciones físicas de equipos (TAGs).

CONVENCIÓN DE MARCADO EN TERRENO:
- Resaltado AMARILLO / marca verde / círculo / check (✓) junto a un TAG → equipo verificado = APROBADO
- Marca ROJA / tachado / X / redline / comentario negativo junto a un TAG → equipo con problema = OBSERVADO
- Sin ninguna marca visible → equipo no inspeccionado todavía = PENDIENTE

REGLAS IMPORTANTES:
- Solo reporta TAGs que puedas identificar CLARAMENTE en las imágenes.
- Asigna confidence de 0.0 a 1.0 según qué tan clara es la marca.
- Si hay texto escrito a mano cerca de un TAG con estado OBSERVADO, captúralo como comentario.
- No reportes TAGs con confidence menor a 0.4.
- No inventes códigos de TAGs que no estén en la lista provista.
- Si un TAG no aparece en la imagen, simplemente no lo incluyas en la respuesta.

Responde ÚNICAMENTE con un array JSON válido, sin texto adicional, sin cercas de código.
Cada elemento del array debe tener exactamente este formato:
{"codigo": "TAG-001", "estado": "APROBADO", "comentario": null, "confidence": 0.95, "pagina": 1}
"""

_USER_TEMPLATE = """\
Se adjuntan {n_pages} página(s) del plano para análisis.

Lista de TAGs registrados en este plano ({n_tags} en total):
{tag_list}

Analiza cada imagen e identifica qué TAGs están marcados y con qué estado.
Responde solo con el array JSON.
"""


def _pdf_to_images(pdf_bytes: bytes, dpi: int, max_pages: int) -> tuple[list[tuple[int, str]], int]:
    """Convierte páginas del PDF a JPEG base64. Retorna ([(pag, b64)], total_páginas)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = doc.page_count
    n = min(total, max_pages)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    results: list[tuple[int, str]] = []

    for i in range(n):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        results.append((i + 1, b64))

    doc.close()
    return results, total


def _build_tag_list(tags: list[TagInfo]) -> str:
    lines = []
    for t in tags:
        parts = [f"• {t.codigo}"]
        if t.descripcion:
            parts.append(f"— {t.descripcion}")
        if t.area:
            parts.append(f"[{t.area}]")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def _extract_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Sin array JSON en la respuesta del modelo: {raw[:300]}")
    return json.loads(match.group())


def _parse_estado(raw: str) -> TagEstado:
    v = raw.upper().strip()
    if v in ("APROBADO", "APPROVED", "OK", "VERIFICADO"):
        return TagEstado.APROBADO
    if v in ("OBSERVADO", "OBSERVED", "REDLINE", "RECHAZADO", "FLAGGED"):
        return TagEstado.OBSERVADO
    return TagEstado.PENDIENTE


async def analyze_plano(
    pdf_bytes: bytes,
    tags: list[TagInfo],
) -> tuple[list[TagSugerencia], int, list[str]]:
    """
    Analiza el PDF amarillado y retorna sugerencias de cambio de estado.

    Returns:
        (sugerencias, paginas_analizadas, advertencias)
    """
    advertencias: list[str] = []

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY no está configurada. "
            "Copia myplans_worker/.env.example a .env y agrega tu API key."
        )

    page_images, total_pages = _pdf_to_images(pdf_bytes, settings.PDF_DPI, settings.MAX_PAGES)
    paginas_analizadas = len(page_images)

    if total_pages > settings.MAX_PAGES:
        advertencias.append(
            f"El plano tiene {total_pages} páginas. Solo se analizaron las primeras "
            f"{settings.MAX_PAGES} (límite del modelo). Las páginas restantes quedan PENDIENTE."
        )

    if not page_images:
        return [], 0, ["El PDF no contiene páginas procesables."]

    if not tags:
        return [], paginas_analizadas, ["No hay TAGs registrados en este plano."]

    # Índice rápido código→TagInfo (case-insensitive)
    tag_index: dict[str, TagInfo] = {t.codigo.upper(): t for t in tags}

    # Construir el mensaje con todas las imágenes primero, texto al final
    content: list[dict[str, Any]] = []
    for _pagina, b64 in page_images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    content.append({
        "type": "text",
        "text": _USER_TEMPLATE.format(
            n_pages=paginas_analizadas,
            n_tags=len(tags),
            tag_list=_build_tag_list(tags),
        ),
    })

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    logger.info(
        "analyzer: %d páginas, %d TAGs → modelo %s",
        paginas_analizadas, len(tags), settings.CLAUDE_MODEL,
    )

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw_text = response.content[0].text if response.content else "[]"
    logger.debug("analyzer: respuesta raw (primeros 500): %s", raw_text[:500])

    try:
        parsed = _extract_json_array(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("analyzer: fallo parseando JSON — %s | raw: %s", exc, raw_text[:500])
        advertencias.append(
            "El modelo devolvió una respuesta no procesable. Intenta de nuevo."
        )
        return [], paginas_analizadas, advertencias

    sugerencias: list[TagSugerencia] = []
    vistos: set[str] = set()

    for item in parsed:
        codigo = str(item.get("codigo", "")).strip()
        if not codigo:
            continue
        key = codigo.upper()
        if key in vistos:
            continue
        vistos.add(key)

        tag_info = tag_index.get(key)
        if tag_info is None:
            logger.debug("analyzer: TAG '%s' no está en la lista del plano, ignorado", codigo)
            continue

        estado_sugerido = _parse_estado(item.get("estado", "PENDIENTE"))
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))

        # Solo incluir si hay cambio real de estado
        if estado_sugerido == tag_info.estadoActual:
            continue

        comentario = item.get("comentario") or None
        pagina = item.get("pagina")

        sugerencias.append(TagSugerencia(
            idTag=tag_info.idTag,
            codigo=codigo,
            estadoActual=tag_info.estadoActual,
            estadoSugerido=estado_sugerido,
            comentario=comentario,
            confidence=round(confidence, 2),
            pagina=pagina,
        ))

    logger.info("analyzer: %d sugerencias de cambio detectadas", len(sugerencias))
    return sugerencias, paginas_analizadas, advertencias
