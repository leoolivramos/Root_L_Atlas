-- ============================================================
-- RootL Atlas — Índices Espaciais e de Performance
-- PostgreSQL 16 + PostGIS 3.4
-- ============================================================
-- Este arquivo é executado APÓS init.sql (ordem: 02_indexes.sql)
-- Deve ser idempotente (IF NOT EXISTS onde disponível)
-- ============================================================

SET search_path TO atlas, public;

-- ────────────────────────────────────────────────────────────
-- ÍNDICES ESPACIAIS GiST — Municipios
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_municipios_geom
    ON atlas.municipios_mt USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_municipios_centroide
    ON atlas.municipios_mt USING GIST (centroide);

CREATE INDEX IF NOT EXISTS idx_municipios_cd
    ON atlas.municipios_mt (cd_municipio);

CREATE INDEX IF NOT EXISTS idx_municipios_nm_trgm
    ON atlas.municipios_mt USING GIN (nm_municipio_ascii gin_trgm_ops);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES ESPACIAIS GiST — Setores Censitários
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_setores_geom
    ON atlas.setores_censitarios USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_setores_centroide
    ON atlas.setores_censitarios USING GIST (centroide);

CREATE INDEX IF NOT EXISTS idx_setores_cd_setor
    ON atlas.setores_censitarios (cd_setor);

CREATE INDEX IF NOT EXISTS idx_setores_cd_municipio
    ON atlas.setores_censitarios (cd_municipio);

-- Índice parcial: apenas setores urbanos (consultas mais frequentes)
CREATE INDEX IF NOT EXISTS idx_setores_urbanos_geom
    ON atlas.setores_censitarios USING GIST (geom)
    WHERE tipo_setor = 1;

-- ────────────────────────────────────────────────────────────
-- ÍNDICES ESPACIAIS GiST — Escolas
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_escolas_geom
    ON atlas.escolas USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_escolas_co_entidade
    ON atlas.escolas (co_entidade);

CREATE INDEX IF NOT EXISTS idx_escolas_co_municipio
    ON atlas.escolas (co_municipio);

CREATE INDEX IF NOT EXISTS idx_escolas_dependencia
    ON atlas.escolas (tp_dependencia);

-- Índice parcial: escolas em atividade (casos de uso mais comuns)
CREATE INDEX IF NOT EXISTS idx_escolas_ativas_geom
    ON atlas.escolas USING GIST (geom)
    WHERE tp_situacao_funcionamento = 1;

-- Busca por nome
CREATE INDEX IF NOT EXISTS idx_escolas_nome_trgm
    ON atlas.escolas USING GIN (no_entidade gin_trgm_ops);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES ESPACIAIS GiST — Estabelecimentos de Saúde
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_saude_geom
    ON atlas.estabelecimentos_saude USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_saude_co_cnes
    ON atlas.estabelecimentos_saude (co_cnes);

CREATE INDEX IF NOT EXISTS idx_saude_co_municipio
    ON atlas.estabelecimentos_saude (co_municipio);

CREATE INDEX IF NOT EXISTS idx_saude_tp_unidade
    ON atlas.estabelecimentos_saude (tp_unidade);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES — Malha Viária
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_viaria_geom
    ON atlas.malha_viaria_osm USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_viaria_highway
    ON atlas.malha_viaria_osm (highway);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES — Ocorrências de Segurança
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sinesp_co_municipio_ano
    ON atlas.ocorrencias_seguranca (co_municipio, ano, mes);

CREATE INDEX IF NOT EXISTS idx_sinesp_tipo_crime
    ON atlas.ocorrencias_seguranca (tipo_crime);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES — Acessibilidade
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_acessib_cd_setor
    ON atlas.acessibilidade_educacional (cd_setor);

CREATE INDEX IF NOT EXISTS idx_acessib_dist
    ON atlas.acessibilidade_educacional (distancia_eucl_km);

-- ────────────────────────────────────────────────────────────
-- ÍNDICES — Cobertura MapBiomas
-- ────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_mapbiomas_municipio_ano
    ON atlas.cobertura_solo_mapbiomas (co_municipio, ano);

-- ────────────────────────────────────────────────────────────
-- CLUSTER: reorganiza fisicamente setores pelo índice espacial
-- (executar manualmente após carga inicial — operação pesada)
-- CLUSTER atlas.setores_censitarios USING idx_setores_geom;
-- ────────────────────────────────────────────────────────────

-- ────────────────────────────────────────────────────────────
-- FUNÇÃO MVT: gera tile vetorial para uma camada
-- Usada pela API FastAPI para o endpoint /tiles/{z}/{x}/{y}
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION atlas.get_mvt_setores(
    p_z INTEGER,
    p_x INTEGER,
    p_y INTEGER
)
RETURNS BYTEA AS $$
DECLARE
    v_tile   BYTEA;
BEGIN
    -- Guard: setores só fazem sentido a partir do zoom 8
    IF p_z < 8 THEN
        RETURN NULL;
    END IF;

    SELECT ST_AsMVT(q.*, 'setores_censitarios', 4096, 'geom_mvt')
    INTO v_tile
    FROM (
        SELECT
            s.cd_setor,
            s.nm_municipio,
            s.tipo_setor,
            s.nm_tipo_setor,
            s.pop_total,
            s.domicilios_total,
            s.renda_media_domicilio,
            a.distancia_eucl_km    AS dist_escola_km,
            a.qt_escolas_5km,
            a.qt_escolas_publicas_5km,
            -- Simplificação adaptativa ao zoom
            ST_AsMVTGeom(
                CASE
                    WHEN p_z < 10 THEN ST_Simplify(ST_Transform(s.geom, 3857), 20)
                    ELSE ST_Transform(s.geom, 3857)
                END,
                ST_TileEnvelope(p_z, p_x, p_y),
                4096,
                64,
                TRUE
            ) AS geom_mvt
        FROM atlas.setores_censitarios s
        LEFT JOIN atlas.acessibilidade_educacional a ON a.cd_setor = s.cd_setor
        WHERE s.geom && ST_Transform(ST_TileEnvelope(p_z, p_x, p_y, margin => 0.03125), 4326)
    ) q
    WHERE q.geom_mvt IS NOT NULL;

    RETURN COALESCE(v_tile, ''::BYTEA);
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;

CREATE OR REPLACE FUNCTION atlas.get_mvt_escolas(
    p_z INTEGER,
    p_x INTEGER,
    p_y INTEGER
)
RETURNS BYTEA AS $$
DECLARE
    v_tile BYTEA;
BEGIN
    -- Escolas: renderiza a partir do zoom 8
    IF p_z < 8 THEN
        RETURN NULL;
    END IF;

    SELECT ST_AsMVT(q.*, 'escolas', 4096, 'geom_mvt')
    INTO v_tile
    FROM (
        SELECT
            e.co_entidade,
            e.no_entidade,
            e.tp_dependencia,
            e.nm_dependencia,
            e.no_municipio,
            e.in_fund_anos_iniciais,
            e.in_fund_anos_finais,
            e.in_medio_regular,
            e.qt_mat_bas,
            ST_AsMVTGeom(
                ST_Transform(e.geom, 3857),
                ST_TileEnvelope(p_z, p_x, p_y),
                4096, 64, TRUE
            ) AS geom_mvt
        FROM atlas.escolas e
        WHERE e.geom && ST_Transform(ST_TileEnvelope(p_z, p_x, p_y, margin => 0.03125), 4326)
          AND e.tp_situacao_funcionamento = 1  -- apenas em atividade
    ) q
    WHERE q.geom_mvt IS NOT NULL;

    RETURN COALESCE(v_tile, ''::BYTEA);
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;

CREATE OR REPLACE FUNCTION atlas.get_mvt_municipios(
    p_z INTEGER,
    p_x INTEGER,
    p_y INTEGER
)
RETURNS BYTEA AS $$
DECLARE
    v_tile BYTEA;
BEGIN
    SELECT ST_AsMVT(q.*, 'municipios', 4096, 'geom_mvt')
    INTO v_tile
    FROM (
        SELECT
            m.cd_municipio,
            m.nm_municipio,
            m.area_km2,
            m.populacao_2022,
            (SELECT COUNT(*) FROM atlas.escolas e WHERE e.co_municipio = m.cd_municipio) AS qt_escolas,
            ST_AsMVTGeom(
                -- Simplificação mais agressiva em zooms baixos
                CASE
                    WHEN p_z < 7 THEN ST_Simplify(ST_Transform(m.geom, 3857), 100)
                    WHEN p_z < 9 THEN ST_Simplify(ST_Transform(m.geom, 3857), 50)
                    ELSE ST_Transform(m.geom, 3857)
                END,
                ST_TileEnvelope(p_z, p_x, p_y),
                4096, 64, TRUE
            ) AS geom_mvt
        FROM atlas.municipios_mt m
        WHERE m.geom && ST_Transform(ST_TileEnvelope(p_z, p_x, p_y, margin => 0.03125), 4326)
    ) q
    WHERE q.geom_mvt IS NOT NULL;

    RETURN COALESCE(v_tile, ''::BYTEA);
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;

CREATE OR REPLACE FUNCTION atlas.get_mvt_saude(
    p_z INTEGER,
    p_x INTEGER,
    p_y INTEGER
)
RETURNS BYTEA AS $$
DECLARE
    v_tile BYTEA;
BEGIN
    IF p_z < 8 THEN
        RETURN NULL;
    END IF;

    SELECT ST_AsMVT(q.*, 'saude', 4096, 'geom_mvt')
    INTO v_tile
    FROM (
        SELECT
            es.co_cnes,
            es.no_fantasia,
            es.nm_tp_unidade,
            es.tp_gestao,
            es.qt_leitos_total,
            ST_AsMVTGeom(
                ST_Transform(es.geom, 3857),
                ST_TileEnvelope(p_z, p_x, p_y),
                4096, 64, TRUE
            ) AS geom_mvt
        FROM atlas.estabelecimentos_saude es
        WHERE es.geom && ST_Transform(ST_TileEnvelope(p_z, p_x, p_y, margin => 0.03125), 4326)
    ) q
    WHERE q.geom_mvt IS NOT NULL;

    RETURN COALESCE(v_tile, ''::BYTEA);
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;
