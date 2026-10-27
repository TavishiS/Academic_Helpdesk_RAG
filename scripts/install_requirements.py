"""
Install only the requirements that are missing or too old (used by `make venv`).

  python scripts/install_requirements.py [--torch-cpu]
"""
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    from packaging.requirements import Requirement
except ImportError:  # a fresh venv has no `packaging`, but pip always ships a copy
    from pip._vendor.packaging.requirements import Requirement

REQ_FILE = Path(__file__).resolve().parent.parent / "requirements.txt"


def status(req):
    try:
        installed = version(req.name)
    except PackageNotFoundError:
        return None, "missing"
    if req.specifier and not req.specifier.contains(installed, prereleases=True):
        return installed, f"outdated (need {req.specifier})"
    return installed, "ok"


def pip_install(args):
    print(f"    $ pip install {' '.join(args)}", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", *args])


def main():
    reqs = [Requirement(l.strip()) for l in REQ_FILE.read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]

    todo = []
    for req in reqs:
        installed, state = status(req)
        mark = "✔" if state == "ok" else "✘"
        print(f"  {mark} {req.name:<24} {installed or '-':<12} {state}")
        if state != "ok":
            todo.append(str(req))

    if not todo:
        print("==> All requirements already satisfied, nothing to install.")
        return

    # sentence-transformers pulls in PyTorch; the CPU-only wheel is ~5x smaller than the CUDA one
    if "--torch-cpu" in sys.argv and status(Requirement("torch"))[1] == "missing":
        print("==> Installing CPU-only PyTorch first")
        pip_install(["torch", "--index-url", "https://download.pytorch.org/whl/cpu"])

    print(f"==> Installing {len(todo)} package(s): {', '.join(todo)}")
    print("    (this can take several minutes the first time, mostly because of PyTorch)")
    pip_install(todo)
    print("==> Done.")


if __name__ == "__main__":
    main()
