"""
api/routers/metadata.py
=======================
Endpoints de Metadados e Linhagem Canônica de Dados do RootL Atlas.

Fornece aos usuários e componentes da interface (como o painel FeatureDetail)
o inventário oficial de governança de dados:
- Órgão emissor / autoridade pública
- Metodologia de coleta e agregação
- Resolução espacial canônica e restrições éticas
- Links oficiais e permanentes de download
- Frequência de atualização e licença
- Estatísticas de banco em tempo real (última extração, total de feições)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Path as FPath
from fastapi.responses import ORJSONResponse
from loguru import logger

from database import get_connection

router = APIRouter(prefix="/metadata", tags=["metadados"])

# Dicionário de fallback rico e canônico baseado no catalog.yaml
CANONICAL_LAYER_METADATA: dict[str, dict[str, Any]] = {
    "setores": {
        "fonte_id": "ibge_censo_2022_agregados_setores",
        "nome": "Censo Demográfico 2022 — Agregados por Setores Censitários",
        "orgao": "IBGE — Instituto Brasileiro de Geografia e Estatística",
        "dominio": "Demografia & Território",
        "resolucao_espacial": "Setor Censitário (intramunicipal)",
        "frequencia_atualizacao": "Decenal",
        "formato": "GeoPackage / CSV com Atributos Agregados",
        "crs": "EPSG:4674 (SIRGAS 2000) / EPSG:4326 (WGS 84)",
        "url_origem": "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/setores/csv/BR_setores_CD2022.csv",
        "url_portal": "https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html",
        "licenca": "Dados Abertos Governamentais (CC-BY 4.0 / Domínio Público)",
        "metodologia": (
            "Resultados agregados do Censo Demográfico 2022 por setor censitário. "
            "Contém contagem oficial de população residente, total de domicílios, domicílios ocupados "
            "e divisão por sexo (homens e mulheres). Em áreas urbanas com delimitação legal, informa nome do bairro."
        ),
        "tabela_gold": "atlas.setores_censitarios",
    },
    "municipios": {
        "fonte_id": "ibge_censo_2022_populacao",
        "nome": "População Residente Municipal — Censo Demográfico 2022",
        "orgao": "IBGE — Instituto Brasileiro de Geografia e Estatística",
        "dominio": "Demografia & Território",
        "resolucao_espacial": "Municipal (141 municípios de Mato Grosso)",
        "frequencia_atualizacao": "Decenal / Estimativas Anuais",
        "formato": "API SIDRA (Tabela 4709) & Malha Municipal Vetorial",
        "crs": "EPSG:4674 (SIRGAS 2000) / EPSG:4326 (WGS 84)",
        "url_origem": "https://apisidra.ibge.gov.br/values/t/4709/n6/in%20n3%2051/v/93/p/2022",
        "url_portal": "https://sidra.ibge.gov.br/tabela/4709",
        "licenca": "Dados Abertos Governamentais (CC-BY 4.0 / Domínio Público)",
        "metodologia": (
            "População residente apurada no Censo Demográfico 2022 para todos os 141 municípios de Mato Grosso. "
            "Cruzada com o cálculo geométrico de área territorial oficial para obtenção da densidade demográfica (hab/km²)."
        ),
        "tabela_gold": "atlas.municipios_mt",
    },
    "escolas": {
        "fonte_id": "inep_censo_escolar_2025",
        "nome": "Censo da Educação Básica — Microdados Georreferenciados",
        "orgao": "INEP — Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira",
        "dominio": "Educação",
        "resolucao_espacial": "Ponto geográfico (Escola / Estabelecimento de Ensino)",
        "frequencia_atualizacao": "Anual",
        "formato": "Microdados CSV / Shapefile",
        "crs": "EPSG:4326 (WGS 84)",
        "url_origem": "https://download.inep.gov.br/microdados/microdados_educacao_basica_2024.zip",
        "url_portal": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar",
        "licenca": "Dados Abertos Governamentais (Domínio Público)",
        "metodologia": (
            "Levantamento estatístico anual da educação básica brasileira. Contém dependência administrativa (Federal, "
            "Estadual, Municipal, Privada), etapas de ensino ofertadas (Creche, Pré-escola, Fundamental I/II, Médio, EJA), "
            "infraestrutura escolar e total de matrículas."
        ),
        "tabela_gold": "atlas.escolas",
    },
    "saude": {
        "fonte_id": "datasus_cnes_estab",
        "nome": "Cadastro Nacional de Estabelecimentos de Saúde (CNES)",
        "orgao": "DATASUS / Ministério da Saúde",
        "dominio": "Saúde Pública",
        "resolucao_espacial": "Ponto geográfico (Estabelecimento de Saúde)",
        "frequencia_atualizacao": "Mensal",
        "formato": "Disseminação Pública DATASUS (DBC / CSV)",
        "crs": "EPSG:4326 (WGS 84)",
        "url_origem": "ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/ST/",
        "url_portal": "http://cnes.datasus.gov.br/",
        "licenca": "Dados Abertos Governamentais (Domínio Público)",
        "metodologia": (
            "Base cadastral oficial de todas as unidades de assistência à saúde em Mato Grosso. Informa tipo de unidade "
            "(Hospital, UBS, Pronto Atendimento, Clínica), esfera de gestão, leitos totais e leitos SUS."
        ),
        "tabela_gold": "atlas.estabelecimentos_saude",
    },
    "malha_viaria": {
        "fonte_id": "osm_mt_pbf",
        "nome": "OpenStreetMap — Extrato Regional da Rede Viária (Mato Grosso)",
        "orgao": "OpenStreetMap Contributors / Geofabrik",
        "dominio": "Infraestrutura de Transportes",
        "resolucao_espacial": "Segmentos de Vias (LineString)",
        "frequencia_atualizacao": "Semanal / Contínua",
        "formato": "Protocolbuffer Binary Format (.osm.pbf)",
        "crs": "EPSG:4326 (WGS 84)",
        "url_origem": "https://download.geofabrik.de/south-america/brazil/centro-oeste-latest.osm.pbf",
        "url_portal": "https://www.openstreetmap.org/",
        "licenca": "Open Database License (ODbL 1.0)",
        "metodologia": (
            "Rede viária colaborativa filtrada para rodovias federais/estaduais (motorway, trunk, primary), vias secundárias "
            "e vias coletoras urbanas de Mato Grosso com classificação de superfície e velocidade."
        ),
        "tabela_gold": "atlas.malha_viaria_osm",
    },
    "seguranca": {
        "fonte_id": "sinesp_vde_mun",
        "nome": "Sistema Nacional de Informações de Segurança Pública (SINESP)",
        "orgao": "Ministério da Justiça e Segurança Pública (MJSP)",
        "dominio": "Segurança Pública",
        "resolucao_espacial": "Municipal (Mato Grosso)",
        "frequencia_atualizacao": "Mensal",
        "formato": "Dados Abertos CSV",
        "crs": "Sem geometria própria (associado ao polígono municipal)",
        "url_origem": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/sinesp-1/dados-abertos-sinesp",
        "url_portal": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/sinesp-1",
        "licenca": "Dados Abertos Governamentais (Domínio Público)",
        "metodologia": (
            "Registros consolidados de ocorrências policiais e vítimas por tipologia criminal (Homicídio doloso, Lesão corporal "
            "seguida de morte, Roubo de veículo, Roubo seguido de morte, Roubo de carga, Furto de veículo, Estupro). "
            "NOTA ÉTICA: A resolução máxima é estritamente MUNICIPAL. É proibido inferir localização pontual ou de bairro."
        ),
        "tabela_gold": "atlas.ocorrencias_seguranca",
    },
    "queimadas": {
        "fonte_id": "inpe_bdqueimadas_mensal",
        "nome": "BDQueimadas — Programa Queimadas (INPE)",
        "orgao": "INPE — Instituto Nacional de Pesquisas Espaciais",
        "dominio": "Meio Ambiente & Clima",
        "resolucao_espacial": "Ponto geográfico (Resolução do sensor ótico do satélite)",
        "frequencia_atualizacao": "Quase tempo real / Mensal Consolidado",
        "formato": "CSV / GeoJSON",
        "crs": "EPSG:4326 (WGS 84)",
        "url_origem": "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/",
        "url_portal": "https://terrabrasilis.dpi.inpe.br/queimadas/bdqueimadas/",
        "licenca": "Dados Abertos Governamentais (Domínio Público)",
        "metodologia": (
            "Detecção termal de focos de calor ativos a partir de radiômetros espaciais (MODIS/Terra, MODIS/Aqua, VIIRS/NOAA-20, "
            "GOES-16). Contém Potência Radiativa do Fogo (FRP em MW), Risco Meteorológico de Fogo e dias sem chuva."
        ),
        "tabela_gold": "atlas.focos_queimadas",
    },
    "cobertura_solo": {
        "fonte_id": "mapbiomas_col11_lu",
        "nome": "MapBiomas — Cobertura e Uso da Terra (Coleção 11)",
        "orgao": "Rede MapBiomas (Observatório do Clima / Institutos Parceiros)",
        "dominio": "Uso da Terra & Agropecuária",
        "resolucao_espacial": "Pixel 30 metros (Landsat) agregado por município",
        "frequencia_atualizacao": "Anual",
        "formato": "Cloud Optimized GeoTIFF (COG)",
        "crs": "EPSG:4326 (WGS 84)",
        "url_origem": "https://storage.googleapis.com/mapbiomas-public/brasil/collection-8/lclu/coverage/",
        "url_portal": "https://brasil.mapbiomas.org/",
        "licenca": "Creative Commons Attribution 4.0 International (CC-BY 4.0)",
        "metodologia": (
            "Classificação automatizada de imagens multiespectrais Landsat com algoritmos de Random Forest e aprendizado "
            "profundo. Agrupada em classes temáticas como Formação Florestal, Savana, Pastagem, Soja, Algodão e Corpos d'Água."
        ),
        "tabela_gold": "atlas.cobertura_solo_mapbiomas",
    },
}


def load_catalog_yaml() -> list[dict[str, Any]]:
    """Tenta carregar o catálogo de catalog.yaml se disponível."""
    candidates = [
        Path("/app/catalog.yaml"),
        Path("/app/pipeline/catalog.yaml"),
        Path(__file__).resolve().parent.parent.parent / "pipeline" / "catalog.yaml",
        Path("catalog.yaml"),
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "sources" in data:
                        return data["sources"]
            except Exception as e:
                logger.warning(f"Erro ao ler {p}: {e}")
    return []


@router.get(
    "/catalog",
    summary="Catálogo Geral de Fontes de Dados",
    response_class=ORJSONResponse,
)
async def get_catalog() -> dict[str, Any]:
    """
    Retorna o inventário completo de fontes de dados cadastradas no RootL Atlas,
    combinando as diretrizes de governança do catalog.yaml com as camadas ativas.
    """
    sources_from_yaml = load_catalog_yaml()

    return {
        "status": "success",
        "total_fontes": len(CANONICAL_LAYER_METADATA),
        "fontes": CANONICAL_LAYER_METADATA,
        "catalogo_yaml_sources": sources_from_yaml,
    }


@router.get(
    "/layer/{layer_id}",
    summary="Metadados de uma Camada Específica",
    response_class=ORJSONResponse,
)
async def get_layer_metadata(
    layer_id: str = FPath(..., description="ID da camada (setores, municipios, escolas, saude, seguranca, queimadas, malha_viaria, cobertura_solo)"),
) -> dict[str, Any]:
    """
    Retorna os metadados canônicos e estatísticas atuais da tabela correspondente no banco.
    """
    clean_id = layer_id.lower().replace("-", "_")
    if clean_id not in CANONICAL_LAYER_METADATA:
        # Tenta mapear sinônimos
        synonyms = {
            "viaria": "malha_viaria",
            "educacao": "escolas",
            "focos": "queimadas",
            "mapbiomas": "cobertura_solo",
        }
        clean_id = synonyms.get(clean_id, clean_id)

    meta = CANONICAL_LAYER_METADATA.get(clean_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Metadados para camada '{layer_id}' não encontrados. Opções: {list(CANONICAL_LAYER_METADATA.keys())}",
        )

    # Consulta dados dinâmicos do PostgreSQL
    stats = {}
    table_name = meta.get("tabela_gold")
    if table_name:
        try:
            async with get_connection() as conn:
                # Total de registros e data máxima de extração
                query = f"""
                    SELECT
                        COUNT(*)::int AS total_registros,
                        TO_CHAR(MAX(data_extracao), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ultima_extracao,
                        MAX(versao_processamento) AS versao_processamento
                    FROM {table_name}
                """
                row = await conn.fetchrow(query)
                if row:
                    stats = {
                        "total_registros": row["total_registros"],
                        "ultima_extracao": row["ultima_extracao"],
                        "versao_processamento": row["versao_processamento"],
                    }
        except Exception as e:
            logger.debug(f"Não foi possível obter stats da tabela {table_name}: {e}")

    return {
        "layer_id": clean_id,
        "metadata": meta,
        "database_stats": stats,
    }


@router.get(
    "/stats",
    summary="Sumário de Governança e Volumes do Atlas",
    response_class=ORJSONResponse,
)
async def get_summary_stats() -> dict[str, Any]:
    """
    Retorna as métricas agregadas da base de dados do Mato Grosso.
    """
    async with get_connection() as conn:
        row_mun = await conn.fetchrow(
            "SELECT COUNT(*)::int AS total_mun, SUM(populacao_2022)::bigint AS pop_total FROM atlas.municipios_mt"
        )
        row_set = await conn.fetchrow(
            "SELECT COUNT(*)::int AS total_setores, SUM(domicilios_total)::bigint AS dom_total FROM atlas.setores_censitarios"
        )
        row_esc = await conn.fetchrow(
            "SELECT COUNT(*)::int AS total_escolas FROM atlas.escolas WHERE tp_situacao_funcionamento = 1"
        )
        row_sau = await conn.fetchrow(
            "SELECT COUNT(*)::int AS total_saude FROM atlas.estabelecimentos_saude"
        )
        row_queim = await conn.fetchrow(
            "SELECT COUNT(*)::int AS total_focos FROM atlas.focos_queimadas"
        )
        row_seg = await conn.fetchrow(
            "SELECT SUM(qtd_ocorrencias)::bigint AS total_ocorrencias FROM atlas.ocorrencias_seguranca"
        )

    return {
        "uf": "MT",
        "nome_uf": "Mato Grosso",
        "municipios": {
            "total": row_mun["total_mun"] if row_mun else 141,
            "populacao_censo_2022": row_mun["pop_total"] if row_mun else 3658649,
        },
        "setores_censitarios": {
            "total": row_set["total_setores"] if row_set else 9381,
            "domicilios_censo_2022": row_set["dom_total"] if row_set else 1566334,
        },
        "escolas_ativas": row_esc["total_escolas"] if row_esc else 3191,
        "estabelecimentos_saude": row_sau["total_saude"] if row_sau else 8788,
        "focos_queimadas_monitorados": row_queim["total_focos"] if row_queim else 233785,
        "ocorrencias_seguranca_sinesp": row_seg["total_ocorrencias"] if row_seg else 0,
        "sistema_referencia": "SIRGAS 2000 (EPSG:4674) / WGS 84 (EPSG:4326)",
    }
