"""
api/routers/features.py
=========================
Endpoint de feições GeoJSON individuais.

REGRA DE NEGÓCIO CRÍTICA:
- GeoJSON APENAS para feições individuais ou resultados pequenos (< max_features_geojson)
- Visualização massiva → use /tiles/{layer}/{z}/{x}/{y}
- O sistema NUNCA retorna dumps massivos de geometrias em GeoJSON

Cada resposta inclui metadados de linhagem da feição.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import orjson
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import ORJSONResponse
from loguru import logger

from config import settings
from database import get_connection

router = APIRouter(prefix="/features", tags=["features"])


@router.get(
    "/setor/{cd_setor}",
    summary="Detalhe de um Setor Censitário",
    response_class=ORJSONResponse,
)
async def get_setor(
    cd_setor: Annotated[str, Path(min_length=15, max_length=15, description="Geocódigo do setor (15 dígitos)")],
) -> dict:
    """
    Retorna atributos completos de um setor censitário + metadados de linhagem.
    Inclui geometria GeoJSON e dados de acessibilidade educacional pré-calculados.
    """
    sql = """
        SELECT
            s.cd_setor,
            s.cd_municipio,
            s.nm_municipio,
            s.sg_uf,
            s.cd_distrito,
            s.nm_distrito,
            s.nm_bairro,
            s.tipo_setor,
            s.nm_tipo_setor,
            s.pop_total,
            s.domicilios_total,
            s.renda_media_domicilio,
            s.area_km2,
            -- Acessibilidade
            a.distancia_eucl_km,
            a.dist_fund_eucl_km,
            a.qt_escolas_5km,
            a.qt_escolas_10km,
            a.qt_escolas_publicas_5km,
            a.metodo_calculo,
            a.nota_metodologica,
            -- Geometria GeoJSON
            ST_AsGeoJSON(s.geom, 6)::json AS geometry,
            -- Linhagem
            s.fonte_id,
            s.data_extracao,
            s.url_origem,
            s.versao_processamento,
            s.criado_em,
            s.atualizado_em
        FROM atlas.setores_censitarios s
        LEFT JOIN atlas.acessibilidade_educacional a ON a.cd_setor = s.cd_setor
        WHERE s.cd_setor = $1
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, cd_setor)

    if not row:
        raise HTTPException(status_code=404, detail=f"Setor '{cd_setor}' não encontrado")

    data = dict(row)
    geom = data.pop("geometry", None)

    return {
        "type": "Feature",
        "id": cd_setor,
        "geometry": geom,
        "properties": data,
        "_lineage": {
            "fonte_id": data.get("fonte_id"),
            "data_extracao": str(data.get("data_extracao", "")),
            "url_origem": data.get("url_origem"),
            "versao_processamento": data.get("versao_processamento"),
            "criado_em": str(data.get("criado_em", "")),
        },
    }


@router.get(
    "/escola/{co_entidade}",
    summary="Detalhe de uma Escola",
    response_class=ORJSONResponse,
)
async def get_escola(
    co_entidade: Annotated[int, Path(description="Código INEP da entidade")],
) -> dict:
    """Retorna atributos completos de uma escola com metadados de linhagem."""
    sql = """
        SELECT
            e.co_entidade,
            e.no_entidade,
            e.tp_dependencia,
            e.nm_dependencia,
            e.tp_situacao_funcionamento,
            e.co_municipio,
            e.no_municipio,
            e.no_bairro,
            e.in_inf_creche,
            e.in_inf_pre_escola,
            e.in_fund_anos_iniciais,
            e.in_fund_anos_finais,
            e.in_medio_regular,
            e.in_eja,
            e.in_laboratorio_informatica,
            e.in_laboratorio_ciencias,
            e.in_biblioteca,
            e.in_quadra_esportes,
            e.in_acessibilidade,
            e.qt_salas_utilizadas,
            e.qt_mat_bas,
            e.cd_setor_ref,
            e.ano_censo,
            ST_AsGeoJSON(e.geom, 6)::json AS geometry,
            -- Linhagem
            e.fonte_id,
            e.data_extracao,
            e.url_origem,
            e.versao_processamento,
            e.criado_em
        FROM atlas.escolas e
        WHERE e.co_entidade = $1
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, co_entidade)

    if not row:
        raise HTTPException(status_code=404, detail=f"Escola '{co_entidade}' não encontrada")

    data = dict(row)
    geom = data.pop("geometry", None)

    return {
        "type": "Feature",
        "id": co_entidade,
        "geometry": geom,
        "properties": data,
        "_lineage": {
            "fonte_id": data.get("fonte_id"),
            "ano_censo": data.get("ano_censo"),
            "url_origem": data.get("url_origem"),
            "versao_processamento": data.get("versao_processamento"),
        },
    }


@router.get(
    "/municipio/{cd_municipio}",
    summary="Detalhe de um Município",
    response_class=ORJSONResponse,
)
async def get_municipio(
    cd_municipio: Annotated[str, Path(min_length=6, max_length=7)],
    include_geometry: bool = Query(True, description="Incluir geometria GeoJSON"),
) -> dict:
    """Retorna resumo de um município com estatísticas agregadas."""
    geom_sql = "ST_AsGeoJSON(ST_Simplify(m.geom, 0.001), 6)::json" if include_geometry else "null"

    sql = f"""
        SELECT
            m.cd_municipio,
            m.nm_municipio,
            m.area_km2,
            m.populacao_2022,
            (SELECT COUNT(*) FROM atlas.setores_censitarios s WHERE s.cd_municipio = m.cd_municipio)::int AS qt_setores,
            (SELECT COUNT(*) FROM atlas.escolas e WHERE e.co_municipio = m.cd_municipio)::int AS qt_escolas_total,
            (SELECT COUNT(*) FROM atlas.escolas e WHERE e.co_municipio = m.cd_municipio AND e.tp_dependencia IN (1,2,3))::int AS qt_escolas_publicas,
            (SELECT COUNT(*) FROM atlas.estabelecimentos_saude es WHERE es.co_municipio = m.cd_municipio)::int AS qt_estabelecimentos_saude,
            (SELECT COALESCE(SUM(qtd_ocorrencias), 0) FROM atlas.ocorrencias_seguranca os WHERE os.co_municipio = m.cd_municipio)::int AS qt_ocorrencias_seguranca,
            {geom_sql} AS geometry,
            m.fonte_id,
            m.data_extracao,
            m.criado_em
        FROM atlas.municipios_mt m
        WHERE m.cd_municipio = $1
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, cd_municipio)

    if not row:
        raise HTTPException(status_code=404, detail=f"Município '{cd_municipio}' não encontrado")

    data = dict(row)
    geom = data.pop("geometry", None)

    return {
        "type": "Feature",
        "id": cd_municipio,
        "geometry": geom,
        "properties": data,
    }


@router.get(
    "/saude/{co_cnes}",
    summary="Detalhe de um Estabelecimento de Saúde",
    response_class=ORJSONResponse,
)
async def get_saude(
    co_cnes: Annotated[str, Path(description="Código CNES do estabelecimento")],
) -> dict:
    """Retorna atributos completos de uma unidade de saúde."""
    sql = """
        SELECT
            es.co_cnes,
            es.no_fantasia,
            es.no_razao_social,
            es.tp_unidade,
            es.nm_tp_unidade,
            es.tp_gestao,
            es.co_municipio,
            es.no_municipio,
            es.qt_leitos_total,
            es.qt_leitos_sus,
            es.qt_leitos_nao_sus,
            es.cd_setor_ref,
            ST_AsGeoJSON(es.geom, 6)::json AS geometry,
            es.fonte_id,
            es.data_extracao,
            es.versao_processamento,
            es.criado_em
        FROM atlas.estabelecimentos_saude es
        WHERE es.co_cnes = $1
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(sql, co_cnes)

    if not row:
        raise HTTPException(status_code=404, detail=f"Estabelecimento CNES '{co_cnes}' não encontrado")

    data = dict(row)
    geom = data.pop("geometry", None)

    return {
        "type": "Feature",
        "id": co_cnes,
        "geometry": geom,
        "properties": data,
        "_lineage": {
            "fonte_id": data.get("fonte_id"),
            "data_extracao": str(data.get("data_extracao", "")),
            "versao_processamento": data.get("versao_processamento"),
        },
    }


@router.get(
    "/municipio/{cd_municipio}/seguranca",
    summary="Estatísticas de Segurança do Município",
    response_class=ORJSONResponse,
)
async def get_municipio_seguranca(
    cd_municipio: Annotated[str, Path(min_length=6, max_length=7)],
) -> dict:
    """Retorna consolidação de ocorrências criminais (SINESP) para o município."""
    sql = """
        SELECT
            tipo_crime,
            SUM(qtd_ocorrencias)::int AS total_ocorrencias,
            SUM(qtd_vitimas)::int AS total_vitimas,
            SUM(COALESCE(qtd_vitimas_femininas, 0))::int AS total_vitimas_femininas,
            SUM(COALESCE(qtd_vitimas_masculinas, 0))::int AS total_vitimas_masculinas
        FROM atlas.ocorrencias_seguranca
        WHERE co_municipio = $1
        GROUP BY tipo_crime
        ORDER BY total_ocorrencias DESC
    """
    async with get_connection() as conn:
        rows = await conn.fetch(sql, cd_municipio)

    total_ocorrencias = sum(r["total_ocorrencias"] for r in rows) if rows else 0
    total_vitimas = sum(r["total_vitimas"] for r in rows) if rows else 0

    return {
        "cd_municipio": cd_municipio,
        "fonte": "SINESP / MJSP",
        "total_ocorrencias": total_ocorrencias,
        "total_vitimas": total_vitimas,
        "crimes": [dict(r) for r in rows],
    }


@router.get(
    "/seguranca/filtros",
    summary="Filtros Disponíveis para Segurança Pública",
    response_class=ORJSONResponse,
)
async def get_seguranca_filtros() -> dict:
    """Retorna os anos e tipos de crime disponíveis na base SINESP."""
    async with get_connection() as conn:
        anos_rows = await conn.fetch("SELECT DISTINCT ano FROM atlas.ocorrencias_seguranca ORDER BY ano DESC")
        crimes_rows = await conn.fetch("""
            SELECT tipo_crime, SUM(qtd_ocorrencias)::int as total
            FROM atlas.ocorrencias_seguranca
            GROUP BY tipo_crime
            ORDER BY total DESC
        """)

    return {
        "anos": [r["ano"] for r in anos_rows],
        "tipos_crime": [r["tipo_crime"] for r in crimes_rows],
        "crimes_totais": [dict(r) for r in crimes_rows],
    }


@router.get(
    "/seguranca/heatmap",
    summary="GeoJSON de Pontos para Mapa de Calor de Segurança",
    response_class=ORJSONResponse,
)
async def get_seguranca_heatmap(
    ano: int | None = Query(None, description="Ano de referência (ex: 2024, 2023)"),
    tipo_crime: str | None = Query(None, description="Tipo de crime específico ou 'todos'"),
    mes: int | None = Query(None, ge=1, le=12, description="Mês específico"),
    metrica: str = Query("ocorrencias", description="Métrica: ocorrencias ou vitimas"),
) -> dict:
    """
    Retorna FeatureCollection GeoJSON com centroides municipais ponderados
    para renderização direta em camadas Heatmap do MapLibre GL.
    """
    where_clauses = ["1=1"]
    params = []
    p_idx = 1

    if ano is not None:
        where_clauses.append(f"s.ano = ${p_idx}")
        params.append(ano)
        p_idx += 1

    if tipo_crime and tipo_crime.lower() not in ("todos", "all", ""):
        where_clauses.append(f"s.tipo_crime = ${p_idx}")
        params.append(tipo_crime)
        p_idx += 1

    if mes is not None:
        where_clauses.append(f"s.mes = ${p_idx}")
        params.append(mes)
        p_idx += 1

    where_sql = " AND ".join(where_clauses)
    val_expr = "COALESCE(s.qtd_ocorrencias, 0)" if metrica == "ocorrencias" else "COALESCE(s.qtd_vitimas, 0)"

    sql = f"""
        WITH stats AS (
            SELECT
                s.co_municipio,
                SUM(COALESCE(s.qtd_ocorrencias, 0))::int AS qtd_ocorrencias,
                SUM(COALESCE(s.qtd_vitimas, 0))::int AS qtd_vitimas,
                SUM({val_expr})::int AS val
            FROM atlas.ocorrencias_seguranca s
            WHERE {where_sql}
            GROUP BY s.co_municipio
        ),
        max_val AS (
            SELECT NULLIF(MAX(val), 0) AS max_v FROM stats
        )
        SELECT
            m.cd_municipio,
            m.nm_municipio,
            COALESCE(m.populacao_2022, 0)::int AS populacao_2022,
            COALESCE(st.qtd_ocorrencias, 0)::int AS qtd_ocorrencias,
            COALESCE(st.qtd_vitimas, 0)::int AS qtd_vitimas,
            COALESCE(st.val, 0)::int AS val,
            ROUND(COALESCE((st.val::numeric / NULLIF(mv.max_v, 0)), 0), 4)::float AS weight,
            CASE
                WHEN COALESCE(m.populacao_2022, 0) > 0 THEN
                    ROUND((COALESCE(st.val, 0)::numeric / m.populacao_2022 * 100000), 1)::float
                ELSE 0.0
            END AS taxa_100k,
            -- Polígono simplificado do município (tolerância 0.01° ≈ ~1 km)
            -- Necessário para renderização como camada fill (choropleth) no MapLibre.
            -- NÃO usar centroide — fill layer requer geometria poligonal.
            ST_AsGeoJSON(ST_SimplifyPreserveTopology(m.geom, 0.01), 6)::json AS geometry
        FROM atlas.municipios_mt m
        LEFT JOIN stats st ON st.co_municipio = m.cd_municipio
        CROSS JOIN max_val mv
        WHERE m.geom IS NOT NULL
        ORDER BY val DESC
    """

    async with get_connection() as conn:
        rows = await conn.fetch(sql, *params)

    features = [
        {
            "type": "Feature",
            "id": r["cd_municipio"],
            "geometry": json.loads(r["geometry"]) if isinstance(r["geometry"], str) else r["geometry"],
            "properties": {
                "cd_municipio": r["cd_municipio"],
                "nm_municipio": r["nm_municipio"],
                "populacao_2022": r["populacao_2022"],
                "qtd_ocorrencias": r["qtd_ocorrencias"],
                "qtd_vitimas": r["qtd_vitimas"],
                "val": r["val"],
                "weight": r["weight"],
                "taxa_100k": r["taxa_100k"],
            },
        }
        for r in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "_metadata": {
            "ano": ano,
            "tipo_crime": tipo_crime or "todos",
            "mes": mes,
            "metrica": metrica,
            "total_municipios": len(features),
        },
    }


@router.get(
    "/municipio/{cd_municipio}/cobertura_solo",
    summary="Cobertura do Solo MapBiomas do Município",
    response_class=ORJSONResponse,
)
async def get_municipio_cobertura_solo(
    cd_municipio: Annotated[str, Path(min_length=6, max_length=7)],
) -> dict:
    """Retorna consolidação das classes de cobertura do solo (MapBiomas) para o município."""
    sql = """
        SELECT
            ano,
            classe_mapbiomas,
            nm_classe,
            area_ha::float AS area_ha
        FROM atlas.cobertura_solo_mapbiomas
        WHERE co_municipio = $1
        ORDER BY ano DESC, area_ha DESC
    """
    async with get_connection() as conn:
        rows = await conn.fetch(sql, cd_municipio)

    classes_list = [dict(r) for r in rows]
    total_area_ha = sum(r["area_ha"] for r in classes_list) if classes_list else 0.0

    return {
        "cd_municipio": cd_municipio,
        "fonte": "MapBiomas Coleção 11",
        "total_area_ha": round(total_area_ha, 2),
        "classes": classes_list,
    }


@router.get(
    "/municipio/{cd_municipio}/saude",
    summary="Unidades de Saúde do Município",
    response_class=ORJSONResponse,
)
async def get_municipio_saude(
    cd_municipio: Annotated[str, Path(min_length=6, max_length=7)],
) -> dict:
    """Retorna lista dos principais estabelecimentos de saúde do município."""
    sql = """
        SELECT
            co_cnes,
            no_fantasia,
            nm_tp_unidade,
            tp_gestao,
            qt_leitos_total,
            qt_leitos_sus,
            qt_leitos_nao_sus
        FROM atlas.estabelecimentos_saude
        WHERE co_municipio = $1
        ORDER BY qt_leitos_total DESC, no_fantasia ASC
        LIMIT 100
    """
    async with get_connection() as conn:
        rows = await conn.fetch(sql, cd_municipio)

    return {
        "cd_municipio": cd_municipio,
        "fonte": "DATASUS CNES",
        "total_unidades": len(rows),
        "estabelecimentos": [dict(r) for r in rows],
    }


@router.get(
    "/bbox",
    summary="Feições em Bounding Box",
    response_class=ORJSONResponse,
    description=(
        "Retorna feições dentro de uma bbox como GeoJSON FeatureCollection. "
        f"Limitado a {settings.max_features_geojson} feições. "
        "Para volumes maiores, use /tiles/{layer}/{z}/{x}/{y}."
    ),
)
async def get_features_in_bbox(
    layer: str = Query(..., description="Camada: setores, escolas, saude, malha_viaria"),
    xmin: float = Query(...),
    ymin: float = Query(...),
    xmax: float = Query(...),
    ymax: float = Query(...),
    limit: int = Query(100, ge=1, le=settings.max_features_geojson),
) -> dict:
    """Feições GeoJSON dentro de uma bbox — para uso analítico restrito."""
    table_map = {
        "setores": ("atlas.setores_censitarios", "cd_setor", "geom"),
        "escolas": ("atlas.escolas", "co_entidade::text", "geom"),
        "saude": ("atlas.estabelecimentos_saude", "co_cnes", "geom"),
        "malha_viaria": ("atlas.malha_viaria_osm", "osm_id::text", "geom"),
    }

    if layer not in table_map:
        raise HTTPException(status_code=400, detail=f"Camada inválida: {layer}")

    table, id_col, geom_col = table_map[layer]
    sql = f"""
        SELECT
            {id_col} AS id,
            ST_AsGeoJSON({geom_col}, 6)::json AS geometry,
            row_to_json(t) AS properties
        FROM {table} t
        WHERE {geom_col} && ST_MakeEnvelope($1, $2, $3, $4, 4326)
        LIMIT $5
    """

    async with get_connection() as conn:
        rows = await conn.fetch(sql, xmin, ymin, xmax, ymax, limit)

    features = [
        {
            "type": "Feature",
            "id": row["id"],
            "geometry": row["geometry"],
            "properties": dict(row["properties"]) if row["properties"] else {},
        }
        for row in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "_metadata": {
            "count": len(features),
            "limit": limit,
            "truncated": len(features) == limit,
            "note": (
                f"Limitado a {limit} feições. "
                "Para volumes maiores, use a API de tiles MVT."
            ) if len(features) == limit else None,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints de Queimadas (INPE BDQueimadas)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/queimadas/heatmap",
    summary="Choropleth Municipal de Queimadas (GeoJSON)",
    response_class=ORJSONResponse,
)
async def get_queimadas_heatmap(
    ano: Annotated[int | None, Query(description="Ano de referência")] = None,
    mes: Annotated[int | None, Query(ge=1, le=12, description="Mês de referência")] = None,
    bioma: Annotated[str | None, Query(description="Bioma (Amazônia, Cerrado, Pantanal)")] = None,
    apenas_referencia: Annotated[bool, Query(description="Filtrar apenas satélite de referência (AQUA)")] = False,
    metrica: Annotated[str, Query(description="Métrica: focos, frp_medio, risco_medio")] = "focos",
) -> dict:
    """
    Retorna GeoJSON dos municípios de MT com agregação de focos de queimadas.
    Permite alternar entre total de focos, FRP médio e risco de fogo médio.
    """
    where_clauses = ["1=1"]
    params: list[Any] = []
    p_idx = 1

    if ano is not None:
        where_clauses.append(f"q.ano = ${p_idx}")
        params.append(ano)
        p_idx += 1

    if mes is not None:
        where_clauses.append(f"q.mes = ${p_idx}")
        params.append(mes)
        p_idx += 1

    if bioma and bioma.lower() not in ("todos", "all", ""):
        where_clauses.append(f"q.bioma ILIKE ${p_idx}")
        params.append(f"%{bioma}%")
        p_idx += 1

    if apenas_referencia:
        where_clauses.append("q.is_referencia = TRUE")

    where_sql = " AND ".join(where_clauses)

    if metrica == "frp_medio":
        val_calc = "ROUND(COALESCE(AVG(q.frp), 0)::numeric, 1)::float"
    elif metrica == "risco_medio":
        val_calc = "ROUND(COALESCE(AVG(q.risco_fogo), 0)::numeric, 2)::float"
    else:
        val_calc = "COUNT(*)::int"

    sql = f"""
        WITH stats AS (
            SELECT
                q.co_municipio,
                COUNT(*)::int AS total_focos,
                COUNT(*) FILTER (WHERE q.is_referencia = TRUE)::int AS focos_referencia,
                ROUND(COALESCE(AVG(q.frp), 0)::numeric, 1)::float AS frp_medio,
                ROUND(COALESCE(MAX(q.frp), 0)::numeric, 1)::float AS frp_maximo,
                ROUND(COALESCE(AVG(q.risco_fogo), 0)::numeric, 2)::float AS risco_medio,
                COUNT(*) FILTER (WHERE q.bioma = 'Amazônia')::int AS focos_amazonia,
                COUNT(*) FILTER (WHERE q.bioma = 'Cerrado')::int AS focos_cerrado,
                COUNT(*) FILTER (WHERE q.bioma = 'Pantanal')::int AS focos_pantanal,
                {val_calc} AS val
            FROM atlas.focos_queimadas q
            WHERE {where_sql}
            GROUP BY q.co_municipio
        ),
        max_val AS (
            SELECT NULLIF(MAX(val), 0) AS max_v FROM stats
        )
        SELECT
            m.cd_municipio,
            m.nm_municipio,
            COALESCE(m.populacao_2022, 0)::int AS populacao_2022,
            COALESCE(m.area_km2, 0)::float AS area_km2,
            COALESCE(st.total_focos, 0)::int AS total_focos,
            COALESCE(st.focos_referencia, 0)::int AS focos_referencia,
            COALESCE(st.frp_medio, 0.0)::float AS frp_medio,
            COALESCE(st.frp_maximo, 0.0)::float AS frp_maximo,
            COALESCE(st.risco_medio, 0.0)::float AS risco_medio,
            COALESCE(st.focos_amazonia, 0)::int AS focos_amazonia,
            COALESCE(st.focos_cerrado, 0)::int AS focos_cerrado,
            COALESCE(st.focos_pantanal, 0)::int AS focos_pantanal,
            COALESCE(st.val, 0)::float AS val,
            ROUND(COALESCE((st.val::numeric / NULLIF(mv.max_v, 0)), 0), 4)::float AS weight,
            ST_AsGeoJSON(ST_SimplifyPreserveTopology(m.geom, 0.01), 6)::json AS geometry
        FROM atlas.municipios_mt m
        LEFT JOIN stats st ON st.co_municipio = m.cd_municipio
        CROSS JOIN max_val mv
        WHERE m.geom IS NOT NULL
        ORDER BY val DESC
    """

    async with get_connection() as conn:
        rows = await conn.fetch(sql, *params)

    features = [
        {
            "type": "Feature",
            "id": r["cd_municipio"],
            "geometry": json.loads(r["geometry"]) if isinstance(r["geometry"], str) else r["geometry"],
            "properties": {
                "cd_municipio": r["cd_municipio"],
                "nm_municipio": r["nm_municipio"],
                "populacao_2022": r["populacao_2022"],
                "area_km2": r["area_km2"],
                "total_focos": r["total_focos"],
                "focos_referencia": r["focos_referencia"],
                "frp_medio": r["frp_medio"],
                "frp_maximo": r["frp_maximo"],
                "risco_medio": r["risco_medio"],
                "focos_amazonia": r["focos_amazonia"],
                "focos_cerrado": r["focos_cerrado"],
                "focos_pantanal": r["focos_pantanal"],
                "val": r["val"],
                "weight": r["weight"],
            },
        }
        for r in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "_metadata": {
            "ano": ano,
            "mes": mes,
            "bioma": bioma or "todos",
            "apenas_referencia": apenas_referencia,
            "metrica": metrica,
            "total_municipios": len(features),
        },
    }


@router.get(
    "/queimadas/filtros",
    summary="Opções de filtros para Queimadas",
    response_class=ORJSONResponse,
)
async def get_queimadas_filtros() -> dict:
    """Retorna anos, meses, biomas e satélites disponíveis no banco."""
    async with get_connection() as conn:
        anos_rows = await conn.fetch("SELECT DISTINCT ano FROM atlas.focos_queimadas ORDER BY ano DESC")
        biomas_rows = await conn.fetch("SELECT DISTINCT bioma FROM atlas.focos_queimadas WHERE bioma IS NOT NULL AND bioma != '' ORDER BY bioma")
        sat_rows = await conn.fetch("SELECT satelite, COUNT(*) as qtd FROM atlas.focos_queimadas GROUP BY satelite ORDER BY qtd DESC")
        total_focos = await conn.fetchval("SELECT COUNT(*) FROM atlas.focos_queimadas")

    anos = [r["ano"] for r in anos_rows] if anos_rows else [2025, 2024]
    biomas = [r["bioma"] for r in biomas_rows] if biomas_rows else ["Amazônia", "Cerrado", "Pantanal"]
    satelites = [{"satelite": r["satelite"], "qtd": r["qtd"]} for r in sat_rows] if sat_rows else []

    return {
        "anos": anos,
        "biomas": biomas,
        "satelites": satelites,
        "total_focos": total_focos or 0,
    }


@router.get(
    "/queimadas/stats",
    summary="Estatísticas Consolidadas de Queimadas",
    response_class=ORJSONResponse,
)
async def get_queimadas_stats(
    ano: Annotated[int | None, Query(description="Ano")] = None,
    mes: Annotated[int | None, Query(ge=1, le=12, description="Mês")] = None,
) -> dict:
    """Retorna métricas agregadas por bioma, top municípios e série mensal."""
    where_sql = "1=1"
    params: list[Any] = []
    p_idx = 1
    if ano is not None:
        where_sql += f" AND ano = ${p_idx}"
        params.append(ano)
        p_idx += 1
    if mes is not None:
        where_sql += f" AND mes = ${p_idx}"
        params.append(mes)
        p_idx += 1

    sql_biomas = f"""
        SELECT bioma, COUNT(*) as qtd, ROUND(AVG(frp)::numeric, 1)::float as frp_medio
        FROM atlas.focos_queimadas
        WHERE {where_sql}
        GROUP BY bioma ORDER BY qtd DESC
    """

    sql_top_mun = f"""
        SELECT co_municipio, municipio, COUNT(*) as qtd, ROUND(AVG(frp)::numeric, 1)::float as frp_medio
        FROM atlas.focos_queimadas
        WHERE {where_sql}
        GROUP BY co_municipio, municipio ORDER BY qtd DESC LIMIT 5
    """

    async with get_connection() as conn:
        biomas_res = await conn.fetch(sql_biomas, *params)
        top_mun_res = await conn.fetch(sql_top_mun, *params)
        geral = await conn.fetchrow(f"""
            SELECT
                COUNT(*)::int as total,
                COUNT(*) FILTER (WHERE is_referencia = TRUE)::int as total_referencia,
                ROUND(AVG(frp)::numeric, 1)::float as frp_medio,
                ROUND(MAX(frp)::numeric, 1)::float as frp_maximo,
                ROUND(AVG(risco_fogo)::numeric, 2)::float as risco_medio
            FROM atlas.focos_queimadas
            WHERE {where_sql}
        """, *params)

    return {
        "geral": dict(geral) if geral else {},
        "por_bioma": [dict(r) for r in biomas_res],
        "top_municipios": [dict(r) for r in top_mun_res],
    }


@router.get(
    "/municipio/{cd_municipio}/queimadas",
    summary="Resumo de Queimadas do Município",
    response_class=ORJSONResponse,
)
async def get_municipio_queimadas(
    cd_municipio: Annotated[str, Path(min_length=6, max_length=7)],
) -> dict:
    """Retorna consolidação histórica mensal de queimadas do município."""
    sql = """
        SELECT
            ano,
            mes,
            total_focos,
            focos_referencia,
            focos_amazonia,
            focos_cerrado,
            focos_pantanal,
            frp_medio,
            frp_maximo,
            risco_fogo_medio,
            dias_sem_chuva_medio
        FROM atlas.queimadas_municipais_resumo
        WHERE co_municipio = $1 OR co_municipio LIKE $1 || '%'
        ORDER BY ano DESC, mes DESC
    """
    async with get_connection() as conn:
        rows = await conn.fetch(sql, cd_municipio)

    if rows:
        tot_focos = sum(r["total_focos"] for r in rows)
        tot_ref = sum(r["focos_referencia"] for r in rows)
        frp_vals = [r["frp_medio"] for r in rows if r["frp_medio"] is not None]
        risco_vals = [r["risco_fogo_medio"] for r in rows if r["risco_fogo_medio"] is not None]
        chuva_vals = [r["dias_sem_chuva_medio"] for r in rows if r["dias_sem_chuva_medio"] is not None]

        return {
            "cd_municipio": cd_municipio,
            "total_focos": tot_focos,
            "focos_referencia": tot_ref,
            "frp_medio": round(sum(frp_vals) / len(frp_vals), 1) if frp_vals else None,
            "risco_fogo_medio": round(sum(risco_vals) / len(risco_vals), 2) if risco_vals else None,
            "dias_sem_chuva_medio": round(sum(chuva_vals) / len(chuva_vals), 1) if chuva_vals else None,
            "registros": [dict(r) for r in rows],
        }

    # Fallback para focos_queimadas caso o resumo ainda esteja sendo calculado
    fallback_sql = """
        SELECT
            COUNT(*)::int AS total_focos,
            COUNT(*) FILTER (WHERE is_referencia = TRUE)::int AS focos_referencia,
            ROUND(COALESCE(AVG(frp), 0)::numeric, 1)::float AS frp_medio,
            ROUND(COALESCE(AVG(risco_fogo), 0)::numeric, 2)::float AS risco_fogo_medio,
            ROUND(COALESCE(AVG(numero_dias_sem_chuva), 0)::numeric, 1)::float AS dias_sem_chuva_medio
        FROM atlas.focos_queimadas
        WHERE co_municipio = $1 OR co_municipio LIKE $1 || '%'
    """
    async with get_connection() as conn:
        fb = await conn.fetchrow(fallback_sql, cd_municipio)

    return {
        "cd_municipio": cd_municipio,
        "total_focos": fb["total_focos"] if fb else 0,
        "focos_referencia": fb["focos_referencia"] if fb else 0,
        "frp_medio": fb["frp_medio"] if fb else None,
        "risco_fogo_medio": fb["risco_fogo_medio"] if fb else None,
        "dias_sem_chuva_medio": fb["dias_sem_chuva_medio"] if fb else None,
        "registros": [],
    }

