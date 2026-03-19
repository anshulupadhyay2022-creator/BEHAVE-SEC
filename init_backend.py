#!/usr/bin/env python3
"""
============================================================
  BEHAVE-SEC  |  Backend Initializer
  Run this file to bootstrap and start the entire backend.

  Usage:
      python init_backend.py
      python init_backend.py --host 0.0.0.0 --port 8000
      python init_backend.py --reload          # dev hot-reload

  What this file does (in order):
      1. Verifies Python >= 3.8
      2. Loads environment variables from .env (if present)
      3. Installs missing pip packages from requirements.txt
      4. Creates required runtime directories
      5. Validates that backend_api.py is importable
      6. Launches the Uvicorn ASGI server
============================================================
"""

import sys
import os
import argparse
import subprocess
import importlib.util


# ──────────────────────────────────────────────────────────
# ANSI colour helpers (graceful fallback on Windows)
# ──────────────────────────────────────────────────────────
try:
    import colorama  # type: ignore[import-untyped]
    colorama.init(autoreset=True)
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""


def banner() -> None:
    print(f"\n{BOLD}{CYAN}" + "=" * 60)
    print("  BEHAVE-SEC  |  Backend Initializer  v1.0")
    print("=" * 60 + RESET + "\n")


def ok(msg: str)   -> None: print(f"  {GREEN}[OK]{RESET}  {msg}")
def err(msg: str)  -> None: print(f"  {RED}[ERR]{RESET} {msg}")
def warn(msg: str) -> None: print(f"  {YELLOW}[!!]{RESET}  {msg}")
def info(msg: str) -> None: print(f"  {CYAN}[>>]{RESET}  {msg}")


# ──────────────────────────────────────────────────────────
# STEP 1 – Python version check
# ──────────────────────────────────────────────────────────
def check_python_version(min_major: int = 3, min_minor: int = 8) -> None:
    info("Checking Python version ...")
    major, minor = sys.version_info.major, sys.version_info.minor
    version_str = f"{major}.{minor}.{sys.version_info.micro}"

    if (major, minor) < (min_major, min_minor):
        err(f"Python {min_major}.{min_minor}+ required  (found {version_str})")
        sys.exit(1)

    ok(f"Python {version_str}")


# ──────────────────────────────────────────────────────────
# STEP 2 – Load .env variables
# ──────────────────────────────────────────────────────────
def load_dotenv(env_path: str = ".env") -> None:
    info("Loading environment variables ...")

    if not os.path.isfile(env_path):
        warn(f".env file not found at '{env_path}' — skipping")
        return

    with open(env_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            # Skip blanks and comments
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            # Don't overwrite variables already set in the real environment
            if key and key not in os.environ:
                os.environ[key] = value

    ok(f"Environment loaded from '{env_path}'")


# ──────────────────────────────────────────────────────────
# STEP 3 – Dependency installation
# ──────────────────────────────────────────────────────────
REQUIRED_PACKAGES = [
    ("fastapi",           "fastapi"),
    ("uvicorn",           "uvicorn"),
    ("pydantic",          "pydantic"),
    ("python-multipart",  "multipart"),  # package name vs import name
]


def _is_importable(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def install_dependencies(requirements_file: str = "requirements.txt") -> None:
    info("Checking package dependencies ...")

    missing = []
    for pkg_name, import_name in REQUIRED_PACKAGES:
        if _is_importable(import_name):
            ok(f"{pkg_name}")
        else:
            warn(f"{pkg_name}  — NOT FOUND")
            missing.append(pkg_name)

    if missing:
        print()
        warn(f"Installing {len(missing)} missing package(s) ...")

        if os.path.isfile(requirements_file):
            cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file, "--quiet"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + missing

        try:
            subprocess.check_call(cmd)
            ok("All packages installed successfully")
        except subprocess.CalledProcessError as exc:
            err(f"pip install failed (exit {exc.returncode})")
            err("Please run:  pip install -r requirements.txt")
            sys.exit(1)
    else:
        ok("All required packages are already installed")


# ──────────────────────────────────────────────────────────
# STEP 4 – Create required directories
# ──────────────────────────────────────────────────────────
REQUIRED_DIRS = [
    "data/behavioral",   # stores JSON + CSV session dumps
    "logs",              # uvicorn / app logs
]


def create_directories() -> None:
    info("Setting up runtime directories ...")
    for directory in REQUIRED_DIRS:
        os.makedirs(directory, exist_ok=True)
        ok(f"'{directory}/' ready")


# ──────────────────────────────────────────────────────────
# STEP 5 – Validate backend package
# ──────────────────────────────────────────────────────────
def validate_backend_module(package_path: str = "backend/main.py") -> None:
    info("Validating backend package ...")

    if not os.path.isfile(package_path):
        err(f"'{package_path}' not found in the current directory")
        err("Make sure you run this script from the project root (d:/BEHAVE SEC/)")
        sys.exit(1)

    ok(f"'backend/' package found and readable")


# ──────────────────────────────────────────────────────────
# STEP 6 – Launch the server
# ──────────────────────────────────────────────────────────
def launch_server(host: str, port: int, reload: bool, workers: int) -> None:
    print()
    print(f"{BOLD}{CYAN}" + "=" * 60 + RESET)
    print(f"  {BOLD}Launching BEHAVE-SEC Backend Server{RESET}")
    print(f"{CYAN}" + "=" * 60 + RESET)
    print(f"  Server URL  :  http://{host}:{port}")
    print(f"  Swagger UI  :  http://{host}:{port}/docs")
    print(f"  ReDoc       :  http://{host}:{port}/redoc")
    print(f"  Data Dir    :  ./data/behavioral/")
    print(f"  Hot-Reload  :  {'enabled' if reload else 'disabled'}")
    print(f"  Workers     :  {workers}")
    print(f"\n  Press  Ctrl+C  to stop the server")
    print(f"{CYAN}" + "=" * 60 + RESET + "\n")

    # Import uvicorn here (guaranteed installed by step 3)
    import uvicorn  # type: ignore[import-untyped]  # noqa: PLC0415

    if reload:
        # Reload mode requires the app to be specified as an import string
        uvicorn.run(
            "backend.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
        )
    else:
        uvicorn.run(
            "backend.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info",
        )


# ──────────────────────────────────────────────────────────
# CLI argument parsing
# ──────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BEHAVE-SEC Backend Initializer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python init_backend.py\n"
            "  python init_backend.py --port 9000\n"
            "  python init_backend.py --reload\n"
            "  python init_backend.py --host 0.0.0.0 --port 8080 --workers 4\n"
        ),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("BACKEND_HOST", "0.0.0.0"),
        help="Host address to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BACKEND_PORT", "8000")),
        help="Port number (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable hot-reload on code changes (dev only)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("BACKEND_WORKERS", "1")),
        help="Number of worker processes (default: 1; ignored with --reload)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        default=False,
        help="Skip the dependency installation step",
    )
    return parser.parse_args()


# ──────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Always run from the script's own directory so relative
    # paths (behavioral_data/, backend_api.py, .env) work correctly.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    sys.path.insert(0, script_dir)

    banner()
    args = parse_args()

    check_python_version()
    load_dotenv()

    if not args.skip_install:
        install_dependencies()
    else:
        info("Dependency install step skipped (--skip-install)")

    create_directories()
    validate_backend_module()   # checks backend/main.py exists

    launch_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )
