"""Enhetstester för Trafikverket-källan — parsning, statushärledning och fel."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.datasources.base import DataSourceError
from app.datasources.trafikverket import (
    API_URL,
    TrafikverketDataSource,
    build_request_xml,
    derive_status,
    map_message_type,
    parse_timestamp,
    parse_wkt_geometry,
)
from app.domain import ProjectStatus, ProjectType

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


class TestParseWktGeometry:
    def test_point(self):
        result = parse_wkt_geometry("POINT (18.07 59.33)")
        assert result == {"type": "Point", "coordinates": (18.07, 59.33)}

    def test_linestring(self):
        result = parse_wkt_geometry("LINESTRING (18.07 59.33, 18.08 59.34)")
        assert result["type"] == "LineString"
        assert list(result["coordinates"]) == [(18.07, 59.33), (18.08, 59.34)]

    def test_multipoint(self):
        result = parse_wkt_geometry("MULTIPOINT ((18.07 59.33), (18.08 59.34))")
        assert result["type"] == "MultiPoint"

    def test_invalid_returns_none(self):
        assert parse_wkt_geometry("INTE WKT ALLS") is None

    def test_empty_returns_none(self):
        assert parse_wkt_geometry(None) is None
        assert parse_wkt_geometry("") is None


class TestDeriveStatus:
    def test_future_start_is_planerad(self):
        start = datetime(2027, 1, 1, tzinfo=UTC)
        assert derive_status(start, None, NOW) == ProjectStatus.PLANERAD

    def test_past_end_is_avslutad(self):
        end = datetime(2025, 1, 1, tzinfo=UTC)
        assert derive_status(None, end, NOW) == ProjectStatus.AVSLUTAD

    def test_ongoing_is_pagaende(self):
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2027, 1, 1, tzinfo=UTC)
        assert derive_status(start, end, NOW) == ProjectStatus.PAGAENDE

    def test_no_dates_is_pagaende(self):
        assert derive_status(None, None, NOW) == ProjectStatus.PAGAENDE


class TestParseTimestamp:
    def test_iso_with_offset(self):
        result = parse_timestamp("2026-08-01T10:00:00.000+02:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_naive_becomes_aware(self):
        result = parse_timestamp("2026-08-01T10:00:00")
        assert result.tzinfo is not None

    def test_invalid_returns_none(self):
        assert parse_timestamp("inte-en-tid") is None
        assert parse_timestamp(None) is None


class TestMapMessageType:
    def test_known_types(self):
        assert map_message_type("Vägarbete") == ProjectType.VAG
        assert map_message_type("Järnväg") == ProjectType.JARNVAG

    def test_unknown_is_ovrigt(self):
        assert map_message_type("Rymduppskjutning") == ProjectType.OVRIGT
        assert map_message_type(None) == ProjectType.OVRIGT


class TestBuildRequestXml:
    def test_without_bbox_has_empty_filter(self):
        xml = build_request_xml("nyckel123")
        assert "<FILTER></FILTER>" in xml
        assert 'authenticationkey="nyckel123"' in xml

    def test_with_bbox_has_within_filter(self):
        xml = build_request_xml("nyckel123", bbox=(17.0, 59.0, 19.0, 60.0))
        assert "WITHIN" in xml
        assert "17.0 59.0, 19.0 60.0" in xml


SAMPLE_RESPONSE = {
    "RESPONSE": {
        "RESULT": [
            {
                "Situation": [
                    {
                        "Deviation": [
                            {
                                "Id": "TRV-1",
                                "Header": "Vägarbete E4",
                                "Message": "Körfält avstängt",
                                "MessageType": "Vägarbete",
                                "StartTime": "2026-07-01T08:00:00.000+02:00",
                                "EndTime": "2026-09-01T17:00:00.000+02:00",
                                "SeverityCode": 2,
                                "Geometry": {"Point": {"WGS84": "POINT (18.07 59.33)"}},
                            }
                        ]
                    },
                    {
                        # Deviation som objekt (inte lista) — förekommer i API:t
                        "Deviation": {
                            "Id": "TRV-2",
                            "Header": "Framtida banarbete",
                            "MessageType": "Järnväg",
                            "StartTime": "2027-01-01T00:00:00.000+01:00",
                            "Geometry": {
                                "Line": {"WGS84": "LINESTRING (11.93 57.71, 11.97 57.715)"}
                            },
                        }
                    },
                    {
                        # Deviation utan Id ska hoppas över
                        "Deviation": [{"Header": "Utan id"}]
                    },
                ]
            }
        ]
    }
}


class TestParseResponse:
    def setup_method(self):
        self.source = TrafikverketDataSource(api_key="test")

    def test_parses_deviations(self):
        results = self.source._parse_response(SAMPLE_RESPONSE, bbox=None)
        assert len(results) == 2

        first = results[0]
        assert first.external_id == "TRV-1"
        assert first.name == "Vägarbete E4"
        assert first.project_type == ProjectType.VAG
        assert first.geometry["type"] == "Point"
        assert first.source == "trafikverket"

    def test_status_derived_from_times(self):
        results = self.source._parse_response(SAMPLE_RESPONSE, bbox=None)
        # TRV-2 startar 2027 — måste bli planerad, inte hårdkodat pågående
        by_id = {r.external_id: r for r in results}
        assert by_id["TRV-2"].status == ProjectStatus.PLANERAD

    def test_bbox_filters_results(self):
        stockholm_bbox = (17.5, 59.0, 18.5, 59.7)
        results = self.source._parse_response(SAMPLE_RESPONSE, bbox=stockholm_bbox)
        assert [r.external_id for r in results] == ["TRV-1"]


class TestFetch:
    async def test_missing_api_key_raises(self):
        source = TrafikverketDataSource(api_key="")
        with pytest.raises(DataSourceError, match="TRAFIKVERKET_API_KEY"):
            await source.fetch_infrastructure_projects()

    @respx.mock
    async def test_http_error_raises_not_swallowed(self):
        respx.post(API_URL).mock(return_value=httpx.Response(500))
        source = TrafikverketDataSource(api_key="test")
        with pytest.raises(DataSourceError, match="misslyckades"):
            await source.fetch_infrastructure_projects()

    @respx.mock
    async def test_happy_path(self):
        respx.post(API_URL).mock(return_value=httpx.Response(200, json=SAMPLE_RESPONSE))
        source = TrafikverketDataSource(api_key="test")
        results = await source.fetch_infrastructure_projects()
        assert len(results) == 2
