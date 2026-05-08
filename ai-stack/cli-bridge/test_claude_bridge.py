import asyncio
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "claude_bridge.py"
SPEC = importlib.util.spec_from_file_location("claude_bridge_under_test", MODULE_PATH)
claude_bridge = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(claude_bridge)


def test_call_codex_uses_workspace_and_output_file(monkeypatch, tmp_path):
    output_text = "artifact-backed codex response"
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

        def kill(self):
            return None

    async def fake_create_subprocess_exec(*cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        output_index = cmd.index("--output-last-message") + 1
        Path(cmd[output_index]).write_text(output_text, encoding="utf-8")
        return FakeProc()

    monkeypatch.setattr(claude_bridge, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(claude_bridge.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        claude_bridge._call_codex(
            [
                {"role": "system", "content": "Write the requested artifact to the repo."},
                {"role": "user", "content": "Create the module classification map."},
            ]
        )
    )

    assert result == output_text
    assert "--cd" in captured["cmd"]
    assert str(tmp_path) in captured["cmd"]
    assert "--output-last-message" in captured["cmd"]
    prompt = captured["cmd"][-1]
    assert "System instructions:" in prompt
    assert "Write the requested artifact to the repo." in prompt
    assert "Create the module classification map." in prompt
    assert captured["cwd"] == str(tmp_path)
