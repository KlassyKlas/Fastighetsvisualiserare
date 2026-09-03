"""Filtolkningen är ren logik — här låses rubrikalias, talformat,
geometrihantering och felrapportering fast utan databas."""

import json
import math
from pathlib import Path

import asyncpg
import pytest
from shapely.geometry import Point, shape

from app.domain import PropertyType
from app.schemas import PropertyCreate
from app.services.property_import import (
    COLUMN_ALIASES,
    M_PER_DEG_LAT,
    ImportFormatError,
    SourceRow,
    map_headers,
    normalize_header,
    parse_decimal,
    parse_geometry,
    parse_int,
    parse_property_type,
    parse_rows,
    read_csv,
    read_file,
    read_geojson,
    square_around_point,
)

EXAMPLE_CSV = Path(__file__).parents[2] / "scripts" / "examples" / "fastigheter_exempel.csv"

WKT_POLYGON = "POLYGON((18.06 59.33, 18.07 59.33, 18.07 59.34, 18.06 59.34, 18.06 59.33))"
# Självskärande "fluga" — topologiskt ogiltig
BOWTIE_POLYGON = "POLYGON((18 59, 18.1 59.1, 18.1 59, 18 59.1, 18 59))"
GEOJSON_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[18.06, 59.33], [18.07, 59.33], [18.07, 59.34], [18.06, 59.34], [18.06, 59.33]]
    ],
}


def _row(**columns: object) -> dict[str, object]:
    return {"Beteckning": "Norrmalm 1:5", **columns}


class TestNormalizeHeader:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Taxeringsvärde (kr)", "taxeringsvärde"),
            ("Org.nr", "orgnr"),
            ("  Ägare ", "ägare"),
            ("owner_name", "ownername"),
            ("Lagfaren ägare", "lagfarenägare"),
            ("Bygg-år", "byggår"),
            ("Area (m²)", "area"),
            ("\ufeffBeteckning", "beteckning"),
        ],
    )
    def test_examples(self, raw, expected):
        assert normalize_header(raw) == expected


class TestMapHeaders:
    def test_swedish_aliases(self):
        mapping = map_headers(
            ["Fastighetsbeteckning", "Kommun", "Taxeringsvärde (kr)", "Typ", "Org.nr", "Anteckning"]
        )
        assert mapping == {
            "Fastighetsbeteckning": "designation",
            "Kommun": "municipality",
            "Taxeringsvärde (kr)": "assessed_value_sek",
            "Typ": "property_type",
            "Org.nr": "owner_org_number",
        }

    def test_geometry_aliases(self):
        assert map_headers(["WKT", "X", "Y"]) == {
            "WKT": "geometry",
            "X": "longitude",
            "Y": "latitude",
        }
        assert map_headers(["Öst", "Nord"]) == {"Öst": "longitude", "Nord": "latitude"}

    def test_field_names_always_accepted(self):
        fields = [name for name in PropertyCreate.model_fields if name != "metadata_json"]
        assert map_headers(fields) == {name: name for name in fields}

    def test_every_property_create_field_has_aliases(self):
        expected = set(PropertyCreate.model_fields) - {"metadata_json"}
        assert expected <= set(COLUMN_ALIASES)

    def test_conflicting_columns_rejected(self):
        with pytest.raises(ImportFormatError, match="betyder båda owner_name"):
            map_headers(["Ägare", "owner_name"])


class TestNumbers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1 234 567 kr", 1_234_567.0),
            ("1\xa0234\xa0567", 1_234_567.0),
            ("1.234.567", 1_234_567.0),
            ("12,5", 12.5),
            ("12.5", 12.5),
            ("1.234.567,50", 1_234_567.5),
            ("1,234,567.89", 1_234_567.89),
            ("4 250,5 m²", 4250.5),
            ("SEK 100", 100.0),
            ("-3,5", -3.5),
            ("+12", 12.0),
            # Excel-stavningar av enheter: siffra, snedstreck, ",-"/":-", procent
            ("12,5 m2", 12.5),
            ("12,5 kvm", 12.5),
            ("1 250 000 kr/år", 1_250_000.0),
            ("1 250 000,-", 1_250_000.0),
            ("1.250.000:-", 1_250_000.0),
            ("10 %", 10.0),
            # Exponent är inte en enhet
            ("1e5", 100_000.0),
            ("1,25E+08", 125_000_000.0),
            ("", None),
            ("   ", None),
            (None, None),
            (42, 42.0),
            (17.97, 17.97),
        ],
    )
    def test_parse_decimal(self, raw, expected):
        assert parse_decimal(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "abc",
            "kr",
            "-",
            "1-2",
            "nan",
            "inf",
            True,
            # Tusentalsavgränsare utan tresiffriga grupper är ett skrivfel, inte 125
            "12..5",
            "1,2,3.4",
            "1.2,3.4",
            ",234,567",
        ],
    )
    def test_parse_decimal_rejects_non_numbers(self, raw):
        with pytest.raises(ValueError, match="inte ett tal"):
            parse_decimal(raw)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1 250 000", 1_250_000),
            ("125 000 000 kr", 125_000_000),
            ("12,0", 12),
            ("1962", 1962),
            ("", None),
            (1975, 1975),
            (1975.0, 1975),
        ],
    )
    def test_parse_int(self, raw, expected):
        assert parse_int(raw) == expected

    @pytest.mark.parametrize("raw", ["12,5", "1 234,56 kr", 12.5])
    def test_parse_int_rejects_decimals_instead_of_rounding(self, raw):
        with pytest.raises(ValueError, match="inte ett heltal"):
            parse_int(raw)


class TestPropertyType:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("kontor", PropertyType.KONTOR),
            ("Kontor", PropertyType.KONTOR),
            ("BOSTAD", PropertyType.BOSTAD),
            (" villa ", PropertyType.VILLA),
            ("", None),
            (None, None),
        ],
    )
    def test_case_insensitive(self, raw, expected):
        assert parse_property_type(raw) == expected

    def test_unknown_value_lists_valid_values(self):
        with pytest.raises(ValueError, match="okänd fastighetstyp 'lager'") as exc_info:
            parse_property_type("lager")
        for property_type in PropertyType:
            assert property_type.value in str(exc_info.value)


class TestParseGeometry:
    def test_wkt_polygon(self):
        geom = parse_geometry(WKT_POLYGON)
        assert geom.geom_type == "Polygon"
        assert geom.bounds == (18.06, 59.33, 18.07, 59.34)

    def test_wkt_multipolygon(self):
        geom = parse_geometry(
            "MULTIPOLYGON(((18.06 59.33, 18.07 59.33, 18.07 59.34, 18.06 59.33)))"
        )
        assert geom.geom_type == "MultiPolygon"

    def test_geojson_string_and_dict(self):
        expected = shape(GEOJSON_POLYGON)
        assert parse_geometry(json.dumps(GEOJSON_POLYGON)).equals(expected)
        assert parse_geometry(GEOJSON_POLYGON).equals(expected)

    @pytest.mark.parametrize("raw", ["", "   ", None])
    def test_empty_is_none(self, raw):
        assert parse_geometry(raw) is None

    def test_z_coordinates_are_stripped(self):
        geom = parse_geometry(
            "POLYGON Z((18.06 59.33 5, 18.07 59.33 5, 18.07 59.34 5, 18.06 59.33 5))"
        )
        assert geom.has_z is False

    @pytest.mark.parametrize(
        "raw", ["POLYGON((nonsens", '{"type": "Nonsens"}', "{}", {"type": "Polygon"}]
    )
    def test_invalid_raises_value_error(self, raw):
        with pytest.raises(ValueError, match="ogiltig geometri"):
            parse_geometry(raw)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # De vanligaste WKT-felen förklaras på svenska, inte med GEOS text
            ("POLYGON((18 59, 18.1 59, 18.1 59.1))", "ringen är inte sluten"),
            ("POLYGON((18 59, 18.1 59))", "ringen är inte sluten"),
            (
                {"type": "Polygon", "coordinates": [[[18, 59], [18.1, 59]]]},
                "för få punkter i ringen",
            ),
            ("POLYGN((1 2, 3 4, 5 6, 1 2))", "okänd geometrityp 'POLYGN'"),
            ("Drottninggatan 10", "okänd geometrityp 'DROTTNINGGATAN'"),
            ('{"type": "Nonsens"}', "okänd geometrityp 'nonsens'"),
            ("POLYGON((a b, c d))", "väntade ett tal men fann 'a'"),
            ("POLYGON((18 59, ", "slutar för tidigt"),
            (f"{WKT_POLYGON} extra", "text efter geometrins slut"),
            ({"type": "Polygon"}, "GeoJSON-geometrin saknar 'coordinates'"),
            ("SRID=999999;POINT(1 2)", "okänt SRID 999999 i EWKT-prefixet"),
        ],
    )
    def test_parse_errors_in_swedish(self, raw, expected):
        with pytest.raises(ValueError, match="ogiltig geometri") as exc_info:
            parse_geometry(raw)
        message = str(exc_info.value)
        assert expected in message
        assert "Exception" not in message

    def test_sweref99_tm_transformed_to_wgs84(self):
        geom = parse_geometry("POINT(674000 6580000)", srid=3006)
        assert geom.x == pytest.approx(18.06, abs=0.05)
        assert geom.y == pytest.approx(59.33, abs=0.05)

    def test_ewkt_prefix_sets_the_srid(self):
        # PostGIS ST_AsEWKT: prefixets SRID gäller för värdet, även om filen är i WGS84
        geom = parse_geometry("SRID=3006;POINT(674000 6580000)")
        assert geom.x == pytest.approx(18.06, abs=0.05)
        assert geom.y == pytest.approx(59.33, abs=0.05)
        assert parse_geometry(f"srid=4326;{WKT_POLYGON}", srid=3006).bounds == (
            18.06,
            59.33,
            18.07,
            59.34,
        )

    def test_coordinates_outside_wgs84_hint_at_srid(self):
        with pytest.raises(ValueError, match="--srid") as exc_info:
            parse_geometry("POINT(674000 6580000)")
        # Koordinaterna skrivs som användaren känner igen dem — inte 6.58e+06
        assert "(674000, 6580000)" in str(exc_info.value)

    def test_self_intersecting_polygon_is_rejected(self):
        with pytest.raises(ValueError, match="ogiltig polygon") as exc_info:
            parse_geometry(BOWTIE_POLYGON)
        assert "skär sig själv vid (18.05, 59.05)" in str(exc_info.value)

    def test_hole_outside_shell_is_rejected(self):
        wkt = (
            "POLYGON((18 59, 18.1 59, 18.1 59.1, 18 59.1, 18 59), "
            "(18.2 59.2, 18.3 59.2, 18.3 59.3, 18.2 59.3, 18.2 59.2))"
        )
        with pytest.raises(ValueError, match="hål ligger utanför ytterringen"):
            parse_geometry(wkt)


class TestSquareAroundPoint:
    def test_side_is_twice_the_half_size_in_meters(self):
        square = square_around_point(18.0, 59.33, 25)
        minx, miny, maxx, maxy = square.bounds
        assert (maxy - miny) * M_PER_DEG_LAT == pytest.approx(50)
        width_m = (maxx - minx) * M_PER_DEG_LAT * math.cos(math.radians(59.33))
        assert width_m == pytest.approx(50)
        assert square.contains(Point(18.0, 59.33))


class TestParseRows:
    def test_full_row_with_wkt(self):
        result = parse_rows(
            [
                {
                    "Beteckning": "Norrmalm 1:5",
                    "Kommun": "Stockholm",
                    "Ägare": "Bolaget AB",
                    "Org.nr": "556000-0001",
                    "Taxeringsvärde (kr)": "125 000 000",
                    "Area (m²)": "4 250,5",
                    "Typ": "Kontor",
                    "Byggår": "1962",
                    "Geometri": WKT_POLYGON,
                }
            ]
        )
        assert result.problems == []
        assert result.rows_read == 1
        assert result.without_geometry == 0
        [item] = result.items
        assert item.designation == "Norrmalm 1:5"
        assert item.municipality == "Stockholm"
        assert item.owner_name == "Bolaget AB"
        assert item.owner_org_number == "556000-0001"
        assert item.assessed_value_sek == 125_000_000
        assert item.area_sqm == 4250.5
        assert item.property_type == PropertyType.KONTOR
        assert item.building_year == 1962
        assert shape(item.geometry).equals(shape(GEOJSON_POLYGON))
        assert result.column_mapping["Taxeringsvärde (kr)"] == "assessed_value_sek"
        assert result.extra_columns == []

    def test_geojson_geometry_dict(self):
        result = parse_rows([_row(geometry=GEOJSON_POLYGON)])
        assert shape(result.items[0].geometry).equals(shape(GEOJSON_POLYGON))

    def test_lng_lat_in_sweref99_tm_with_buffer(self):
        result = parse_rows([_row(x="674000", y="6580000")], srid=3006, point_buffer_m=25)
        assert result.problems == []
        [item] = result.items
        centroid = shape(item.geometry).centroid
        assert centroid.x == pytest.approx(18.06, abs=0.05)
        assert centroid.y == pytest.approx(59.33, abs=0.05)
        assert result.without_geometry == 0

    def test_polygon_in_sweref99_tm(self):
        wkt = (
            "POLYGON((674000 6580000, 674100 6580000, 674100 6580100, "
            "674000 6580100, 674000 6580000))"
        )
        result = parse_rows([_row(Geometri=wkt)], srid=3006)
        minx, miny, maxx, maxy = shape(result.items[0].geometry).bounds
        assert 18.0 < minx < maxx < 18.1
        assert 59.3 < miny < maxy < 59.4

    def test_point_without_buffer_gives_no_geometry(self):
        result = parse_rows([_row(Lng="17,9710", Lat="59,3615")])
        assert result.problems == []
        assert result.items[0].geometry is None
        assert result.without_geometry == 1
        assert result.points_without_buffer == 1

    def test_point_with_buffer_gives_square(self):
        result = parse_rows([_row(Lng="17,9710", Lat="59,3615")], point_buffer_m=25)
        geom = shape(result.items[0].geometry)
        assert geom.geom_type == "Polygon"
        assert geom.contains(Point(17.971, 59.3615))
        assert result.without_geometry == 0
        assert result.points_without_buffer == 0

    def test_only_one_coordinate_is_a_problem(self):
        result = parse_rows([_row(Lng="17,9710", Lat="")])
        assert result.items == []
        [problem] = result.problems
        assert problem.message == "Lng: både longitud och latitud krävs"

    def test_row_without_any_geometry(self):
        result = parse_rows([_row(Kommun="Stockholm")])
        assert result.items[0].geometry is None
        assert result.without_geometry == 1
        assert result.points_without_buffer == 0

    def test_geometry_column_wins_over_lng_lat(self):
        result = parse_rows([_row(Geometri=WKT_POLYGON, Lng="10", Lat="60")], point_buffer_m=25)
        assert shape(result.items[0].geometry).bounds == (18.06, 59.33, 18.07, 59.34)

    def test_non_polygon_geometry_is_a_problem(self):
        result = parse_rows([_row(Geometri="LINESTRING(18 59, 18.1 59.1)")])
        [problem] = result.problems
        assert problem.message.startswith("Geometri: geometrin måste vara POLYGON")

    def test_invalid_wkt_is_a_problem_not_a_crash(self):
        result = parse_rows([_row(Geometri="POLYGON((trasig")])
        [problem] = result.problems
        assert problem.message.startswith("Geometri: ogiltig geometri")

    def test_invalid_polygon_is_a_problem(self):
        result = parse_rows([_row(Geometri=BOWTIE_POLYGON)])
        assert result.items == []
        [problem] = result.problems
        assert problem.message.startswith("Geometri: ogiltig polygon: geometrin skär sig själv")

    def test_unknown_srid(self):
        with pytest.raises(ImportFormatError, match="Okänt SRID 999999"):
            parse_rows([_row()], srid=999999)

    def test_invalid_buffer(self):
        with pytest.raises(ImportFormatError, match="point_buffer_m"):
            parse_rows([_row()], point_buffer_m=0)

    def test_duplicates_first_wins(self):
        result = parse_rows([_row(Kommun="Stockholm"), _row(Kommun="Solna")])
        assert [item.municipality for item in result.items] == ["Stockholm"]
        [problem] = result.problems
        assert problem.line == 3
        assert problem.designation == "Norrmalm 1:5"
        assert "dubblett" in problem.message
        assert "rad 2" in problem.message

    def test_extra_columns_to_metadata(self):
        rows = [_row(Anteckning="Ombyggd 2018", Tomt="")]
        result = parse_rows(rows)
        assert result.items[0].metadata_json == {"Anteckning": "Ombyggd 2018"}
        assert result.extra_columns == ["Anteckning", "Tomt"]

        assert parse_rows(rows, extra_to_metadata=False).items[0].metadata_json == {}

    def test_empty_header_is_ignored(self):
        # Avslutande ';' i rubrikraden (vanligt från Excel) ger en tom rubrik
        result = parse_rows([_row(**{"": "skräp", "Anteckning": "a", " ": "x"})])
        assert result.items[0].metadata_json == {"Anteckning": "a"}
        assert result.extra_columns == ["Anteckning"]

    def test_row_problems_carry_line_and_header(self):
        rows = [
            _row(**{"Taxeringsvärde (kr)": "12,5"}),
            _row(Beteckning="Vasastan 2:8", Typ="lager"),
            _row(Beteckning="Bra 1:1", Typ="villa"),
        ]
        result = parse_rows(rows)
        assert [item.designation for item in result.items] == ["Bra 1:1"]
        assert result.rows_read == 3
        assert result.failed_lines == 2
        messages = {(p.line, p.designation): p.message for p in result.problems}
        assert messages[(2, "Norrmalm 1:5")] == "Taxeringsvärde (kr): '12,5' är inte ett heltal"
        assert messages[(3, "Vasastan 2:8")].startswith("Typ: okänd fastighetstyp 'lager'")

    def test_validation_error_becomes_row_problem_in_swedish(self):
        result = parse_rows([_row(Byggår="999", Area="-5"), _row(Byggår="2300")])
        assert result.items == []
        messages = sorted((problem.line, problem.message) for problem in result.problems)
        assert messages == [
            (2, "Area: måste vara minst 0"),
            (2, "Byggår: måste vara minst 1000"),
            (3, "Byggår: får vara högst 2200"),
        ]

    def test_missing_designation_value(self):
        result = parse_rows([_row(Beteckning="  ", Kommun="Stockholm")])
        [problem] = result.problems
        assert problem.designation is None
        assert problem.message == "saknar fastighetsbeteckning"

    def test_missing_designation_column(self):
        rows = [{"Kommun": "Stockholm", "Ägare": "X"}, {"Kommun": "Solna", "Ägare": "Y"}]
        with pytest.raises(ImportFormatError, match="Kolumner i filen: Kommun, Ägare"):
            parse_rows(rows)

    def test_rows_without_designation_key_are_row_problems(self):
        # GeoJSON-features kan sakna enstaka attribut — bara den raden ska falla
        rows = [
            {"beteckning": "C 1:1", "geometry": None},
            {"ägare": "X", "geometry": None},
            {"beteckning": "C 1:2", "geometry": None},
        ]
        result = parse_rows(rows, first_line=1)
        assert [item.designation for item in result.items] == ["C 1:1", "C 1:2"]
        [problem] = result.problems
        assert (problem.line, problem.message) == (2, "saknar fastighetsbeteckning")

    def test_designation_key_may_be_missing_in_first_row(self):
        result = parse_rows([{"ägare": "X"}, {"beteckning": "C 1:2"}], first_line=1)
        assert [item.designation for item in result.items] == ["C 1:2"]
        assert [problem.line for problem in result.problems] == [1]

    def test_blank_rows_skipped_but_line_numbers_kept(self):
        result = parse_rows([_row(), {"Beteckning": "", "Kommun": ""}, _row()])
        assert result.rows_read == 2
        assert [problem.line for problem in result.problems] == [4]

    def test_source_rows_keep_their_own_line_numbers(self):
        rows = [SourceRow(2, _row()), SourceRow(7, _row(Typ="lager"))]
        result = parse_rows(rows)
        assert [(p.line, p.message[:4]) for p in result.problems] == [(7, "Typ:")]

    def test_first_line_for_geojson_features(self):
        result = parse_rows([_row(Typ="lager")], first_line=1)
        assert result.problems[0].line == 1


class TestReaders:
    def test_csv_semicolon_decimal_comma(self, tmp_path):
        path = tmp_path / "fastigheter.csv"
        path.write_text(
            "Beteckning;Ägare;Area (m²)\nNorrmalm 1:5;Bolaget AB;4 250,5\n", encoding="utf-8"
        )
        rows = read_csv(path)
        assert rows == [
            (2, {"Beteckning": "Norrmalm 1:5", "Ägare": "Bolaget AB", "Area (m²)": "4 250,5"})
        ]
        [item] = parse_rows(rows).items
        assert item.owner_name == "Bolaget AB"
        assert item.area_sqm == 4250.5

    def test_csv_with_bom(self, tmp_path):
        path = tmp_path / "bom.csv"
        path.write_text("Beteckning;Kommun\nA 1:1;Solna\n", encoding="utf-8-sig")
        assert read_csv(path) == [(2, {"Beteckning": "A 1:1", "Kommun": "Solna"})]

    def test_csv_cp1252_fallback(self, tmp_path):
        path = tmp_path / "excel.csv"
        path.write_bytes("Beteckning;Ägare\nSödermalm 1:1;Åsa Öberg\n".encode("cp1252"))
        assert read_csv(path) == [(2, {"Beteckning": "Södermalm 1:1", "Ägare": "Åsa Öberg"})]

    def test_csv_utf16_with_bom(self, tmp_path):
        # Excels "Unicode-text": UTF-16 med BOM, tabavgränsad
        path = tmp_path / "unicode.txt"
        path.write_bytes("Beteckning\tÄgare\nSödermalm 1:1\tÅsa Öberg\n".encode("utf-16"))
        assert read_csv(path) == [(2, {"Beteckning": "Södermalm 1:1", "Ägare": "Åsa Öberg"})]

    def test_csv_trailing_empty_header(self, tmp_path):
        path = tmp_path / "avslutande.csv"
        path.write_text("Beteckning;Kommun;\nA 1:1;Solna;x\n", encoding="utf-8")
        rows = read_csv(path)
        assert rows == [(2, {"Beteckning": "A 1:1", "Kommun": "Solna", "": "x"})]
        result = parse_rows(rows)
        assert result.items[0].metadata_json == {}
        assert result.extra_columns == []

    def test_csv_duplicate_headers_rejected(self, tmp_path):
        path = tmp_path / "dubbel.csv"
        path.write_text("Beteckning;Kommun;Kommun \nA 1:1;Sol;Sun\n", encoding="utf-8")
        with pytest.raises(ImportFormatError, match="dubblerade rubriker \\('Kommun'\\)"):
            read_csv(path)

    def test_csv_comma_with_quoted_wkt(self, tmp_path):
        path = tmp_path / "komma.csv"
        path.write_text(f'Beteckning,Geometri\n"Norrmalm 1:5","{WKT_POLYGON}"\n', encoding="utf-8")
        assert read_csv(path) == [(2, {"Beteckning": "Norrmalm 1:5", "Geometri": WKT_POLYGON})]

    def test_csv_tab(self, tmp_path):
        path = tmp_path / "tab.csv"
        path.write_text("Beteckning\tKommun\nA 1:1\tStockholm\n", encoding="utf-8")
        assert read_csv(path) == [(2, {"Beteckning": "A 1:1", "Kommun": "Stockholm"})]

    def test_csv_single_column_falls_back_to_semicolon(self, tmp_path):
        path = tmp_path / "en.csv"
        path.write_text("Beteckning\nA 1:1\n", encoding="utf-8")
        assert read_csv(path) == [(2, {"Beteckning": "A 1:1"})]

    @pytest.mark.parametrize(
        ("text", "second_header"),
        [
            # Rubrik med kommatecken, lika många som i varje datarad — csv.Sniffer
            # hade valt ',' här
            ("Beteckning;Adress, ort\nA 1:1;Gatan 1, Sthlm\nB 1:1;Gatan 2, Sthlm\n", "Adress, ort"),
            ("Beteckning;Area (m², total)\nA 1:1;12,5\nB 1:1;13,5\n", "Area (m², total)"),
            # Citerad rubrik med kommatecken i en kommaseparerad fil
            ('"Beteckning","Adress, ort"\n"A 1:1","x"\n"B 1:1","y"\n', "Adress, ort"),
            # Semikolon i rubriken, citerat, i en kommaseparerad fil
            ('Beteckning,"Anm; övrigt"\nA 1:1,x\nB 1:1,y\n', "Anm; övrigt"),
        ],
    )
    def test_csv_delimiter_is_decided_by_the_header_row(self, tmp_path, text, second_header):
        path = tmp_path / "rubrik.csv"
        path.write_text(text, encoding="utf-8")
        rows = read_csv(path)
        assert [list(row.values) for row in rows] == [["Beteckning", second_header]] * 2
        assert [row.values["Beteckning"] for row in rows] == ["A 1:1", "B 1:1"]

    def test_csv_headers_and_values_are_trimmed(self, tmp_path):
        # ", "-avgränsat: mellanslaget efter kommatecknet ska inte hamna i
        # rubriken (metadata_json-nyckel) eller i värdet
        path = tmp_path / "mellanslag.csv"
        path.write_text("Beteckning, Kommun , Anteckning\nA 1:1, Solna, x\n", encoding="utf-8")
        rows = read_csv(path)
        assert rows == [(2, {"Beteckning": "A 1:1", "Kommun": "Solna", "Anteckning": "x"})]
        result = parse_rows(rows)
        assert result.column_mapping == {"Beteckning": "designation", "Kommun": "municipality"}
        assert result.extra_columns == ["Anteckning"]
        assert result.items[0].metadata_json == {"Anteckning": "x"}

    def test_csv_line_numbers_survive_blank_lines_and_quoted_newlines(self, tmp_path):
        path = tmp_path / "rader.csv"
        path.write_text(
            "Beteckning;Adress;Typ\r\n"
            "A 1:1;;villa\r\n"
            "\r\n"  # rad 3: helt tom — DictReader hoppar över den tyst
            'B 1:1;"Gatan 1\r\nBox 2";villa\r\n'  # rad 4–5: citerad radbrytning
            ";;\r\n"  # rad 6: bara avgränsare
            "C 1:1;;lager\r\n",  # rad 7
            encoding="utf-8",
        )
        rows = read_csv(path)
        assert [(line, values["Beteckning"]) for line, values in rows] == [
            (2, "A 1:1"),
            (4, "B 1:1"),
            (6, ""),
            (7, "C 1:1"),
        ]
        assert rows[1].values["Adress"] == "Gatan 1\r\nBox 2"
        result = parse_rows(rows)
        assert result.rows_read == 3
        assert [(p.line, p.designation) for p in result.problems] == [(7, "C 1:1")]

    def test_csv_field_larger_than_the_csv_module_default(self, tmp_path):
        # En detaljerad polygon ur QGIS överskrider lätt csv-modulens 128 kB-gräns
        big_polygon = Point(18.06, 59.33).buffer(0.01, quad_segs=1500).wkt
        assert len(big_polygon) > 131_072
        path = tmp_path / "stor.csv"
        path.write_text(f"Beteckning;Geometri\nA 1:1;{big_polygon}\n", encoding="utf-8")
        result = parse_rows(read_csv(path))
        assert result.problems == []
        assert shape(result.items[0].geometry).is_valid

    def test_csv_empty_file(self, tmp_path):
        path = tmp_path / "tom.csv"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ImportFormatError, match="tom"):
            read_csv(path)

    def test_geojson_feature_collection(self, tmp_path):
        collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "beteckning": "Norrmalm 1:5",
                        "ägare": "Bolaget AB",
                        "taxeringsvärde": 125000000,
                        "anteckning": "från QGIS",
                    },
                    "geometry": GEOJSON_POLYGON,
                },
                {
                    "type": "Feature",
                    "properties": {"beteckning": "Punkt 1:1"},
                    "geometry": {"type": "Point", "coordinates": [17.971, 59.3615]},
                },
            ],
        }
        path = tmp_path / "fastigheter.geojson"
        path.write_text(json.dumps(collection), encoding="utf-8")

        rows = read_geojson(path)
        assert [row.line for row in rows] == [1, 2]
        assert rows[0].values["geometry"] == GEOJSON_POLYGON
        result = parse_rows(rows, point_buffer_m=25)
        assert result.problems == []
        first, second = result.items
        assert first.owner_name == "Bolaget AB"
        assert first.assessed_value_sek == 125_000_000
        assert first.metadata_json == {"anteckning": "från QGIS"}
        assert shape(first.geometry).equals(shape(GEOJSON_POLYGON))
        assert shape(second.geometry).geom_type == "Polygon"

    def test_geojson_cp1252_fallback(self, tmp_path):
        collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"beteckning": "Åkersberga 1:1"},
                    "geometry": None,
                }
            ],
        }
        path = tmp_path / "cp.geojson"
        path.write_bytes(json.dumps(collection, ensure_ascii=False).encode("cp1252"))
        assert read_geojson(path)[0].values["beteckning"] == "Åkersberga 1:1"

    def test_geojson_rejects_other_json(self, tmp_path):
        path = tmp_path / "annat.json"
        path.write_text('{"foo": 1}', encoding="utf-8")
        with pytest.raises(ImportFormatError, match="FeatureCollection"):
            read_geojson(path)
        path.write_text("[1,", encoding="utf-8")
        with pytest.raises(ImportFormatError, match="ogiltig JSON"):
            read_geojson(path)

    def test_read_file_dispatches_on_suffix(self, tmp_path):
        geojson = tmp_path / "f.GeoJSON"
        geojson.write_text(
            json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8"
        )
        assert read_file(geojson) == []
        csv_path = tmp_path / "f.txt"
        csv_path.write_text("Beteckning\nA 1:1\n", encoding="utf-8")
        assert read_file(csv_path) == [(2, {"Beteckning": "A 1:1"})]


class TestExampleFile:
    def test_parses_without_problems(self):
        result = parse_rows(read_file(EXAMPLE_CSV))
        assert result.problems == []
        assert len(result.items) == 3
        assert result.without_geometry == 1
        assert result.points_without_buffer == 1

        by_designation = {item.designation: item for item in result.items}
        norrmalm = by_designation["Norrmalm 1:5"]
        assert norrmalm.assessed_value_sek == 125_000_000
        assert norrmalm.area_sqm == 4250.5
        assert norrmalm.owner_org_number == "556000-0001"
        assert norrmalm.property_type == PropertyType.KONTOR
        assert norrmalm.metadata_json == {"Anteckning": "Ombyggd 2018"}
        assert by_designation["Vasastan 2:8"].metadata_json == {}
        assert by_designation["Sundbyberg 3:12"].geometry is None

    def test_with_buffer_every_row_has_valid_geometry_in_sweden(self):
        result = parse_rows(read_file(EXAMPLE_CSV), point_buffer_m=25)
        assert result.without_geometry == 0
        for item in result.items:
            geom = shape(item.geometry)
            assert geom.is_valid
            minx, miny, maxx, maxy = geom.bounds
            assert 10 <= minx <= maxx <= 25
            assert 55 <= miny <= maxy <= 70


class TestCli:
    """CLI:t utan databas: --dry-run och felvägarna."""

    @pytest.fixture
    def main(self):
        from scripts.import_properties import main

        return main

    def test_dry_run_on_example(self, main, capsys):
        assert main([str(EXAMPLE_CSV), "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "Läste 3 rader" in out
        assert "3 giltiga, 0 med fel" in out
        assert "Taxeringsvärde (kr) → assessed_value_sek" in out
        assert "metadata: Anteckning" in out
        assert "1 rad saknar polygon" in out
        assert "Torrkörning" in out
        assert "Norrmalm 1:5" in out

    def test_dry_run_never_calls_the_write_path(self, monkeypatch, capsys):
        import scripts.import_properties as cli

        async def boom(items):
            raise AssertionError("skrivvägen ska inte anropas vid --dry-run")

        monkeypatch.setattr(cli, "_write", boom)
        assert cli.main([str(EXAMPLE_CSV), "--dry-run", "--point-buffer-m", "25"]) == 0
        assert "saknar polygon" not in capsys.readouterr().out

    def test_problems_listed_with_line_numbers(self, main, tmp_path, capsys):
        path = tmp_path / "fel.csv"
        path.write_text(
            "Beteckning;Typ;Taxeringsvärde\n"
            "Norrmalm 1:5;lager;100\n"
            "Vasastan 2:8;kontor;12,5\n"
            "Bra 1:1;villa;100\n",
            encoding="utf-8",
        )
        assert main([str(path), "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "Läste 3 rader" in out
        assert "1 giltiga, 2 med fel" in out
        assert "rad 2 (Norrmalm 1:5): Typ: okänd fastighetstyp 'lager'" in out
        assert "rad 3 (Vasastan 2:8): Taxeringsvärde: '12,5' är inte ett heltal" in out

        assert main([str(path), "--dry-run", "--strict"]) == 1
        assert "Avbryter (--strict)" in capsys.readouterr().out

    def test_problem_list_is_capped(self, main, tmp_path, capsys):
        path = tmp_path / "många.csv"
        lines = ["Beteckning;Typ"] + [f"Fel {i}:1;lager" for i in range(25)] + ["Ok 1:1;villa"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert main([str(path), "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "rad 21 (Fel 19:1)" in out
        assert "rad 22" not in out
        assert "… och 5 till" in out

    def test_no_valid_rows_fails(self, main, tmp_path, capsys):
        path = tmp_path / "bara_fel.csv"
        path.write_text("Beteckning;Typ\nA 1:1;lager\n", encoding="utf-8")
        assert main([str(path), "--dry-run"]) == 1
        assert "Inga giltiga rader" in capsys.readouterr().out

    def test_missing_file_fails(self, main, tmp_path, capsys):
        assert main([str(tmp_path / "finns_inte.csv"), "--dry-run"]) == 1
        assert "Fel:" in capsys.readouterr().err

    def test_missing_designation_column_fails(self, main, tmp_path, capsys):
        path = tmp_path / "utan.csv"
        path.write_text("Kommun;Ägare\nStockholm;Bolaget AB\n", encoding="utf-8")
        assert main([str(path), "--dry-run"]) == 1
        assert "fastighetsbeteckning" in capsys.readouterr().err

    def test_unknown_srid_fails(self, main, capsys):
        assert main([str(EXAMPLE_CSV), "--dry-run", "--srid", "999999"]) == 1
        assert "Okänt SRID" in capsys.readouterr().err

    def test_geojson_problems_use_feature_numbers(self, main, tmp_path, capsys):
        collection = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"beteckning": "A 1:1"}, "geometry": None},
                {
                    "type": "Feature",
                    "properties": {"beteckning": "B 1:1", "typ": "lager"},
                    "geometry": None,
                },
            ],
        }
        path = tmp_path / "f.geojson"
        path.write_text(json.dumps(collection), encoding="utf-8")
        assert main([str(path), "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "rad 2 (B 1:1): typ: okänd fastighetstyp" in out
        assert "1 rad saknar polygon" in out

    def test_problem_line_numbers_are_file_lines(self, main, tmp_path, capsys):
        path = tmp_path / "rader.csv"
        path.write_text(
            'Beteckning;Adress;Typ\nA 1:1;;villa\n\nB 1:1;"Gatan 1\nBox 2";villa\nC 1:1;;lager\n',
            encoding="utf-8",
        )
        assert main([str(path), "--dry-run"]) == 0
        assert "rad 6 (C 1:1): Typ: okänd fastighetstyp" in capsys.readouterr().out

    def test_help_and_errors_are_in_swedish(self, main, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert out.startswith("användning: ")
        assert "Visa den här hjälpen" in out
        assert "argument:" in out and "flaggor:" in out
        for english in ("usage:", "positional arguments", "options:", "show this help"):
            assert english not in out

        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "fel: följande argument saknas: FIL" in err
        assert "error" not in err

        with pytest.raises(SystemExit):
            main([str(EXAMPLE_CSV), "--srid", "abc"])
        assert "'abc' är inte en EPSG-kod" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "error",
        [
            # asyncpg:s anslutningsfel ärver varken OSError eller SQLAlchemyError
            asyncpg.InvalidPasswordError('password authentication failed for user "x"'),
            asyncpg.InvalidCatalogNameError('database "finns_inte" does not exist'),
            asyncpg.InterfaceError("connection is closed"),
            ConnectionRefusedError(111, "Connection refused"),
        ],
    )
    def test_database_errors_are_reported_not_raised(self, monkeypatch, capsys, error):
        import scripts.import_properties as cli

        async def failing_write(items):
            raise error

        monkeypatch.setattr(cli, "_write", failing_write)
        assert cli.main([str(EXAMPLE_CSV)]) == 1
        err = capsys.readouterr().err
        assert "Fel: kunde inte skriva till databasen" in err
        assert type(error).__name__ in err
