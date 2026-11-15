"""Fetch data/index/ from the public GitHub Release `data` (used by deploy/web/cloudbuild.yaml).

Same layout as `scripts/data.py pull`, but standard library only and no `gh`
login: the repo is public, so listing and downloading release files needs no key.
"""
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = sys.argv[1] if len(sys.argv) > 1 else "FionaL7/AnalogAtlas"
DEST = Path("data/index")


def main() -> None:
    url = f"https://api.github.com/repos/{REPO}/releases/tags/data"
    with urllib.request.urlopen(url, timeout=60) as r:
        assets = json.load(r)["assets"]
    DEST.mkdir(parents=True, exist_ok=True)
    mine = [a for a in assets if a["name"].startswith("index__")]
    if not mine:
        sys.exit("no index__ files on the release")
    for a in mine:
        name = a["name"].split("__", 1)[1]
        tmp = DEST / f".{name}.part"
        urllib.request.urlretrieve(a["browser_download_url"], tmp)
        if name.endswith(".tar"):
            with tarfile.open(tmp) as tf:
                tf.extractall(DEST, filter="data")
            tmp.unlink()
        else:
            tmp.replace(DEST / name)
        print(f"ok {name} ({a['size'] / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
