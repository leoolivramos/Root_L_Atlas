# RootL Atlas 🗺️

> **Plataforma geoespacial de inteligência territorial para o Estado de Mato Grosso.**  
> Dados públicos de educação, saúde e infraestrutura com análise de acessibilidade e linhagem completa.

---

## O que é o RootL Atlas?

O RootL Atlas não é um painel de visualização estático. É uma **plataforma de inteligência territorial** que:

- Ingere dados brutos de **IBGE, INEP, DATASUS e OpenStreetMap** automaticamente
- Preserva a **linhagem completa** de cada ponto de dado (origem, hash SHA-256, data de extração, URL)
- Processa geometrias em três camadas de qualidade (**Bronze → Silver → Gold**)
- Gera métricas de **acessibilidade educacional** por setor censitário
- Serve **Mosaicos Vetoriais (MVT)** em tempo real via PostGIS para o frontend MapLibre GL

---

## Stack Tecnológico

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| **Pipeline** | Python 3.11 + GeoPandas 1.0 + DuckDB | Processamento geoespacial eficiente single-node (ADR-001) |
| **Formatos** | GeoParquet + bbox_col | Filtro espacial por pushdown (ADR-002, 26x mais rápido) |
| **Banco** | PostgreSQL 15 + PostGIS 3.4 | ST_AsMVT + GiST indexes para tiles em tempo real |
| **Tiles** | ST_AsMVT (PostGIS) | Zero serialização Python, latência <100ms P99 (ADR-003) |
| **API** | FastAPI + asyncpg | Pool de conexões nativo, respostas ORJson |
| **Frontend** | Vue 3 + Pinia + MapLibre GL 4 | Reatividade de estado, tiles MVT nativos |
| **Orquestração** | Prefect 2 | Linhagem de execução, retries automáticos |
| **Armazenamento** | MinIO (S3-compatível) | Lakehouse local, migrável para S3/GCS |

---

## Início Rápido

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) ou Docker + Docker Compose
- 8GB RAM disponíveis para os containers
- 20GB de espaço em disco (dados do pipeline)

### 1. Configuração

```bash
# Clone o repositório
git clone https://github.com/leoolivramos/Root_L_Atlas.git rootl-atlas
cd rootl-atlas

# Copie e edite as variáveis de ambiente
cp .env.example .env
# Edite .env se necessário (senhas, paths)
```

### 2. Subir a infraestrutura

```bash
make up
```

Aguarde os serviços inicializarem (~60s). Você verá:

```
  🗺️  RootL Atlas iniciado:
  Frontend: http://localhost:5173
  API:      http://localhost:8000/docs
  MinIO:    http://localhost:9001
  Prefect:  http://localhost:4200
```

### 3. Configurar o MinIO (Lakehouse)

```bash
make minio-setup
```

Isso cria os buckets `bronze`, `silver` e `gold` no MinIO local.

### 4. Validar o pipeline (dry-run)

```bash
make pipeline-dry-run
```

Valida o catálogo de fontes e schemas sem baixar nenhum dado.

### 5. Executar o pipeline completo

```bash
make pipeline-run
```

> ⚠️ **Atenção:** O primeiro download pode levar **15-30 minutos** dependendo da sua conexão (Censo IBGE ~800MB, INEP ~500MB). Os downloads são cacheados no Bronze para execuções futuras.

### 6. Acessar a plataforma

Abra http://localhost:5173 no navegador.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│  FONTES PÚBLICAS                                                 │
│  IBGE Censo 2022 · INEP Censo Escolar · DATASUS CNES · OSM      │
└─────────────────────────────────────────────┬───────────────────┘
                                              │ Download + SHA-256
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  BRONZE  (dados brutos + manifesto de linhagem)                  │
│  MinIO / data/bronze/  ·  GeoPackage, CSV, DBC, PBF             │
└─────────────────────────────────────────────┬───────────────────┘
                                              │ Extração + normalização
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SILVER  (legível por máquina, não interpretado semanticamente)  │
│  GeoParquet · UTF-8 · snake_case · deduplicado                   │
└─────────────────────────────────────────────┬───────────────────┘
                                              │ Mapeamento canônico
                                              │ Validação Pandera
                                              │ Spatial join setores
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  GOLD  (modelo canônico + métricas de acessibilidade)            │
│  GeoParquet + bbox_col · Acessibilidade educacional calculada    │
└─────────────┬─────────────────────────────────────────────┬─────┘
              │ PostGIS Loader (upsert)                     │ DuckDB analytics
              ▼                                             ▼
┌────────────────────────────┐               ┌─────────────────────┐
│  PostgreSQL + PostGIS       │               │  Consultas analíticas│
│  atlas.setores_censitarios  │               │  DuckDB / notebooks  │
│  atlas.escolas              │               └─────────────────────┘
│  atlas.acessibilidade_...   │
└─────────────┬───────────────┘
              │ ST_AsMVT (tiles)
              │ ST_AsGeoJSON (features)
              ▼
┌────────────────────────────┐
│  FastAPI + asyncpg          │
│  /tiles/{layer}/{z}/{x}/{y} │
│  /features/{layer}/{id}     │
│  /accessibility/...         │
│  /search                    │
└─────────────┬───────────────┘
              │ MVT + JSON
              ▼
┌────────────────────────────┐
│  Vue 3 + MapLibre GL        │
│  Camadas MVT interativas    │
│  Filtros de acessibilidade  │
│  Linhagem de dados visível  │
└────────────────────────────┘
```

---

## Comandos Úteis

```bash
make help           # Lista todos os comandos
make db-stats       # Contagem de registros nas tabelas
make test-all       # Executa todos os testes
make logs-api       # Logs da API em tempo real
make clean          # Para containers (preserva dados)
make reset          # Para e apaga TODOS os volumes
```

---

## Decisões de Arquitetura (ADRs)

| ADR | Decisão | Resumo |
|-----|---------|--------|
| [ADR-001](docs/adr/ADR-001-lakehouse-local-first.md) | DuckDB vs Spark | Single-node até >4h de processamento |
| [ADR-002](docs/adr/ADR-002-geoparquet-bbox-col.md) | GeoParquet + bbox_col | 26x mais rápido para filtros espaciais |
| [ADR-003](docs/adr/ADR-003-mvt-postgis.md) | ST_AsMVT PostGIS | Zero serialização Python, <100ms P99 |

---

## Escopo MVP (Fase 1)

✅ IBGE Setores Censitários 2022 — Mato Grosso  
✅ INEP Censo Escolar 2024 — MT  
✅ Pipeline Bronze → Silver → Gold  
✅ Acessibilidade euclidiana escola ↔ setor  
✅ API MVT + GeoJSON + Acessibilidade  
✅ Frontend MapLibre GL com filtros data-driven  

🔲 **Fase 2:** DATASUS CNES saúde, OSM rede viária, acessibilidade por tempo de viagem (OSRM)  
🔲 **Fase 3:** MapBiomas cobertura do solo, ANA corpos d'água, expansão nacional

---

## Princípio Fundamental

> *"O sistema não armazena meras coordenadas cartesianas desprovidas de contexto — preserva rigorosamente a origem, temporalidade, validade geométrica e significado semântico de cada ponto de dado ingerido."*

Cada feição exibida no frontend inclui:
- **fonte_id**: identificador da fonte de dados
- **data_extracao**: quando os dados foram baixados
- **url_origem**: URL do download original
- **versao_processamento**: versão do schema de transformação
- **nota_metodologica**: avisos sobre limitações do método (ex: distância euclidiana)

---

## Licença

Dados públicos utilizados:
- IBGE: Domínio público
- INEP: Lei de Acesso à Informação (LAI)
- OpenStreetMap: ODbL 1.0

Código: MIT
