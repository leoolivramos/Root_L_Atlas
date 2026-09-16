# ADR-001: Arquitetura Lakehouse Local-First (sem cluster distribuído inicial)

## Contexto

A especificação arquitetural do RootL Atlas envolve a ingestão e processamento de múltiplos conjuntos de dados geoespaciais públicos: malha censitária IBGE (~milhares de polígonos por estado), microdados INEP, CNES/DATASUS, OSM, MapBiomas e ANA.

Um ponto de decisão crítico emergiu: **qual plataforma de processamento distribuído adotar para o pipeline de dados geoespaciais?**

As opções avaliadas foram:

1. Apache Spark (Databricks, EMR, Dataproc) + Sedona (GeoSpark)
2. DuckDB + GeoPandas em máquina única / containers dedicados
3. Dask + GeoPandas com workers distribuídos

## Decisão

**Adotamos a opção 2: DuckDB + GeoPandas em processamento de máquina única.**

O pipeline de ingestão e transformação opera exclusivamente em DuckDB (para processamento analítico Parquet) e GeoPandas (para operações geoespaciais), sem dependência de cluster distribuído na fase inicial.

## Justificativa

### 1. Volume Inicial Não Justifica Cluster

O escopo MVP limita-se ao estado de Mato Grosso:

- ~50.000 setores censitários
- ~4.000 escolas
- ~3.000 estabelecimentos de saúde
- OSM Centro-Oeste: ~300MB PBF

DuckDB processa bilhões de linhas em tabelas Parquet em uma única máquina com 16GB RAM. O volume inicial está **4 ordens de magnitude abaixo** do ponto de justificativa de cluster.

### 2. Custo Operacional

Um cluster Spark mínimo viável (3 workers, AWS EMR) custa ~$300-500/mês para cargas batch. Para o estágio de validação do modelo, este custo é proibitivo sem ROI demonstrado.

### 3. Complexidade Operacional

Spark requer gestão de cluster, configuração de YARN/Kubernetes, depuração de executors, etc. DuckDB + GeoPandas executa em qualquer máquina ou container Python com `pip install`.

### 4. GeoParquet como ponte

A adoção do formato GeoParquet (com `bbox_col` nativo) garante que os dados produzidos por DuckDB/GeoPandas são **100% compatíveis** com plataformas distribuídas futuras (Spark + Sedona, Trino + geospatial). A migração futura é uma mudança de engine de leitura, não de formato de dados.
