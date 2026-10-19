#!/usr/bin/env python3
"""Download the OQLF linguistic datasets from Données Québec.

The data is not committed to this repo. Run this script to fetch it into
data/raw/. It writes a MANIFEST.json next to the files with the source URL,
size, SHA-256 and download time, so a scan can say which data it used.

The script asks the Données Québec (CKAN) API for the current file URLs,
because the OQLF puts the release date in each file name. If the API is not
reachable, it falls back to the last known URLs below.

Uses the Python standard library only.

Examples:
    python scripts/download_oqlf_data.py
    python scripts/download_oqlf_data.py --only terms
    python scripts/download_oqlf_data.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATASET_ID = "1c6567bf-8995-40b9-84a4-50faabae12f4"
DATASET_PAGE = "https://www.donneesquebec.ca/recherche/dataset/donnees-linguistiques"
API_URL = "https://www.donneesquebec.ca/recherche/api/3/action/package_show?id=" + DATASET_ID
LICENSE = "CC BY-NC-SA 4.0"
ATTRIBUTION = (
    "Source : Office québécois de la langue française, Vitrine linguistique. "
    "Données diffusées sur Données Québec sous licence CC BY-NC-SA 4.0."
)

# Short name -> resource id and last known download URL (checked 2026-10-19).
RESOURCES = {
    "terms": {
        "resource_id": "882453c2-93c3-4204-b5ff-6d6297082ad9",
        "title": "Termes officialisés (Grand dictionnaire terminologique)",
        "fallback_url": (
            "https://www.donneesquebec.ca/recherche/dataset/" + DATASET_ID
            + "/resource/882453c2-93c3-4204-b5ff-6d6297082ad9/download/termes_officialises_2026-01-14.csv"
        ),
    },
    "records": {
        "resource_id": "c3ce0af4-7c0f-4dd2-b53a-6dc7fb3ea5ef",
        "title": "Fiches terminologiques (Grand dictionnaire terminologique)",
        "fallback_url": (
            "https://www.donneesquebec.ca/recherche/dataset/" + DATASET_ID
            + "/resource/c3ce0af4-7c0f-4dd2-b53a-6dc7fb3ea5ef/download/fiches_recentes_signees_oqlf_2026-01-19.csv"
        ),
    },
    "bdl": {
        "resource_id": "f91f62f6-2bed-4bf1-891b-51255bf5fbba",
        "title": "Phrases grammaticales et agrammaticales (Banque de dépannage linguistique)",
        "fallback_url": (
            "https://www.donneesquebec.ca/recherche/dataset/" + DATASET_ID
            + "/resource/f91f62f6-2bed-4bf1-891b-51255bf5fbba/download/bdl-phrases-grammaticales-agrammaticales.csv"
        ),
    },
}

DEFAULT_DEST = Path(__file__).resolve().parent.parent / "data" / "raw"
USER_AGENT = "quebec-french-scanner/0.1 (portfolio project; data download script)"
TIMEOUT = 60


def fetch_current_urls() -> dict[str, str]:
    """Return resource_id -> current download URL from the CKAN API.

    Returns an empty dict if the API cannot be reached or parsed.
    """
    request = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Could not read the Données Québec API ({error}). Using last known URLs.")
        return {}
    if not payload.get("success"):
        print("The Données Québec API returned an error. Using last known URLs.")
        return {}
    return {r["id"]: r["url"] for r in payload["result"].get("resources", []) if r.get("url")}


def download(url: str, target: Path) -> tuple[int, str]:
    """Stream url to target. Return (size in bytes, sha256 hex)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 16):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(target)
    return size, digest.hexdigest()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 16):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the OQLF datasets from Données Québec.")
    parser.add_argument(
        "--only",
        choices=sorted(RESOURCES),
        action="append",
        help="Download only this dataset. Repeat to pick several. Default: all.",
    )
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Folder to save into. Default: data/raw")
    parser.add_argument("--force", action="store_true", help="Download again even if the file exists.")
    args = parser.parse_args(argv)

    names = args.only or list(RESOURCES)
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest_path = args.dest / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({"dataset_page": DATASET_PAGE, "license": LICENSE, "attribution": ATTRIBUTION})
    files = manifest.setdefault("files", {})

    print(f"OQLF data is licensed {LICENSE}. Attribution is required and commercial use is not allowed.")
    current = fetch_current_urls()
    failures = 0

    for name in names:
        info = RESOURCES[name]
        url = current.get(info["resource_id"], info["fallback_url"])
        target = args.dest / url.rsplit("/", 1)[-1]
        if target.exists() and not args.force:
            print(f"[{name}] {target.name} already exists. Skipping. Use --force to download again.")
            if name not in files:
                files[name] = {"file": target.name, "url": url, "bytes": target.stat().st_size,
                               "sha256": sha256_of(target), "downloaded_at": None}
            continue
        print(f"[{name}] Downloading {url}")
        try:
            size, checksum = download(url, target)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"[{name}] Failed: {error}", file=sys.stderr)
            failures += 1
            continue
        files[name] = {
            "title": info["title"],
            "resource_id": info["resource_id"],
            "file": target.name,
            "url": url,
            "bytes": size,
            "sha256": checksum,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        print(f"[{name}] Saved {target.name} ({size / 1_000_000:.1f} MB)")

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest written to {manifest_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
