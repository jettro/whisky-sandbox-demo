import asyncio

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from whisky_sandbox_demo.hybrid import code_toolset, path_trace
from whisky_sandbox_demo.tools import DOMAIN_TOOL_NAMES, DOMAIN_TOOLS


def test_tools_are_offered_directly_and_in_run_code():
    seen: list[str] = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        seen.extend(t.name for t in info.function_tools)
        return ModelResponse(parts=[TextPart("ok")])

    run_code = code_toolset(DOMAIN_TOOLS, max_tool_calls=5, resource_limits={})
    agent = Agent(FunctionModel(model), tools=list(DOMAIN_TOOLS), toolsets=[run_code])
    asyncio.run(agent.run("hi"))
    assert sorted(seen) == sorted([*DOMAIN_TOOL_NAMES, "run_code"])


def test_path_trace_classifies_each_response():
    snippet = "offers = await get_supplier_offers('s1', ids)\ntotal = sum(o.price_cents for o in x)"
    messages = [
        ModelRequest.user_text_prompt("plan"),
        ModelResponse(parts=[ToolCallPart("get_tasting_brief", {})]),
        ModelResponse(
            parts=[ToolCallPart("search_whiskies", {}), ToolCallPart("run_code", {"code": "1"})]
        ),
        ModelResponse(parts=[ToolCallPart("run_code", {"code": snippet})]),
        ModelResponse(parts=[ToolCallPart("final_result", {})]),
    ]
    path = path_trace(messages, [snippet])
    assert path.routes == "direct > mixed > code > output"
    assert path.first_code_step == 2
    assert (path.direct_calls, path.run_code_calls) == (2, 2)
    assert path.money_arithmetic_in_code


def test_fetch_only_snippet_is_not_money_arithmetic():
    path = path_trace([], ["brief = await get_tasting_brief()\nprint(brief)"])
    assert not path.money_arithmetic_in_code
