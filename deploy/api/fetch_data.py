"""Fetch what the API needs from the GitHub Release `data` (used by the Dockerfile).

Retries and resumes, because the 588 MB tiles tar does get cut off mid-download.
Standard library only: the image has no curl.
"""
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = sys.argv[1] if len(sys.argv) > 1 else "FionaL7/AnalogAtlas"
BASE = f"https://github.com/{REPO}/releases/download/data"
DATA = Path("data")
FILES = ("meta.parquet", "img.npy", "shade.npy", "order.json")
INDEX = [f"{body}_{f}" for body in ("moon", "moon_polar", "earth") for f in FILES] + ["earth_scores.parquet"]
# Mars (docs/MARS-PLAN.md) is fetched when it is on the release and skipped
# when it is not, so the deploy works before and after the Mars index exists.
# Its tiles are not fetched: the app draws Mars pictures from NASA Mars Trek.
OPTIONAL_INDEX = [f"mars_{f}" for f in FILES]
TILES = ["moon", "earth"]


def get(url: str, dest: Path, tries: int = 6) -> None:
    for attempt in range(1, tries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                total = have + int(r.headers.get("Content-Length", 0))
                if have and r.status != 206:      # server ignored Range: start over
                    have, total = 0, int(r.headers.get("Content-Length", 0))
                with open(dest, "ab" if have else "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
            if dest.stat().st_size >= total:
                print(f"ok {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
                return
        except Exception as e:  # noqa: BLE001 - any network error: retry
            print(f"{dest.name}: attempt {attempt} failed: {e}")
        time.sleep(3 * attempt)
    sys.exit(f"could not download {url}")


def exists(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


(DATA / "index").mkdir(parents=True, exist_ok=True)
(DATA / "tiles").mkdir(parents=True, exist_ok=True)
for name in INDEX:
    get(f"{BASE}/index__{name}", DATA / "index" / name)
# all four Mars files or none: a half index would fail the order check
if all(exists(f"{BASE}/index__{name}") for name in OPTIONAL_INDEX):
    for name in OPTIONAL_INDEX:
        get(f"{BASE}/index__{name}", DATA / "index" / name)
else:
    print("no complete Mars index on the release yet: serving without Mars")
for body in TILES:
    tar = Path(f"/tmp/tiles_{body}.tar")
    get(f"{BASE}/tiles__{body}.tar", tar)
    with tarfile.open(tar) as tf:
        tf.extractall(DATA / "tiles", filter="data")
    tar.unlink()
