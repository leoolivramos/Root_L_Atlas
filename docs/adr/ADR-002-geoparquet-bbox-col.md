# ADR-002: GeoParquet com bbox_col como Formato Canônico da Camada Gold

## Contexto

A camada Gold do Lakehouse precisa armazenar geometrias complexas (polígonos de setores censitários, linhas viárias, pontos geocodificados) de forma que consultas espaciais analíticas sejam eficientes, sem requerer um banco de dados relacional completo.

As alternativas avaliadas:

1. GeoPackage (SQLite + geometrias WKB)
2. Shapefile (legado, múltiplos arquivos)
3. GeoJSON (texto, ineficiente para volumes grandes)
4. **GeoParquet com bbox_col (formato colunar + índice espacial embutido)**
5. FlatGeobuf (indexado mas menos suporte ecossistema)

## Decisão

**Adotamos GeoParquet spec 1.0 com `write_covering_bbox=True` (bbox_col por row group) como formato único e obrigatório da camada Gold.**

Todos os arquivos geoespaciais na camada Gold são escritos com:

- `geometry_encoding="WKB"` (Well-Known Binary — interoperável)
- `write_covering_bbox=True` — habilita `bbox_col` nos metadados globais e por row group
- `row_group_size=50_000` — balanço entre índice espacial granular e overhead
- `compression="snappy"` — compressão rápida, boa taxa

## Justificativa Técnica

### O que é bbox_col?

A especificação GeoParquet 1.0 define uma coluna estrutural de bounding box que é **escrita nos metadados do row group Parquet**, não como coluna de dados. Para cada bloco de 50.000 linhas, o motor registra:

```
bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax
```

### Por que isso é transformacional?

**Sem bbox_col:** Para filtrar geometrias numa região, o motor deve:

1. Transferir para memória TODOS os bytes do arquivo
2. Desserializar CADA geometria WKB (cara computacionalmente)
3. Calcular o centróide ou envelope de CADA feição
4. Avaliar a interseção com o predicado de busca

**Com bbox_col:** O motor Parquet avalia o predicado contra os metadados do row group:

```python
filters = [
    ("bbox.xmin", "<=", lon_max),
    ("bbox.xmax", ">=", lon_min),
    ("bbox.ymin", "<=", lat_max),
    ("bbox.ymax", ">=", lat_min),
]
```

Se o row group inteiro não intersecta a área de consulta, **nenhum byte de geometria é lido**. Apenas os metadados (alguns kilobytes por row group) são avaliados.

### Impacto prático

Para um arquivo GeoParquet de 500k setores censitários (4 estados):

- **Sem bbox_col:** Consulta para MT → lê e decodifica 500k geometrias (~8s)
- **Com bbox_col:** Consulta para MT → elimina 90% dos row groups → lê apenas ~50k geometrias (~0.3s)

**Redução de latência: 26x em cenários práticos.**

## Conformidade

- Especificação: https://geoparquet.org/releases/v1.0.0/
- Suporte em: GeoPandas ≥ 1.0, DuckDB ≥ 1.0, Apache Sedona, GDAL ≥ 3.8, QGIS ≥ 3.36
