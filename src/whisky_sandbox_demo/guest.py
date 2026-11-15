"""Everything about the Smol guest VM used by demo 3.

The guest never gets network access. Its Python dependencies (matplotlib, reportlab) are
downloaded once on the host as Linux wheels (`scripts/prepare_guest_image.py`), copied into
each fresh VM and installed with `pip --no-index`.
"""

from __future__ import annotations

import platform
from pathlib import Path

from pydantic_ai.workspaces import WorkspaceBackend

GUEST_IMAGE = "python:3.12-slim"
GUEST_PACKAGES = ["matplotlib==3.10.*", "reportlab==4.*"]
WHEELHOUSE = Path("guest") / "wheels"
GUEST_WHEEL_DIR = "/opt/wheels"
VM_CPUS = 2
VM_MEMORY_MB = 1024

NETWORK_PROBE = """
import socket
try:
    socket.create_connection(("pypi.org", 443), timeout=3)
    print("open")
except OSError:
    print("closed")
"""


def guest_arch() -> str:
    """The VM runs the host's CPU architecture."""
    return {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64", "AMD64": "x86_64"}[
        platform.machine()
    ]


def wheel_files() -> list[Path]:
    wheels = sorted(WHEELHOUSE.glob("*.whl"))
    if not wheels:
        raise FileNotFoundError(
            f"No wheels in {WHEELHOUSE}/. Run: uv run python scripts/prepare_guest_image.py"
        )
    return wheels


async def install_guest_packages(backend) -> float:
    """Copy the wheelhouse into the VM and install offline. Returns seconds spent.

    `backend` is a `SmolSandboxBackend`; the copy uses the smol SDK's `write_file`, which moves
    a whole file per call (the generic workspace API moves 64 KiB per command).
    """
    import time

    start = time.perf_counter()
    machine = await backend.get_sandbox()
    await machine.exec(["mkdir", "-p", GUEST_WHEEL_DIR])
    for wheel in wheel_files():
        await machine.write_file(f"{GUEST_WHEEL_DIR}/{wheel.name}", wheel.read_bytes())
    result = await backend.run(
        [
            "pip",
            "install",
            "--no-index",
            "--find-links",
            GUEST_WHEEL_DIR,
            "--disable-pip-version-check",
            "--root-user-action=ignore",
            "--quiet",
            *GUEST_PACKAGES,
        ],
        timeout=300,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"Offline pip install in the guest failed:\n{result.stderr[-2000:]}")
    return time.perf_counter() - start


async def guest_network_closed(backend: WorkspaceBackend) -> bool:
    result = await backend.run(["python", "-c", NETWORK_PROBE], timeout=20)
    return result.stdout.strip() == "closed"
