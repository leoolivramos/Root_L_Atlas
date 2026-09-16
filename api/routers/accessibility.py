"""
api/routers/accessibility.py
==============================
Endpoints de análise de acessibilidade a infraestruturas públicas.

NOTA METODOLÓGICA:
Fase 1 (MVP): distância euclidiana (linha reta) — estimativa conservadora.
Fase 2: tempo de viagem via rede viária (OSRM/Valhalla).

A plataforma tem o dever contínuo de assinalar visualmente que os
tempos/distâncias apresentados correspondem a estimativas, assumindo
responsabilidade científica.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import ORJSONResponse

from database import get_connection

router = APIRouter(prefix="/accessibility", tags=["acessibilidade"])

# Nota padrão de responsabilidade científica
_NOTA_METODOLOGICA = (
    "ESTIMATIVA: Distância euclidiana (linha reta). "
    "Não considera a rede viária, barreiras naturais ou sentido de tráfego. "
    "Fase 2 do roadmap substituirá por tempo de viagem via OSRM (rede viária OSM)."
)


@router.get(
    "/education/sector/{cd_setor}",
    summary="Acessibilidade Educacional de um Setor",
    response_class=ORJSONResponse,
)
async def get_education_accessibility_by_sector(
    cd_setor: str,
    max_km: float = Query(10.0, description="Raio máximo em km (linha reta)"),
) -> dict:
    """
    Retorna métricas de acessibilidade educacional para um setor censitário.

    Inclui:
    - Escola mais próxima (total e por rede pública/fundamental)
    - Contagem de escolas dentro do raio solicitado
    - Nota metodológica obrigatória
    """
    sql = """
        SELECT
            a.cd_setor,
            a.co_entidade_mais_proxima,
            a.distancia_eucl_km,
            a.co_entidade_fund_prox,
            a.dist_fund_eucl_km,
            a.qt_escolas_5km,
            a.qt_escolas_10km,
            a.qt_escolas_publicas_5km,
            -- Escola mais próxima (detalhes)
            e.no_entidade AS no_escola_prox,
            e.nm_dependencia AS rede_escola_prox,
            ST_AsGeoJSON(e.geom, 6)::json AS geom_escola_prox,
            -- Setor (centróide)
            ST_AsGeoJSON(s.centroide, 6)::json AS geom_centroide_setor,
            s.pop_total,
            -- Escolas dentro do raio solicitado
            (
                SELECT jsonb_agg(jsonb_build_object(
                    'co_entidade', ec.co_entidade,
                    'no_entidade', ec.no_entidade,
                    'nm_dependencia', ec.nm_dependencia,
                    'distancia_km', ROUND(
                        ST_Distance(
                            s.centroide::geography,
                            ec.geom::geography
                        ) / 1000.0, 3
                    )
                ) ORDER BY ST_Distance(s.centroide, ec.geom))
                FROM atlas.escolas ec
                WHERE ST_DWithin(
                    s.centroide::geography,
                    ec.geom::geography,
                    $2 * 1000  -- metros
                )
                  AND ec.tp_situacao_funcionamento = 1
            ) AS escolas_no_raio
        FROM atlas.acessibilidade_educacional a
        LEFT JOIN atlas.escolas e ON e.co_entidade = a.co_entidade_mais_proxima
        LEFT JOIN atlas.setores_censitarios s ON s.cd_setor = a.cd_setor
        WHERE a.cd_setor = $1
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, cd_setor, max_km)

    if not row:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Dados de acessibilidade não encontrados para setor '{cd_setor}'. "
                   "Execute o pipeline de cálculo primeiro.",
        )

    data = dict(row)

    return {
        "cd_setor": cd_setor,
        "metodo": "distancia_euclidiana",
        "nota_metodologica": _NOTA_METODOLOGICA,
        "raio_busca_km": max_km,
        "metricas": {
            "escola_mais_proxima": {
                "co_entidade": data.get("co_entidade_mais_proxima"),
                "no_entidade": data.get("no_escola_prox"),
                "rede": data.get("rede_escola_prox"),
                "distancia_eucl_km": data.get("distancia_eucl_km"),
                "geometry": data.get("geom_escola_prox"),
            },
            "escola_fundamental_publica_mais_proxima": {
                "co_entidade": data.get("co_entidade_fund_prox"),
                "distancia_eucl_km": data.get("dist_fund_eucl_km"),
            },
            "contagem_no_raio": {
                "total_5km": data.get("qt_escolas_5km", 0),
                "total_10km": data.get("qt_escolas_10km", 0),
                "publicas_5km": data.get("qt_escolas_publicas_5km", 0),
                f"total_{max_km}km": len(data.get("escolas_no_raio") or []),
            },
        },
        "setor": {
            "pop_total": data.get("pop_total"),
            "centroide": data.get("geom_centroide_setor"),
        },
        "escolas_no_raio": data.get("escolas_no_raio") or [],
    }


@router.get(
    "/education/municipio/{cd_municipio}/summary",
    summary="Resumo de Acessibilidade Educacional do Município",
    response_class=ORJSONResponse,
)
async def get_education_summary_by_municipio(
    cd_municipio: str,
    limiar_km: float = Query(
        5.0,
        description="Distância limiar (km) para definir 'com acesso'",
    ),
) -> dict:
    """
    Resumo de acessibilidade educacional para todos os setores de um município.

    Permite identificar que parcela da população reside razoavelmente
    próxima de aparelhos de ensino.
    """
    sql = """
        WITH setores_municipio AS (
            SELECT
                s.cd_setor,
                s.pop_total,
                a.distancia_eucl_km,
                a.dist_fund_eucl_km,
                a.qt_escolas_publicas_5km,
                CASE
                    WHEN a.dist_fund_eucl_km <= $2 THEN TRUE
                    ELSE FALSE
                END AS tem_acesso_fund_publico
            FROM atlas.setores_censitarios s
            LEFT JOIN atlas.acessibilidade_educacional a ON a.cd_setor = s.cd_setor
            WHERE s.cd_municipio = $1
        )
        SELECT
            COUNT(*) AS total_setores,
            SUM(pop_total) AS populacao_total,
            SUM(pop_total) FILTER (WHERE tem_acesso_fund_publico) AS pop_com_acesso,
            SUM(pop_total) FILTER (WHERE NOT tem_acesso_fund_publico OR tem_acesso_fund_publico IS NULL) AS pop_sem_acesso,
            AVG(distancia_eucl_km) AS dist_media_escola_km,
            AVG(dist_fund_eucl_km) AS dist_media_escola_fund_pub_km,
            MIN(dist_fund_eucl_km) AS dist_min_escola_fund_pub_km,
            MAX(dist_fund_eucl_km) AS dist_max_escola_fund_pub_km,
            COUNT(*) FILTER (WHERE tem_acesso_fund_publico) AS setores_com_acesso,
            COUNT(*) FILTER (WHERE NOT tem_acesso_fund_publico) AS setores_sem_acesso
        FROM setores_municipio
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, cd_municipio, limiar_km)

    if not row or row["total_setores"] == 0:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Município '{cd_municipio}' não encontrado ou sem dados de acessibilidade.",
        )

    data = dict(row)
    pop_total = data.get("populacao_total") or 1
    pop_com_acesso = data.get("pop_com_acesso") or 0

    return {
        "cd_municipio": cd_municipio,
        "metodo": "distancia_euclidiana",
        "nota_metodologica": _NOTA_METODOLOGICA,
        "limiar_acesso_km": limiar_km,
        "resumo": {
            "total_setores": data.get("total_setores"),
            "populacao_total": data.get("populacao_total"),
            "pop_com_acesso_fund_pub": pop_com_acesso,
            "pop_sem_acesso_fund_pub": data.get("pop_sem_acesso"),
            "pct_pop_com_acesso": round(pop_com_acesso / pop_total * 100, 1),
            "setores_com_acesso": data.get("setores_com_acesso"),
            "setores_sem_acesso": data.get("setores_sem_acesso"),
        },
        "distancias": {
            "media_escola_km": round(data.get("dist_media_escola_km") or 0, 2),
            "media_escola_fund_pub_km": round(data.get("dist_media_escola_fund_pub_km") or 0, 2),
            "min_km": round(data.get("dist_min_escola_fund_pub_km") or 0, 2),
            "max_km": round(data.get("dist_max_escola_fund_pub_km") or 0, 2),
        },
    }
