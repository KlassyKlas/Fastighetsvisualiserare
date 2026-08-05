import pytest
from fastapi import HTTPException
from geoalchemy2.shape import to_shape

from app.services.geo import geojson_to_element, parse_bbox, parse_geojson_column

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[18.0, 59.0], [18.1, 59.0], [18.1, 59.1], [18.0, 59.1], [18.0, 59.0]]],
}


class TestGeojsonToElement:
    def test_polygon_promoted_to_multipolygon_with_srid(self):
        element = geojson_to_element(POLYGON)
        assert element.srid == 4326
        assert to_shape(element).geom_type == "MultiPolygon"

    def test_point_keeps_type(self):
        element = geojson_to_element({"type": "Point", "coordinates": [18.0, 59.0]})
        assert to_shape(element).geom_type == "Point"
        assert element.srid == 4326

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            geojson_to_element({"type": "Nonsens", "coordinates": []})
        with pytest.raises(ValueError):
            geojson_to_element({})

    def test_z_coordinates_are_stripped(self):
        # Kolumnernas typmod är 2D — PostGIS avvisar annars hela skrivningen
        element = geojson_to_element({"type": "Point", "coordinates": [18.0, 59.0, 12.5]})
        assert to_shape(element).has_z is False

    def test_allowed_types_rejects_wrong_geometry(self):
        with pytest.raises(ValueError, match="Geometritypen Point"):
            geojson_to_element(
                {"type": "Point", "coordinates": [18.0, 59.0]},
                allowed_types=("MultiPolygon",),
            )

    def test_allowed_types_accepts_promoted_polygon(self):
        element = geojson_to_element(POLYGON, allowed_types=("MultiPolygon",))
        assert to_shape(element).geom_type == "MultiPolygon"


class TestParseBbox:
    def test_valid(self):
        assert parse_bbox("17.5,59.0,18.5,59.7") == (17.5, 59.0, 18.5, 59.7)

    def test_wrong_arity_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            parse_bbox("17.5,59.0,18.5")
        assert exc.value.status_code == 400

    def test_non_numeric_raises_400(self):
        with pytest.raises(HTTPException):
            parse_bbox("a,b,c,d")

    def test_out_of_range_raises_400(self):
        with pytest.raises(HTTPException):
            parse_bbox("200,59,201,60")


class TestParseGeojsonColumn:
    def test_none_passthrough(self):
        assert parse_geojson_column(None) is None

    def test_parses_json(self):
        assert parse_geojson_column('{"type": "Point", "coordinates": [1, 2]}') == {
            "type": "Point",
            "coordinates": [1, 2],
        }
