"""Prepare the guest dependencies for demo 3, once.

1. Downloads Linux wheels for matplotlib and reportlab (and their dependencies) from PyPI
   into guest/wheels/, for the VM's architecture and Python 3.12.
2. Checks the result: boots a throwaway VM from python:3.12-slim with networking OFF,
   installs the wheels offline, imports both libraries, confirms there is no network,
   and deletes the VM.

    uv run python scripts/prepare_guest_image.py

The guest never needs network access: the download happens on the host.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import time

import smol
from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend

from whisky_sandbox_demo import guest


def download_wheels() -> None:
    arch = guest.guest_arch()
    guest.WHEELHOUSE.mkdir(parents=True, exist_ok=True)
    platforms = [f"manylinux_2_{minor}_{arch}" for minor in (17, 24, 26, 27, 28)]
    platforms.append(f"manylinux2014_{arch}")
    cmd = [
        "uvx",
        "pip",
        "download",
        "--quiet",
        "--only-binary=:all:",
        "--python-version",
        "3.12",
        "--dest",
        str(guest.WHEELHOUSE),
        *[arg for p in platforms for arg in ("--platform", p)],
        *guest.GUEST_PACKAGES,
    ]
    if shutil.which("uvx") is None:
        raise SystemExit("uvx not found; install uv first.")
    print(f"Downloading {', '.join(guest.GUEST_PACKAGES)} wheels for linux/{arch}...")
    subprocess.run(cmd, check=True)
    wheels = guest.wheel_files()
    size_mb = sum(w.stat().st_size for w in wheels) / 1e6
    print(f"  {len(wheels)} wheels, {size_mb:.1f} MB in {guest.WHEELHOUSE}/")


async def verify_in_vm() -> None:
    backend = SmolSandboxBackend(
        image=guest.GUEST_IMAGE,
        cpus=guest.VM_CPUS,
        memory_mb=guest.VM_MEMORY_MB,
        allow_internet_access=False,
    )
    start = time.perf_counter()
    try:
        seconds = await guest.install_guest_packages(backend)
        print(f"  offline install in a fresh VM took {seconds:.1f}s")
        result = await backend.run(
            [
                "python",
                "-c",
                "import matplotlib, reportlab; print(matplotlib.__version__, reportlab.Version)",
            ],
            timeout=60,
        )
        print(f"  guest imports: matplotlib/reportlab {result.stdout.strip()}")
        if not await guest.guest_network_closed(backend):
            raise SystemExit("The guest unexpectedly has network access.")
        print("  guest network: closed")
    finally:
        if backend.ref is not None:
            await SmolSandbox().destroy(backend.ref)
    print(f"Verified in {time.perf_counter() - start:.1f}s (VM deleted).")


def main() -> int:
    ok, code, detail = smol.local_availability()
    download_wheels()
    if not ok:
        print(f"Wheels downloaded, but this host cannot run smol VMs ({code}: {detail}).")
        return 1
    print(f"Checking in a network-less {guest.GUEST_IMAGE} VM (first run pulls the image)...")
    asyncio.run(verify_in_vm())
    return 0


if __name__ == "__main__":
    sys.exit(main())
