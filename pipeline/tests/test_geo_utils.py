"""
pipeline/tests/test_geo_utils.py
"""
import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely import make_valid

from transforms.geo_utils import (
    reproject_to_wgs84,
    validate_and_fix_geometries,
    validate_coordinates_in_bbox,
    write_geoparquet_with_bbox,
    read_geoparquet,
    MT_BBOX,
    EPSG_WGS84,
    EPSG_SIRGAS2000,
)


class TestReproject:
    def test_already_wgs84(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(-55.9, -12.6)],
            crs="EPSG:4326",
        )
        result = reproject_to_wgs84(gdf)
        assert result.crs.to_epsg() == 4326

    def test_from_sirgas2000(self):
        # SIRGAS 2000 ≈ WGS84 mas deve aceitar a reprojeção sem erro
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(-55.9, -12.6)],
            crs=f"EPSG:{EPSG_SIRGAS2000}",
        )
        result = reproject_to_wgs84(gdf, source_epsg=EPSG_SIRGAS2000)
        assert result.crs.to_epsg() == EPSG_WGS84

    def test_no_crs_assumes_sirgas(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(-55.9, -12.6)],
        )
        # Deve assumir o CRS padrão sem lançar exceção
        result = reproject_to_wgs84(gdf)
        assert result.crs is not None


class TestValidateGeometries:
    def test_valid_polygon(self):
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[poly], crs="EPSG:4326")
        result, report = validate_and_fix_geometries(gdf)
        assert len(result) == 1
        assert report.empty

    def test_invalid_geometry_is_fixed(self):
        # Bowtie polygon (inválido)
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bowtie], crs="EPSG:4326")
        result, report = validate_and_fix_geometries(gdf)
        assert len(result) == 1
        assert result.geometry.iloc[0].is_valid
        assert len(report) == 1
        assert report["tipo"].iloc[0] == "geometria_invalida"

    def test_none_geometry_removed(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1, 2]},
            geometry=[Point(0, 0), None],
            crs="EPSG:4326",
        )
        result, report = validate_and_fix_geometries(gdf)
        assert len(result) == 1
        assert len(report) == 1


class TestBboxValidation:
    def test_point_inside_mt(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(-55.9, -12.6)],
            crs="EPSG:4326",
        )
        result, report = validate_coordinates_in_bbox(gdf, bbox=MT_BBOX)
        assert len(result) == 1
        assert report.empty

    def test_point_outside_mt_is_flagged(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1, 2]},
            geometry=[Point(-55.9, -12.6), Point(10.0, 50.0)],  # Europa
            crs="EPSG:4326",
        )
        result, report = validate_coordinates_in_bbox(gdf, bbox=MT_BBOX)
        assert len(result) == 1
        assert len(report) == 1

    def test_strict_mode_raises(self):
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(10.0, 50.0)],  # Fora do MT
            crs="EPSG:4326",
        )
        with pytest.raises(ValueError, match="Pipeline bloqueado"):
            validate_coordinates_in_bbox(gdf, bbox=MT_BBOX, strict=True)


class TestGeoParquet:
    def test_write_and_read_with_bbox(self, tmp_path):
        gdf = gpd.GeoDataFrame(
            {
                "id": [1, 2, 3],
                "name": ["A", "B", "C"],
            },
            geometry=[
                Polygon([(-56, -13), (-55, -13), (-55, -12), (-56, -12)]),
                Polygon([(-57, -14), (-56, -14), (-56, -13), (-57, -13)]),
                Polygon([(-55, -12), (-54, -12), (-54, -11), (-55, -11)]),
            ],
            crs="EPSG:4326",
        )
        output = tmp_path / "test.parquet"
        write_geoparquet_with_bbox(gdf, output)
        assert output.exists()
        assert output.stat().st_size > 0

        # Leitura com filtro bbox
        loaded = read_geoparquet(output, bbox=(-57.5, -14.5, -55.5, -12.5))
        assert len(loaded) >= 1

    def test_requires_wgs84(self, tmp_path):
        gdf = gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[Point(500000, 7500000)],
            crs="EPSG:31982",  # UTM
        )
        with pytest.raises(ValueError, match="EPSG:4326"):
            write_geoparquet_with_bbox(gdf, tmp_path / "out.parquet")
