"""Endpoints del worker de análisis de planos amarillados."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from src import analyzer, myplans_client
from src.schemas import AplicarCambiosRequest, AplicarCambiosResponse, AnalisisResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/worker", tags=["MyPlans Worker"])

MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


def _require_token(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token requerido")
    return authorization[7:].strip()



@router.post(
    "/planos/{id_plano}/analizar",
    response_model=AnalisisResponse,
    summary="Analiza un plano amarillado con IA",
    description=(
        "Recibe el PDF anotado del plano y devuelve sugerencias de cambio de estado por TAG. "
        "No aplica ningún cambio — solo sugiere. Usa /aplicar para confirmar."
    ),
)
async def analizar_plano(
    id_plano: int,
    file: UploadFile = File(..., description="PDF del plano con anotaciones/amarillado"),
    jwt_token: str = Depends(_require_token),
) -> AnalisisResponse:
    filename = file.filename or ""
    content_type = file.content_type or ""
    if "pdf" not in content_type.lower() and not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF.",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera el límite de {MAX_PDF_BYTES // 1024 // 1024} MB.",
        )
    if len(pdf_bytes) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo PDF está vacío o corrupto.",
        )

    try:
        tags = await myplans_client.get_tags_by_plano(id_plano, jwt_token)
    except Exception as exc:
        logger.error("analizar_plano: error obteniendo TAGs del plano %d — %s", id_plano, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudieron obtener los TAGs de MyPlans: {exc}",
        ) from exc

    if not tags:
        return AnalisisResponse(
            idPlano=id_plano,
            totalTags=0,
            tagsAnalizados=0,
            sugerencias=[],
            paginasAnalizadas=0,
            advertencias=["Este plano no tiene TAGs. Carga la matriz Excel primero."],
        )

    try:
        sugerencias, paginas_analizadas, advertencias = await analyzer.analyze_plano(
            pdf_bytes=pdf_bytes,
            tags=tags,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("analizar_plano: error en análisis IA — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el análisis con IA: {exc}",
        ) from exc

    return AnalisisResponse(
        idPlano=id_plano,
        totalTags=len(tags),
        tagsAnalizados=len(sugerencias),
        sugerencias=sugerencias,
        paginasAnalizadas=paginas_analizadas,
        advertencias=advertencias,
    )


@router.post(
    "/planos/{id_plano}/aplicar",
    response_model=AplicarCambiosResponse,
    summary="Aplica las sugerencias confirmadas al plano",
    description=(
        "Recibe las sugerencias que el usuario confirmó y actualiza el estado "
        "de cada TAG en MyPlans vía PATCH /api/v1/tags/{id}/estado."
    ),
)
async def aplicar_cambios(
    id_plano: int,
    request: AplicarCambiosRequest,
    jwt_token: str = Depends(_require_token),
) -> AplicarCambiosResponse:
    aplicados = 0
    errores = 0
    detalle: list[dict] = []

    for sug in request.sugerencias:
        try:
            await myplans_client.update_tag_estado(
                id_tag=sug.idTag,
                estado=sug.estadoSugerido,
                comentario=sug.comentario,
                jwt_token=jwt_token,
                por_ia=True,
            )
            aplicados += 1
            detalle.append({"idTag": sug.idTag, "codigo": sug.codigo, "ok": True})
        except Exception as exc:
            errores += 1
            detalle.append({"idTag": sug.idTag, "codigo": sug.codigo, "ok": False, "error": str(exc)})
            logger.warning("aplicar_cambios: fallo actualizando TAG %d — %s", sug.idTag, exc)

    return AplicarCambiosResponse(aplicados=aplicados, errores=errores, detalle=detalle)


@router.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}
