-- ============================================================
-- RootL Atlas — Inicialização do Banco de Dados
-- PostgreSQL 16 + PostGIS 3.4
-- ============================================================

-- Extensões fundamentais
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- busca textual fuzzy

-- Schema principal
CREATE SCHEMA IF NOT EXISTS atlas;
SET search_path TO atlas, public;

-- ============================================================
-- TABELA: municipios_mt
-- Municípios do estado de Mato Grosso
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.municipios_mt (
    id                  SERIAL PRIMARY KEY,
    cd_municipio        VARCHAR(7)  NOT NULL UNIQUE,  -- Código IBGE 7 dígitos
    nm_municipio        TEXT        NOT NULL,
    nm_municipio_ascii  TEXT        NOT NULL,          -- Sem acentos, para busca
    cd_uf               VARCHAR(2)  NOT NULL DEFAULT '51',
    nm_uf               TEXT        NOT NULL DEFAULT 'Mato Grosso',
    sg_uf               VARCHAR(2)  NOT NULL DEFAULT 'MT',
    area_km2            NUMERIC(12, 4),
    populacao_2022      INTEGER,
    centroide           GEOMETRY(POINT, 4326),
    geom                GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    -- Linhagem
    fonte_id            TEXT        NOT NULL DEFAULT 'ibge_censo_2022_setores',
    data_extracao       TIMESTAMPTZ,
    hash_arquivo        TEXT,
    url_origem          TEXT,
    versao_processamento TEXT,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABELA: setores_censitarios
-- Setores censitários do IBGE — unidade espacial fundamental
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.setores_censitarios (
    id                  SERIAL PRIMARY KEY,
    cd_setor            VARCHAR(15) NOT NULL UNIQUE,  -- Geocódigo completo (15 dígitos)
    cd_municipio        VARCHAR(7)  NOT NULL,
    nm_municipio        TEXT        NOT NULL,
    cd_uf               VARCHAR(2)  NOT NULL DEFAULT '51',
    sg_uf               VARCHAR(2)  NOT NULL DEFAULT 'MT',
    cd_distrito         VARCHAR(9),
    nm_distrito         TEXT,
    cd_subdistrito      VARCHAR(11),
    nm_subdistrito      TEXT,
    nm_bairro           TEXT,
    -- Tipologia do setor
    tipo_setor          SMALLINT,                      -- 1=Urbano, 2=Rural, etc.
    nm_tipo_setor       TEXT,
    situacao_setor      SMALLINT,
    -- Dados demográficos do Censo 2022
    pop_total           INTEGER     DEFAULT 0,
    pop_homens          INTEGER     DEFAULT 0,
    pop_mulheres        INTEGER     DEFAULT 0,
    domicilios_total    INTEGER     DEFAULT 0,
    domicilios_ocupados INTEGER     DEFAULT 0,
    renda_media_domicilio NUMERIC(10,2),
    -- Geometria (SIRGAS 2000 / WGS84 = EPSG:4674 ≈ EPSG:4326)
    centroide           GEOMETRY(POINT, 4326),
    geom                GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    area_km2            NUMERIC(12, 6),
    -- Linhagem de dados
    fonte_id            TEXT        NOT NULL DEFAULT 'ibge_censo_2022_setores',
    data_extracao       TIMESTAMPTZ,
    hash_arquivo        TEXT,
    url_origem          TEXT,
    versao_processamento TEXT,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- FK
    CONSTRAINT fk_setor_municipio
        FOREIGN KEY (cd_municipio)
        REFERENCES atlas.municipios_mt (cd_municipio)
        ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED
);

-- ============================================================
-- TABELA: escolas
-- Infraestrutura educacional — Censo Escolar INEP
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.escolas (
    id                      SERIAL PRIMARY KEY,
    co_entidade             BIGINT      NOT NULL UNIQUE,  -- Código INEP
    no_entidade             TEXT        NOT NULL,
    -- Classificação
    tp_dependencia          SMALLINT    NOT NULL,          -- 1=Federal, 2=Estadual, 3=Municipal, 4=Privada
    nm_dependencia          TEXT        NOT NULL,
    tp_situacao_funcionamento SMALLINT  NOT NULL,          -- 1=Em atividade, 2=Paralisada, etc.
    nm_situacao             TEXT,
    -- Localização administrativa
    co_municipio            VARCHAR(7)  NOT NULL,
    no_municipio            TEXT        NOT NULL,
    no_bairro               TEXT,
    -- Etapas de ensino ofertadas (flags booleanas)
    in_inf_creche           BOOLEAN     DEFAULT FALSE,
    in_inf_pre_escola       BOOLEAN     DEFAULT FALSE,
    in_fund_anos_iniciais   BOOLEAN     DEFAULT FALSE,
    in_fund_anos_finais     BOOLEAN     DEFAULT FALSE,
    in_medio_regular        BOOLEAN     DEFAULT FALSE,
    in_medio_integrado      BOOLEAN     DEFAULT FALSE,
    in_eja                  BOOLEAN     DEFAULT FALSE,
    in_especial_exclusiva   BOOLEAN     DEFAULT FALSE,
    -- Infraestrutura
    in_laboratorio_informatica BOOLEAN  DEFAULT FALSE,
    in_laboratorio_ciencias    BOOLEAN  DEFAULT FALSE,
    in_biblioteca           BOOLEAN     DEFAULT FALSE,
    in_quadra_esportes      BOOLEAN     DEFAULT FALSE,
    in_acessibilidade       BOOLEAN     DEFAULT FALSE,
    qt_salas_utilizadas     SMALLINT,
    qt_equip_computador     INTEGER,
    qt_mat_bas              INTEGER,                       -- Matrículas educação básica
    -- Geometria
    geom                    GEOMETRY(POINT, 4326),
    -- Referência ao setor censitário
    cd_setor_ref            VARCHAR(15),
    -- Linhagem
    ano_censo               SMALLINT    NOT NULL,
    fonte_id                TEXT        NOT NULL DEFAULT 'inep_censo_escolar_2025',
    data_extracao           TIMESTAMPTZ,
    hash_arquivo            TEXT,
    url_origem              TEXT,
    versao_processamento    TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABELA: estabelecimentos_saude
-- Cadastro Nacional de Estabelecimentos de Saúde — CNES
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.estabelecimentos_saude (
    id                      SERIAL PRIMARY KEY,
    co_cnes                 VARCHAR(7)  NOT NULL UNIQUE,
    no_fantasia             TEXT,
    no_razao_social         TEXT,
    -- Classificação
    tp_unidade              SMALLINT,
    nm_tp_unidade           TEXT,
    tp_gestao               CHAR(1),                      -- 'M'=Municipal, 'E'=Estadual, 'D'=Dupla
    tp_natureza_juridica    SMALLINT,
    nm_natureza_juridica    TEXT,
    -- Capacidade
    qt_leitos_sus           INTEGER     DEFAULT 0,
    qt_leitos_nao_sus       INTEGER     DEFAULT 0,
    qt_leitos_total         INTEGER     DEFAULT 0,
    -- Serviços ofertados (JSONB para flexibilidade)
    servicos_ofertados      JSONB,
    -- Localização
    co_municipio            VARCHAR(7),
    no_municipio            TEXT,
    no_logradouro           TEXT,
    no_bairro               TEXT,
    -- Geometria
    geom                    GEOMETRY(POINT, 4326),
    cd_setor_ref            VARCHAR(15),
    -- Linhagem
    competencia             DATE,                          -- Mês/ano de referência do CNES
    fonte_id                TEXT        NOT NULL DEFAULT 'datasus_cnes_estab',
    data_extracao           TIMESTAMPTZ,
    hash_arquivo            TEXT,
    url_origem              TEXT,
    versao_processamento    TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABELA: ocorrencias_seguranca
-- Ocorrências SINESP — resolução EXCLUSIVAMENTE municipal
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.ocorrencias_seguranca (
    id                      SERIAL PRIMARY KEY,
    ano                     SMALLINT    NOT NULL,
    mes                     SMALLINT    NOT NULL,
    -- ATENÇÃO: resolução original = município. NUNCA extrapolar para bairros.
    co_municipio            VARCHAR(7)  NOT NULL,
    nm_municipio            TEXT        NOT NULL,
    tipo_crime              TEXT        NOT NULL,
    -- Contagens
    qtd_ocorrencias         INTEGER     DEFAULT 0,
    qtd_vitimas             INTEGER     DEFAULT 0,
    qtd_vitimas_femininas   INTEGER,
    qtd_vitimas_masculinas  INTEGER,
    -- NOTA METODOLÓGICA: geometria = polígono do município (resolução máxima honesta)
    geom                    GEOMETRY(MULTIPOLYGON, 4326), -- herdado de municipios_mt
    resolucao_original      TEXT        NOT NULL DEFAULT 'municipio',
    nota_metodologica       TEXT        NOT NULL DEFAULT
        'Dados agregados em nível municipal conforme fornecido pelo SINESP. ' ||
        'Não representa ocorrências em locais específicos dentro do município.',
    -- Linhagem
    fonte_id                TEXT        NOT NULL DEFAULT 'sinesp_vde_mun',
    data_extracao           TIMESTAMPTZ,
    hash_arquivo            TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ano, mes, co_municipio, tipo_crime)
);

-- ============================================================
-- TABELA: acessibilidade_educacional
-- Métricas de acessibilidade pré-calculadas
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.acessibilidade_educacional (
    id                          SERIAL PRIMARY KEY,
    cd_setor                    VARCHAR(15) NOT NULL UNIQUE,
    -- Escola mais próxima (distância euclidiana — MVP)
    co_entidade_mais_proxima    BIGINT,
    distancia_eucl_km           NUMERIC(8, 3),
    -- Escola mais próxima por tipo
    co_entidade_publica_prox    BIGINT,
    dist_publica_eucl_km        NUMERIC(8, 3),
    co_entidade_fund_prox       BIGINT,
    dist_fund_eucl_km           NUMERIC(8, 3),
    -- Contagem de escolas por raio
    qt_escolas_5km              SMALLINT    DEFAULT 0,
    qt_escolas_10km             SMALLINT    DEFAULT 0,
    qt_escolas_publicas_5km     SMALLINT    DEFAULT 0,
    -- Pop sem acesso (proxy: >10km da escola fundamental pública)
    pop_sem_acesso_proxy        INTEGER,
    -- Método utilizado
    metodo_calculo              TEXT        NOT NULL DEFAULT 'distancia_euclidiana',
    nota_metodologica           TEXT        DEFAULT
        'Distância euclidiana (linha reta). Estimativa conservadora. ' ||
        'Fase 2 substituirá por tempo de viagem via rede viária (OSRM/Valhalla).',
    -- Linhagem
    data_calculo                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    versao_pipeline             TEXT
);

-- ============================================================
-- TABELA: malha_viaria_osm
-- Rede viária derivada do OpenStreetMap
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.malha_viaria_osm (
    id                  BIGSERIAL   PRIMARY KEY,
    osm_id              BIGINT      NOT NULL UNIQUE,
    highway             TEXT,                             -- Classificação OSM da via
    name                TEXT,
    oneway              BOOLEAN     DEFAULT FALSE,
    lanes               SMALLINT,
    maxspeed            SMALLINT,                         -- km/h
    surface             TEXT,
    -- Geometria da via
    geom                GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_m            NUMERIC(12, 2),
    -- Linhagem
    fonte_id            TEXT        NOT NULL DEFAULT 'osm_mt_pbf',
    data_extracao       TIMESTAMPTZ,
    hash_arquivo        TEXT,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABELA: cobertura_solo_mapbiomas
-- Cobertura e uso da terra — MapBiomas (resolução municipal)
-- Nota: raster COG processado e agregado por município para MVP
-- ============================================================
CREATE TABLE IF NOT EXISTS atlas.cobertura_solo_mapbiomas (
    id                  SERIAL PRIMARY KEY,
    co_municipio        VARCHAR(7)  NOT NULL,
    ano                 SMALLINT    NOT NULL,
    classe_mapbiomas    INTEGER     NOT NULL,              -- Código da classe MapBiomas
    nm_classe           TEXT        NOT NULL,
    area_ha             NUMERIC(14, 4),
    -- Linhagem
    colecao             SMALLINT    NOT NULL DEFAULT 11,
    fonte_id            TEXT        NOT NULL DEFAULT 'mapbiomas_col11_lu',
    data_extracao       TIMESTAMPTZ,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (co_municipio, ano, classe_mapbiomas)
);

-- ============================================================
-- Triggers: atualiza campo atualizado_em automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION atlas.set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_municipios_mt_atualizado
    BEFORE UPDATE ON atlas.municipios_mt
    FOR EACH ROW EXECUTE FUNCTION atlas.set_atualizado_em();

CREATE OR REPLACE TRIGGER trg_setores_atualizado
    BEFORE UPDATE ON atlas.setores_censitarios
    FOR EACH ROW EXECUTE FUNCTION atlas.set_atualizado_em();

CREATE OR REPLACE TRIGGER trg_escolas_atualizado
    BEFORE UPDATE ON atlas.escolas
    FOR EACH ROW EXECUTE FUNCTION atlas.set_atualizado_em();

CREATE OR REPLACE TRIGGER trg_saude_atualizado
    BEFORE UPDATE ON atlas.estabelecimentos_saude
    FOR EACH ROW EXECUTE FUNCTION atlas.set_atualizado_em();

-- ============================================================
-- View: resumo_municipio
-- Consolida métricas por município para o dashboard
-- ============================================================
CREATE OR REPLACE VIEW atlas.vw_resumo_municipio AS
SELECT
    m.cd_municipio,
    m.nm_municipio,
    m.area_km2,
    m.populacao_2022,
    COUNT(DISTINCT s.cd_setor) AS qt_setores,
    COUNT(DISTINCT e.co_entidade) AS qt_escolas_total,
    COUNT(DISTINCT e.co_entidade) FILTER (WHERE e.tp_dependencia IN (1,2,3)) AS qt_escolas_publicas,
    COUNT(DISTINCT es.co_cnes) AS qt_estabelecimentos_saude,
    COUNT(DISTINCT es.co_cnes) FILTER (WHERE es.qt_leitos_total > 0) AS qt_hospitais,
    m.geom
FROM atlas.municipios_mt m
LEFT JOIN atlas.setores_censitarios s ON s.cd_municipio = m.cd_municipio
LEFT JOIN atlas.escolas e ON e.co_municipio = m.cd_municipio
LEFT JOIN atlas.estabelecimentos_saude es ON es.co_municipio = m.cd_municipio
GROUP BY m.cd_municipio, m.nm_municipio, m.area_km2, m.populacao_2022, m.geom;

-- ============================================================
-- Comentários de documentação nas tabelas
-- ============================================================
COMMENT ON TABLE atlas.setores_censitarios IS
    'Setores censitários do IBGE (Censo 2022). Unidade espacial fundamental da plataforma. '
    'Fonte: IBGE — Malha de Setores Censitários. SIRGAS 2000 / WGS84 (EPSG:4326).';

COMMENT ON TABLE atlas.escolas IS
    'Infraestrutura educacional. Fonte: INEP Censo Escolar. '
    'Coordenadas originais do registro geocodificado do INEP.';

COMMENT ON TABLE atlas.ocorrencias_seguranca IS
    'Ocorrências do SINESP. ATENÇÃO: resolução máxima = município. '
    'Não extrapolar para bairros ou vias — dado não existe nessa granularidade.';

COMMENT ON COLUMN atlas.escolas.geom IS
    'Ponto geocodificado original do INEP. Projeção WGS84 (EPSG:4326).';

COMMENT ON COLUMN atlas.acessibilidade_educacional.metodo_calculo IS
    'MVP: distância euclidiana. Fase 2: tempo de viagem via OSRM (rede viária OSM).';
