"""Exportera OpenAPI-schemat till backend/openapi.json.

Filen är incheckad och är källan för frontendens genererade
TypeScript-typer (npm run typegen). CI verifierar att båda är i synk.

    uv run python -m scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).parents[1] / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUTPUT_PATH.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Skrev {OUTPUT_PATH} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
