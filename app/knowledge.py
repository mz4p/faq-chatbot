import re
from pathlib import Path

TENANT_RE = re.compile(r"^[a-z0-9-]+$")


def load_tenants(directory: Path) -> dict[str, str]:
    """Wczytuje bazy wiedzy: każdy podkatalog to jedna firma (tenant).

    Pliki .md z podkatalogu są łączone alfabetycznie, każdy pod nagłówkiem z nazwą pliku.
    Katalogi o niepoprawnej nazwie lub bez plików .md są pomijane.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return {}

    tenants: dict[str, str] = {}
    for sub in sorted(directory.iterdir()):
        if not sub.is_dir() or not TENANT_RE.match(sub.name):
            continue
        parts = [
            f"## {md.stem}\n\n{md.read_text(encoding='utf-8').strip()}"
            for md in sorted(sub.glob("*.md"))
        ]
        if parts:
            tenants[sub.name] = "\n\n".join(parts)
    return tenants
