"""Build what the demo page loads, into ``site/``.

    python generator/Second_demo_generator/build_bundle.py             # the Python bundle
    python generator/Second_demo_generator/build_bundle.py --pyodide   # and, once, Pyodide

1. ``site/python_bundle.json``: every module of ``pipeline/`` and
   ``case_model/`` that the demo imports, plus ``demo_bridge.py`` and the two
   fixtures it reads, each under its path in the repo. The page writes them
   into Pyodide's file system in the same layout, so the browser runs exactly
   the repo's code. Rebuild after any change in those folders.
2. ``site/pyodide/``: Pyodide itself and the wheels pydantic and PyMuPDF need (PyMuPDF
   for the Example documents step, Daniel's studio; the page loads it only there). An artifact
   page may load scripts from Pyodide's CDN, but it may not *fetch* from it,
   and Pyodide fetches its WebAssembly, its standard library and its packages.
   So the page serves these files itself. Downloaded from the CDN (or copied
   from an unpacked Pyodide release with ``--pyodide DIR``); each wheel is
   checked against the sha256 in Pyodide's lock file. The artifact host does
   not serve ``.zip`` or ``.whl`` files, so those are stored with ``.wasm``
   added (a type it serves as bytes); the page maps Pyodide's requests to
   those names.

Both are generated, so git ignores them. Publish ``site/`` after building (see
the README).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SITE = HERE / "site"
OUT = SITE / "python_bundle.json"

PYODIDE_VERSION = "0.29.3"         # Python 3.13, pydantic 2.12.5 (tests pass on it)
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_CORE = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip"]
PACKAGES = ["pydantic", "pymupdf"]  # and what they depend on, from the lock file (PyMuPDF: the studio step)
SERVED_AS = ".wasm"                # added to .zip and .whl files (see above)


def bundle_files() -> dict[str, str]:
    """Repo path -> text of every file the demo needs in the browser."""
    for path in (str(ROOT), str(HERE)):
        if path not in sys.path:
            sys.path.insert(0, path)
    import demo_bridge  # noqa: F401  (imports the chain and everything it uses)

    import studio_bridge  # noqa: F401  (Daniel's studio, offline; PyMuPDF is loaded in the page)

    paths = {Path(demo_bridge.__file__).resolve(), demo_bridge.REQUEST_FIXTURE,
             demo_bridge.AMEXIO_FIXTURE, Path(studio_bridge.__file__).resolve(),
             studio_bridge.STUDIO_APP}
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] in ("pipeline", "case_model") and getattr(module, "__file__", None):
            paths.add(Path(module.__file__).resolve())
    return {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(paths)}


def build() -> Path:
    files = bundle_files()
    SITE.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"entry": HERE.relative_to(ROOT).as_posix(), "files": files},
                              ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    return OUT


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def _served(name: str) -> str:
    return name + SERVED_AS if name.endswith((".zip", ".whl")) else name


def fetch_pyodide(source: str = PYODIDE_CDN, out: Path = SITE / "pyodide",
                  packages: tuple[str, ...] | list[str] = tuple(PACKAGES)) -> list[str]:
    """Copy Pyodide's runtime and the wheels of ``packages`` into ``out``,
    with a lock file cut down to those packages. ``source`` is the CDN folder
    or a local folder of an unpacked Pyodide release."""
    def read(name: str) -> bytes:
        if source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source.rstrip("/") + "/" + name, timeout=120) as response:
                return response.read()
        return (Path(source) / name).read_bytes()

    lock = json.loads(read("pyodide-lock.json"))
    keys = {_norm(p["name"]): key for key, p in lock["packages"].items()}
    needed, todo = set(), [_norm(n) for n in packages]
    while todo:
        name = todo.pop()
        if name not in needed:
            needed.add(name)
            todo += [_norm(d) for d in lock["packages"][keys[name]]["depends"]]
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in PYODIDE_CORE:
        (out / _served(name)).write_bytes(read(name))
        written.append(_served(name))
    packages = {}
    for name in sorted(needed):
        entry = lock["packages"][keys[name]]
        data = read(entry["file_name"])
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{entry['file_name']}: sha256 does not match pyodide-lock.json")
        (out / _served(entry["file_name"])).write_bytes(data)
        written.append(_served(entry["file_name"]))
        packages[keys[name]] = entry
    (out / "pyodide-lock.json").write_text(json.dumps({"info": lock["info"], "packages": packages},
                                                      indent=1, sort_keys=True) + "\n",
                                           encoding="utf-8", newline="\n")
    written.append("pyodide-lock.json")
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pyodide", nargs="?", const=PYODIDE_CDN, metavar="SOURCE",
                        help=f"also copy Pyodide {PYODIDE_VERSION} into site/pyodide/ "
                             "(default: from its CDN; or a folder of an unpacked release)")
    args = parser.parse_args()
    out = build()
    print(f"wrote {out.relative_to(ROOT)} ({len(json.loads(out.read_text(encoding='utf-8'))['files'])} files)")
    if args.pyodide:
        files = fetch_pyodide(args.pyodide)
        print(f"wrote site/pyodide/ ({len(files)} files) from {args.pyodide}")
