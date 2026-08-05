"""Seed the database with sample Swedish infrastructure and property data.

Run from the backend directory:
    python -m database.seed
"""

import sys
from datetime import datetime
from pathlib import Path

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from database.connection import Base, SessionLocal, engine
from models.infrastructure import InfrastructureProject
from models.property import Property


def make_polygon_wkt(center_lng: float, center_lat: float) -> str:
    """Create a small rectangular polygon WKT centered on a point.

    Approximately 0.003 degrees longitude x 0.002 degrees latitude.
    """
    half_lng = 0.0015
    half_lat = 0.001
    w = center_lng - half_lng
    e = center_lng + half_lng
    s = center_lat - half_lat
    n = center_lat + half_lat
    return (
        f"SRID=4326;POLYGON(("
        f"{w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}"
        f"))"
    )


INFRASTRUCTURE_PROJECTS = [
    {
        "external_id": "seed-forbifart-stockholm",
        "source": "manual",
        "name": "Förbifart Stockholm",
        "description": (
            "Motorvägsförbindelse väster om Stockholm, huvudsakligen i tunnel. "
            "Förbinder Kungens Kurva i söder med Häggvik i norr."
        ),
        "project_type": "tunnel",
        "status": "pågående",
        "start_date": datetime(2015, 1, 1),
        "end_date": datetime(2030, 12, 31),
        "budget_sek": 34_000_000_000,
        "geometry": "SRID=4326;LINESTRING(17.88 59.39, 17.86 59.35, 17.84 59.30, 17.85 59.25)",
        "impact_radius_m": 3000,
        "metadata_json": {"trafikverket_id": "TRV2015/1234", "kommun": "Stockholm, Järfälla, Sollentuna"},
    },
    {
        "external_id": "seed-vastlanken",
        "source": "manual",
        "name": "Västlänken",
        "description": (
            "Järnvägstunnel under centrala Göteborg med tre nya stationer: "
            "Göteborg Central, Haga och Korsvägen."
        ),
        "project_type": "järnväg",
        "status": "pågående",
        "start_date": datetime(2018, 1, 1),
        "end_date": datetime(2029, 12, 31),
        "budget_sek": 20_000_000_000,
        "geometry": "SRID=4326;LINESTRING(11.93 57.71, 11.97 57.715, 12.01 57.72)",
        "impact_radius_m": 2000,
        "metadata_json": {"trafikverket_id": "TRV2014/5678", "kommun": "Göteborg"},
    },
    {
        "external_id": "seed-ostlanken",
        "source": "manual",
        "name": "Ostlänken",
        "description": (
            "Ny järnväg för höghastighetståg mellan Järna och Linköping. "
            "Del av den planerade nya stambanan."
        ),
        "project_type": "järnväg",
        "status": "planerad",
        "start_date": datetime(2024, 1, 1),
        "end_date": datetime(2040, 12, 31),
        "budget_sek": 90_000_000_000,
        "geometry": "SRID=4326;LINESTRING(17.1 59.0, 16.5 58.7, 15.6 58.4)",
        "impact_radius_m": 5000,
        "metadata_json": {"trafikverket_id": "TRV2017/9012", "kommun": "Nyköping, Norrköping, Linköping"},
    },
    {
        "external_id": "seed-nya-slussen",
        "source": "manual",
        "name": "Nya Slussen",
        "description": (
            "Ombyggnad av Slussen i Stockholm med ny bussterminal, "
            "gångstråk och förbättrad vattenreglering mellan Mälaren och Saltsjön."
        ),
        "project_type": "bro",
        "status": "pågående",
        "start_date": datetime(2016, 1, 1),
        "end_date": datetime(2027, 12, 31),
        "budget_sek": 12_000_000_000,
        "geometry": "SRID=4326;POINT(18.0717 59.3195)",
        "impact_radius_m": 1000,
        "metadata_json": {"kommun": "Stockholm", "stadsdel": "Södermalm"},
    },
    {
        "external_id": "seed-norrbotniabanan",
        "source": "manual",
        "name": "Norrbotniabanan",
        "description": (
            "Ny kustjärnväg mellan Umeå och Luleå. "
            "Avsevärt förbättrar godstransporter och persontrafik i norra Sverige."
        ),
        "project_type": "järnväg",
        "status": "planerad",
        "start_date": datetime(2024, 1, 1),
        "end_date": datetime(2040, 12, 31),
        "budget_sek": 30_000_000_000,
        "geometry": "SRID=4326;LINESTRING(20.26 63.83, 21.0 64.75, 22.15 65.58)",
        "impact_radius_m": 5000,
        "metadata_json": {"trafikverket_id": "TRV2018/3456", "kommun": "Umeå, Skellefteå, Piteå, Luleå"},
    },
    {
        "external_id": "seed-tvarbana-sodertorn",
        "source": "manual",
        "name": "Tvärförbindelse Södertörn",
        "description": (
            "Ny väg mellan E4/E20 vid Vårby backe och väg 73 vid Jordbro. "
            "Knyter ihop de södra delarna av Stockholmsregionen."
        ),
        "project_type": "väg",
        "status": "planerad",
        "start_date": datetime(2025, 1, 1),
        "end_date": datetime(2032, 12, 31),
        "budget_sek": 10_000_000_000,
        "geometry": "SRID=4326;LINESTRING(17.93 59.22, 18.04 59.20, 18.15 59.19)",
        "impact_radius_m": 2000,
        "metadata_json": {"trafikverket_id": "TRV2019/7890", "kommun": "Huddinge, Haninge"},
    },
    {
        "external_id": "seed-citybanan",
        "source": "manual",
        "name": "Citybanan",
        "description": (
            "Pendeltågstunnel under centrala Stockholm mellan Tomteboda och Stockholms södra. "
            "Två nya stationer: Stockholm City och Stockholm Odenplan."
        ),
        "project_type": "järnväg",
        "status": "avslutad",
        "start_date": datetime(2009, 1, 1),
        "end_date": datetime(2017, 7, 10),
        "budget_sek": 16_800_000_000,
        "geometry": "SRID=4326;LINESTRING(18.04 59.345, 18.055 59.335, 18.07 59.32)",
        "impact_radius_m": 1500,
        "metadata_json": {"trafikverket_id": "TRV2006/0001", "kommun": "Stockholm, Solna"},
    },
    {
        "external_id": "seed-marieholmstunneln",
        "source": "manual",
        "name": "Marieholmstunneln",
        "description": (
            "Ny vägtunnel under Göta älv i Göteborg. "
            "Avlastar Tingstadstunneln och förbättrar trafikflödet."
        ),
        "project_type": "tunnel",
        "status": "pågående",
        "start_date": datetime(2018, 1, 1),
        "end_date": datetime(2026, 12, 31),
        "budget_sek": 4_000_000_000,
        "geometry": "SRID=4326;POINT(12.00 57.72)",
        "impact_radius_m": 1500,
        "metadata_json": {"trafikverket_id": "TRV2016/4567", "kommun": "Göteborg"},
    },
    {
        "external_id": "seed-roslagsbanan",
        "source": "manual",
        "name": "Roslagsbanan utbyggnad",
        "description": (
            "Utbyggnad och modernisering av Roslagsbanan i nordöstra Stockholm. "
            "Dubbelspår, nya stationer och ökad kapacitet."
        ),
        "project_type": "kollektivtrafik",
        "status": "planerad",
        "start_date": datetime(2023, 1, 1),
        "end_date": datetime(2030, 12, 31),
        "budget_sek": 6_000_000_000,
        "geometry": "SRID=4326;LINESTRING(18.07 59.36, 18.10 59.38, 18.17 59.43)",
        "impact_radius_m": 1500,
        "metadata_json": {"kommun": "Stockholm, Täby, Vallentuna"},
    },
    {
        "external_id": "seed-e4-sundsvall",
        "source": "manual",
        "name": "E4 Förbifart Sundsvall",
        "description": (
            "Ny sträckning av E4 förbi Sundsvall med bro över Sundsvallsfjärden. "
            "Minskar genomfartstrafiken i centrala Sundsvall."
        ),
        "project_type": "väg",
        "status": "avslutad",
        "start_date": datetime(2010, 1, 1),
        "end_date": datetime(2015, 10, 19),
        "budget_sek": 4_100_000_000,
        "geometry": "SRID=4326;LINESTRING(17.25 62.36, 17.30 62.39, 17.38 62.42)",
        "impact_radius_m": 2000,
        "metadata_json": {"trafikverket_id": "TRV2007/8901", "kommun": "Sundsvall"},
    },
]


PROPERTIES = [
    {
        "designation": "Norrmalm 1:5",
        "municipality": "Stockholm",
        "county": "Stockholms län",
        "area_sqm": 4500,
        "assessed_value_sek": 85_000_000,
        "property_type": "kontor",
        "owner_name": "Vasakronan AB",
        "owner_org_number": "556061-4603",
        "address": "Kungsgatan 10",
        "postal_code": "111 43",
        "city": "Stockholm",
        "geometry": make_polygon_wkt(18.065, 59.335),
        "building_year": 1965,
        "living_area_sqm": None,
        "zoning": "C",
        "metadata_json": {},
    },
    {
        "designation": "Södermalm 3:12",
        "municipality": "Stockholm",
        "county": "Stockholms län",
        "area_sqm": 2800,
        "assessed_value_sek": 120_000_000,
        "property_type": "bostad",
        "owner_name": "Stockholms Kooperativa Bostadsförening",
        "owner_org_number": "702001-1234",
        "address": "Hornsgatan 45",
        "postal_code": "118 49",
        "city": "Stockholm",
        "geometry": make_polygon_wkt(18.07, 59.315),
        "building_year": 1928,
        "living_area_sqm": 5200,
        "zoning": "B",
        "metadata_json": {},
    },
    {
        "designation": "Solna Centrum 2:1",
        "municipality": "Solna",
        "county": "Stockholms län",
        "area_sqm": 12000,
        "assessed_value_sek": 350_000_000,
        "property_type": "handel",
        "owner_name": "Unibail-Rodamco-Westfield",
        "owner_org_number": "556079-1415",
        "address": "Solnavägen 25",
        "postal_code": "171 45",
        "city": "Solna",
        "geometry": make_polygon_wkt(18.00, 59.36),
        "building_year": 1995,
        "living_area_sqm": None,
        "zoning": "C",
        "metadata_json": {},
    },
    {
        "designation": "Nacka Strand 5:3",
        "municipality": "Nacka",
        "county": "Stockholms län",
        "area_sqm": 5000,
        "assessed_value_sek": 95_000_000,
        "property_type": "bostad",
        "owner_name": "JM AB",
        "owner_org_number": "556045-2770",
        "address": "Strandvägen 1",
        "postal_code": "131 52",
        "city": "Nacka",
        "geometry": make_polygon_wkt(18.14, 59.31),
        "building_year": 2018,
        "living_area_sqm": 8500,
        "zoning": "B",
        "metadata_json": {},
    },
    {
        "designation": "Sundbyberg 1:8",
        "municipality": "Sundbyberg",
        "county": "Stockholms län",
        "area_sqm": 3200,
        "assessed_value_sek": 78_000_000,
        "property_type": "bostad",
        "owner_name": "Sundbybergs Bostäder AB",
        "owner_org_number": "556055-1234",
        "address": "Sturegatan 12",
        "postal_code": "172 31",
        "city": "Sundbyberg",
        "geometry": make_polygon_wkt(17.97, 59.36),
        "building_year": 1972,
        "living_area_sqm": 4800,
        "zoning": "B",
        "metadata_json": {},
    },
    {
        "designation": "Kista 4:2",
        "municipality": "Stockholm",
        "county": "Stockholms län",
        "area_sqm": 25000,
        "assessed_value_sek": 420_000_000,
        "property_type": "kontor",
        "owner_name": "Castellum AB",
        "owner_org_number": "556475-5550",
        "address": "Kistagången 8",
        "postal_code": "164 40",
        "city": "Stockholm",
        "geometry": make_polygon_wkt(17.95, 59.40),
        "building_year": 2002,
        "living_area_sqm": None,
        "zoning": "J",
        "metadata_json": {},
    },
    {
        "designation": "Hammarby Sjöstad 7:1",
        "municipality": "Stockholm",
        "county": "Stockholms län",
        "area_sqm": 6000,
        "assessed_value_sek": 180_000_000,
        "property_type": "bostad",
        "owner_name": "HSB Stockholm",
        "owner_org_number": "504001-1234",
        "address": "Hammarby Allé 42",
        "postal_code": "120 63",
        "city": "Stockholm",
        "geometry": make_polygon_wkt(18.10, 59.30),
        "building_year": 2006,
        "living_area_sqm": 9200,
        "zoning": "B",
        "metadata_json": {},
    },
    {
        "designation": "Bromma 12:4",
        "municipality": "Stockholm",
        "county": "Stockholms län",
        "area_sqm": 800,
        "assessed_value_sek": 12_500_000,
        "property_type": "villa",
        "owner_name": "Anna Lindström",
        "owner_org_number": None,
        "address": "Åkeshovsvägen 18",
        "postal_code": "168 39",
        "city": "Stockholm",
        "geometry": make_polygon_wkt(17.94, 59.34),
        "building_year": 1945,
        "living_area_sqm": 220,
        "zoning": "B",
        "metadata_json": {},
    },
    {
        "designation": "Täby Centrum 3:7",
        "municipality": "Täby",
        "county": "Stockholms län",
        "area_sqm": 15000,
        "assessed_value_sek": 280_000_000,
        "property_type": "handel",
        "owner_name": "Unibail-Rodamco-Westfield",
        "owner_org_number": "556079-1415",
        "address": "Stora Marknadsvägen 15",
        "postal_code": "183 34",
        "city": "Täby",
        "geometry": make_polygon_wkt(18.07, 59.44),
        "building_year": 1968,
        "living_area_sqm": None,
        "zoning": "C",
        "metadata_json": {},
    },
    {
        "designation": "Flemingsberg 2:5",
        "municipality": "Huddinge",
        "county": "Stockholms län",
        "area_sqm": 8000,
        "assessed_value_sek": 150_000_000,
        "property_type": "utbildning",
        "owner_name": "Akademiska Hus AB",
        "owner_org_number": "556459-9156",
        "address": "Alfred Nobels Allé 7",
        "postal_code": "141 52",
        "city": "Huddinge",
        "geometry": make_polygon_wkt(17.95, 59.22),
        "building_year": 2012,
        "living_area_sqm": None,
        "zoning": "S",
        "metadata_json": {},
    },
]


def seed():
    """Seed the database with sample data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    session = SessionLocal()

    try:
        # Check if infrastructure projects already exist
        existing_projects = session.query(InfrastructureProject).count()
        if existing_projects > 0:
            print(
                f"Database already contains {existing_projects} infrastructure projects. "
                "Skipping infrastructure seed."
            )
        else:
            print("Seeding infrastructure projects...")
            for i, proj_data in enumerate(INFRASTRUCTURE_PROJECTS, 1):
                project = InfrastructureProject(
                    external_id=proj_data["external_id"],
                    source=proj_data["source"],
                    name=proj_data["name"],
                    description=proj_data["description"],
                    project_type=proj_data["project_type"],
                    status=proj_data["status"],
                    start_date=proj_data["start_date"],
                    end_date=proj_data["end_date"],
                    budget_sek=proj_data["budget_sek"],
                    geometry=proj_data["geometry"],
                    impact_radius_m=proj_data["impact_radius_m"],
                    metadata_json=proj_data["metadata_json"],
                )
                session.add(project)
                print(f"  [{i}/10] {proj_data['name']} ({proj_data['status']})")

            session.commit()
            print("Infrastructure projects seeded successfully.")

        # Check if properties already exist
        existing_properties = session.query(Property).count()
        if existing_properties > 0:
            print(
                f"Database already contains {existing_properties} properties. "
                "Skipping property seed."
            )
        else:
            print("Seeding properties...")
            for i, prop_data in enumerate(PROPERTIES, 1):
                prop = Property(
                    designation=prop_data["designation"],
                    municipality=prop_data["municipality"],
                    county=prop_data["county"],
                    area_sqm=prop_data["area_sqm"],
                    assessed_value_sek=prop_data["assessed_value_sek"],
                    property_type=prop_data["property_type"],
                    owner_name=prop_data["owner_name"],
                    owner_org_number=prop_data["owner_org_number"],
                    address=prop_data["address"],
                    postal_code=prop_data["postal_code"],
                    city=prop_data["city"],
                    geometry=prop_data["geometry"],
                    building_year=prop_data["building_year"],
                    living_area_sqm=prop_data["living_area_sqm"],
                    zoning=prop_data["zoning"],
                    metadata_json=prop_data["metadata_json"],
                )
                session.add(prop)
                print(f"  [{i}/10] {prop_data['designation']} ({prop_data['property_type']})")

            session.commit()
            print("Properties seeded successfully.")

        print("\nSeed complete!")
        final_projects = session.query(InfrastructureProject).count()
        final_properties = session.query(Property).count()
        print(f"  Infrastructure projects: {final_projects}")
        print(f"  Properties: {final_properties}")

    except Exception as e:
        session.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
