CREATE OR REPLACE FUNCTION atlas.get_mvt_malha_viaria(p_z integer, p_x integer, p_y integer)
RETURNS bytea
LANGUAGE plpgsql
STABLE PARALLEL SAFE
AS $$
DECLARE
    v_tile BYTEA;
BEGIN
    IF p_z < 5 THEN
        RETURN NULL;
    END IF;

    SELECT ST_AsMVT(q.*, 'malha_viaria', 4096, 'geom_mvt')
    INTO v_tile
    FROM (
        SELECT
            v.osm_id,
            v.highway,
            v.name,
            v.oneway,
            v.maxspeed,
            v.surface,
            ST_AsMVTGeom(
                ST_Transform(v.geom, 3857),
                ST_TileEnvelope(p_z, p_x, p_y),
                4096, 64, TRUE
            ) AS geom_mvt
        FROM atlas.malha_viaria_osm v
        WHERE v.geom && ST_Transform(ST_TileEnvelope(p_z, p_x, p_y, margin => 0.03125), 4326)
          AND (
              -- Zoom 11+: todas as vias
              p_z >= 11
              -- Zoom 8 a 10: rodovias, arteriais e coletoras (secundárias e terciárias)
              OR (p_z >= 8 AND v.highway IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'))
              -- Zoom 5 a 7: rodovias principais federais e estaduais
              OR (p_z >= 5 AND v.highway IN ('motorway', 'trunk', 'primary', 'secondary', 'motorway_link', 'trunk_link', 'primary_link'))
          )
    ) q
    WHERE q.geom_mvt IS NOT NULL;

    RETURN COALESCE(v_tile, ''::BYTEA);
END;
$$;
