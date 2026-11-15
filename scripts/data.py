"""Share data/ between machines through GitHub Release files (release tag `data`).

    python scripts/data.py pull                 # data/index/ (all the API needs)
    python scripts/data.py pull raw tiles       # other folders
    python scripts/data.py pull all
    python scripts/data.py push index           # upload all of data/index/
    python scripts/data.py push raw/minirf index/moon_meta.parquet
    python scripts/data.py list

Each entry directly under data/<folder>/ is one release file:
    a file   -> "<folder>__<name>"         e.g. index__moon_meta.parquet
    a folder -> "<folder>__<name>.tar"     e.g. tiles__moon.tar (uncompressed; tiles are PNG/JPG)
Push replaces files of the same name, so the last push of an entry wins.
Needs only the standard library and a logged-in `gh`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TAG = "data"
FOLDERS = ["index", "raw", "tiles"]
MAX_BYTES = 2 * 1024**3  # GitHub's per-file limit


def gh(*args: str, capture: bool = False) -> str:
    r = subprocess.run(["gh", *args], cwd=ROOT, text=True,
                       capture_output=capture, check=False)
    if r.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed:\n{r.stderr if capture else ''}")
    return r.stdout if capture else ""


def ensure_release() -> None:
    r = subprocess.run(["gh", "release", "view", TAG], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        gh("release", "create", TAG, "--title", "Data files (data/)", "--latest=false",
           "--notes", "Shared data/ files. Use `python scripts/data.py pull|push`; "
                      "see .claude/skills/data-sync/SKILL.md.")


def assets() -> list[dict]:
    out = gh("release", "view", TAG, "--json", "assets", capture=True)
    return json.loads(out)["assets"]


def entries(target: str) -> list[Path]:
    """'index' -> every entry in data/index/; 'raw/minirf' -> just that entry."""
    p = DATA / target
    if not p.exists():
        sys.exit(f"{p} does not exist")
    if target in FOLDERS:
        return sorted(x for x in p.iterdir() if not x.name.startswith("."))
    if p.parent.parent != DATA or p.parent.name not in FOLDERS:
        sys.exit(f"{target}: give a folder ({', '.join(FOLDERS)}) or one entry inside it")
    return [p]


def push(targets: list[str]) -> None:
    ensure_release()
    with tempfile.TemporaryDirectory() as tmp:
        for target in targets:
            for p in entries(target):
                name = f"{p.parent.name}__{p.name}"
                if p.is_dir():
                    name += ".tar"
                    src = Path(tmp) / name
                    print(f"packing {p.relative_to(DATA)} ...")
                    with tarfile.open(src, "w") as tf:
                        tf.add(p, arcname=p.name)
                else:
                    src = Path(tmp) / name
                    shutil.copy2(p, src)
                if src.stat().st_size > MAX_BYTES:
                    sys.exit(f"{name} is over 2 GB; split the folder first")
                print(f"uploading {name} ({src.stat().st_size / 1e6:.1f} MB)")
                gh("release", "upload", TAG, str(src), "--clobber")
                src.unlink()


def pull(folders: list[str]) -> None:
    if folders == ["all"]:
        folders = FOLDERS
    names = [a["name"] for a in assets()]
    with tempfile.TemporaryDirectory() as tmp:
        for folder in folders:
            if folder not in FOLDERS:
                sys.exit(f"unknown folder {folder}; use {', '.join(FOLDERS)} or all")
            mine = [n for n in names if n.startswith(f"{folder}__")]
            if not mine:
                print(f"nothing uploaded for {folder}/ yet")
                continue
            dest = DATA / folder
            dest.mkdir(parents=True, exist_ok=True)
            for name in mine:
                print(f"downloading {name}")
                gh("release", "download", TAG, "-p", name, "-D", tmp, "--clobber")
                src = Path(tmp) / name
                if name.endswith(".tar"):
                    with tarfile.open(src) as tf:
                        tf.extractall(dest, filter="data")
                else:
                    shutil.move(src, dest / name.split("__", 1)[1])
                src.unlink(missing_ok=True)
    print("done")


def list_assets() -> None:
    for a in sorted(assets(), key=lambda a: a["name"]):
        print(f"{a['size'] / 1e6:9.1f} MB  {a['updatedAt'][:16]}  {a['name']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull")
    p.add_argument("folders", nargs="*", default=["index"])
    p = sub.add_parser("push")
    p.add_argument("targets", nargs="+")
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "pull":
        pull(a.folders)
    elif a.cmd == "push":
        push(a.targets)
    else:
        list_assets()


if __name__ == "__main__":
    main()
