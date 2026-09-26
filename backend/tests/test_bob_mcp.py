import asyncio
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import uvicorn

from codetwin.api import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_project_configuration_registers_review_tools_without_auto_approval():
    configuration = json.loads((PROJECT_ROOT / ".bob" / "mcp.json").read_text(encoding="utf-8"))
    server = configuration["mcpServers"]["codetwin"]
    assert server["command"] == "python"
    assert server["args"] == ["${workspaceFolder}/backend/run_bob_mcp.py"]
    assert server["alwaysAllow"] == []
    assert server["disabled"] is False

    rules = (PROJECT_ROOT / ".bob" / "rules-code" / "codetwin-impact-validation.md").read_text(encoding="utf-8")
    for tool_name in (
        "analyze_change",
        "get_analysis_context",
        "submit_bob_impact_review",
        "run_targeted_tests",
    ):
        assert tool_name in rules


def _object_result(result):
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                return decoded
    raise AssertionError("MCP tool did not return a structured object")


def test_ibm_bob_stdio_server_supports_review_and_test_workflow():
    backend_path = PROJECT_ROOT / "backend"
    server_path = backend_path / "run_bob_mcp.py"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(backend_path)

    async def workflow():
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            host, port = port_socket.getsockname()
        api_server = uvicorn.Server(uvicorn.Config(
            create_app(), host=host, port=port, log_level="critical", access_log=False
        ))
        api_thread = threading.Thread(target=api_server.run, daemon=True)
        api_thread.start()
        deadline = time.monotonic() + 10
        while not api_server.started and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert api_server.started, "Test FastAPI server did not start"

        environment["CODETWIN_API_BASE_URL"] = f"http://{host}:{port}"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(server_path)],
            cwd=str(PROJECT_ROOT),
            env=environment,
        )
        try:
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    tool_names = {tool.name for tool in listed.tools}
                    assert tool_names == {
                        "analyze_change",
                        "get_analysis_context",
                        "submit_bob_impact_review",
                        "run_targeted_tests",
                    }

                    created = await session.call_tool("analyze_change", {
                        "files": {
                            "app/main.py": "def run(): return 4\n",
                            "tests/test_main.py": "from app.main import run\ndef test_run(): assert run() == 4\n",
                            "app/other.py": "VALUE = 1\n",
                        },
                        "changed_files": ["app/main.py"],
                    })
                    assert not created.isError
                    analysis = _object_result(created)
                    analysis_id = analysis["analysis_id"]
                    assert analysis["status"] == "awaiting_bob_review"

                    context_result = await session.call_tool(
                        "get_analysis_context", {"analysis_id": analysis_id}
                    )
                    context = _object_result(context_result)
                    assert context["review_snapshot"]["app/main.py"] == "def run(): return 4\n"
                    predicted = context["predicted_impact"]["files"]
                    reviewed = await session.call_tool("submit_bob_impact_review", {
                        "analysis_id": analysis_id,
                        "confirmed_files": predicted,
                        "possible_files": [],
                        "not_affected_files": context["not_affected"],
                        "rationale": "Inspected the changed function, importing test, and isolated module in the captured snapshot.",
                    })
                    assert not reviewed.isError
                    result = await session.call_tool(
                        "run_targeted_tests", {"analysis_id": analysis_id}
                    )
                    validated = _object_result(result)
                    assert validated["test_results"]["passed"] is True, validated["test_results"]
                    assert validated["safe_to_merge"] is True
        finally:
            api_server.should_exit = True
            api_thread.join(timeout=5)

    asyncio.run(workflow())
