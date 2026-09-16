# ADR-003: Geração de Mosaicos Vetoriais (MVT) no PostgreSQL via ST_AsMVT

## Contexto

O frontend MapLibre GL consome dados geoespaciais via Mosaicos Vetoriais (MVT — formato Mapbox). As opções de geração:

1. **Python no servidor:** GeoPandas serializa GeoJSON → converte para protobuf MVT (mapbox-vector-tile)
2. **Tippecanoe pré-processamento:** Gera arquivos MBTiles offline, servidos por nginx
3. **PostGIS em tempo real:** `ST_AsMVT` + `ST_TileEnvelope` + índice GiST

## Decisão

**Adotamos geração 100% em tempo real pelo PostGIS (`ST_AsMVT`).**

## Justificativa

### Comparação de desempenho

| Método | P50 latência | P99 latência | CPU servidor | Atualização dados |
|--------|-------------|-------------|--------------|-------------------|
| Python MVT | ~180ms | ~800ms | Alto | Imediata |
| Tippecanoe/MBTiles | ~8ms | ~25ms | Mínimo | Rebuild completo |
| PostGIS ST_AsMVT | **~15ms** | **~80ms** | Médio | **Imediata** |

### Por que PostGIS ganha

**`ST_AsMVT` vs Python:**

O PostGIS serializa geometrias **diretamente do formato interno binário** para o protobuf MVT, sem passar por GeoJSON. Não há round-trip de serialização/desserialização em Python.

A função `ST_AsMVTGeom` simplifica automaticamente geometrias proporcionalmente ao zoom (mais simples em zoom baixo, mais detalhadas em zoom alto), usando `ST_Simplify` internamente com tolerância calibrada ao tile.

**`ST_TileEnvelope` + índice GiST:**

O envelope de tile é calculado uma vez em SQL. O predicado `ST_Intersects(geom, envelope)` ativa o índice GiST por bounding box, evitando full table scan.

```sql
-- PostGIS calcula TUDO: envelope, simplificação, clipagem, serialização protobuf
SELECT ST_AsMVT(q, 'setores_censitarios', 4096, 'geom')
FROM (
    SELECT cd_setor, nm_municipio, pop_total, dist_escola_km,
           ST_AsMVTGeom(geom, ST_TileEnvelope($1, $2, $3)) AS geom
    FROM atlas.setores_censitarios
    WHERE geom && ST_TileEnvelope($1, $2, $3)
      AND $1 >= 8  -- zoom guard
) q
```

**vs Tippecanoe:**

Tippecanoe gera tiles melhores para escalas muito baixas (mundo inteiro). Para um escopo estadual (MT), com dados que podem ser atualizados semanalmente, o rebuild completo é impraticável como fluxo operacional.

### Zero-copy no servidor Python

O handler FastAPI recebe os bytes binários do PostGIS e os retorna diretamente via `Response(content=tile_bytes, media_type="application/vnd.mapbox-vector-tile")`. O processo Python **não desserializa, não manipula e não reserializa** nenhuma geometria.

```python
tile_data: bytes = row[0]  # bytes diretos do asyncpg
return Response(content=tile_data, media_type=CONTENT_TYPE_MVT)
```

## Implicações nos Índices

Esta decisão exige índices GiST obrigatórios em todas as tabelas geoespaciais:

```sql
CREATE INDEX CONCURRENTLY ON atlas.setores_censitarios USING gist(geom);
CREATE INDEX CONCURRENTLY ON atlas.escolas USING gist(geom);
```

Sem eles, cada requisição de tile faria full table scan — latência de segundos por tile.
