"""Optional live checks. Run with: uv run pytest -m integration

They need OPENAI_API_KEY (model) or a host that can run smol VMs plus the prepared wheelhouse.
Each is skipped when its prerequisite is missing.
"""

import asyncio
import os

import pytest

from whisky_sandbox_demo import config, guest

pytestmark = pytest.mark.integration


def _smol_ready() -> bool:
    try:
        import smol
    except ImportError:
        return False
    return smol.local_availability()[0] and guest.WHEELHOUSE.exists()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
@pytest.mark.parametrize("use_code_mode", [False, True])
def test_planning_agent_produces_a_valid_plan(use_code_mode):
    from pydantic_ai_harness import CodeMode

    from whisky_sandbox_demo.demos._runner import build_planning_agent
    from whisky_sandbox_demo.prompts import TASK
    from whisky_sandbox_demo.validation import validate_plan

    agent = build_planning_agent([CodeMode()] if use_code_mode else [])
    result = agent.run_sync(TASK)
    report = validate_plan(result.output)
    assert report.valid, report.failed


@pytest.mark.skipif(not _smol_ready(), reason="no smol VM support or wheelhouse missing")
def test_guest_vm_is_offline_and_has_report_libraries():
    from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend

    async def check():
        backend = SmolSandboxBackend(image=guest.GUEST_IMAGE, allow_internet_access=False)
        try:
            await guest.install_guest_packages(backend)
            result = await backend.run(["python", "-c", "import matplotlib, reportlab"], timeout=60)
            assert result.exit_code == 0, result.stderr
            assert await guest.guest_network_closed(backend)
            env = await backend.run(["env"], timeout=10)
            assert "OPENAI" not in env.stdout
        finally:
            if backend.ref is not None:
                await SmolSandbox().destroy(backend.ref)

    asyncio.run(check())


def test_model_name_gets_provider_prefix(monkeypatch):
    monkeypatch.setenv("DEMO_MODEL", "some-model")
    assert config.get_agent_model() == "openai:some-model"
