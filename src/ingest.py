import hashlib
import json
import sys
import urllib.request
from datetime import date

from config import RAW_DIR, RAW_FILES, SOURCES


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "covid19-global-analytics"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest(force=False):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for key, filename in RAW_FILES.items():
        dest = RAW_DIR / filename
        if dest.exists() and not force:
            print(f"ingest: {filename} already present, skipping")
            continue
        print(f"ingest: downloading {filename}")
        try:
            download(SOURCES[key], dest)
        except OSError as err:
            sys.exit(f"ingest: could not download {SOURCES[key]}: {err}")
        manifest[filename] = {
            "url": SOURCES[key],
            "accessed": date.today().isoformat(),
            "bytes": dest.stat().st_size,
            "sha256": sha256(dest),
        }

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    ingest(force="--force" in sys.argv)
