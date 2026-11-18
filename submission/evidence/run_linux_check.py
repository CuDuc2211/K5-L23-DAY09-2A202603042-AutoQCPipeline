"""Verify the unmodified lab checker on a byte-verified Linux-native copy.

Run inside a Linux Python 3.12 container with the repo mounted read-only.
See VERIFICATION.md. No protected source or checker is modified.
"""
import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path("/opt/lab-verification"))
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if os.name != "posix":
        parser.error("Use Linux/container; this runner does not patch the Windows checker.")
    if destination == source or source in destination.parents or destination.exists():
        parser.error("Destination must be a new directory outside the source repo.")
    destination.mkdir(parents=True)
    pairs = []
    for name in ("data", "pipeline", "tests", "configs", "scripts", "submission"):
        shutil.copytree(source / name, destination / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
        pairs.extend((p, destination / p.relative_to(source))
                     for p in (source / name).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts)
    for name in ("README.md", "requirements.txt"):
        shutil.copy2(source / name, destination / name)
        pairs.append((source / name, destination / name))
    (destination / "work").mkdir()
    extra = source / "submission/evidence/extra_contract_checks.py"
    copied_extra = destination / "work/test_extra_checks.py"
    shutil.copy2(extra, copied_extra)
    pairs.append((extra, copied_extra))
    assert all(digest(a) == digest(b) for a, b in pairs), "Source/copy hash mismatch"
    print(f"SOURCE_SNAPSHOT_IDENTICAL {len(pairs)} files", flush=True)
    print("Python", sys.version, flush=True)
    for name in ("pillow", "imagehash", "pyyaml", "pytest", "numpy", "scipy", "pywavelets"):
        print(name, importlib.metadata.version(name), flush=True)
    scratch = destination.parent / (destination.name + "-scratch")
    scratch.mkdir()
    env = dict(os.environ, PYTHONUTF8="1", TMPDIR=str(scratch),
               PYTEST_ADDOPTS=f"--capture=sys --basetemp={scratch}/pytest",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    result = subprocess.run([sys.executable, "scripts/check_submission.py", "--no-train"],
                            cwd=destination, env=env, text=True, capture_output=True,
                            timeout=180)
    text = result.stdout + result.stderr + f"\nCHECK_EXIT_CODE={result.returncode}\n"
    (scratch / "check_core.log").write_text(text, encoding="utf-8")
    print(text, flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
