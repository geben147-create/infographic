"""
Tests for script generation activity and Ollama LLM provider.

TDD RED phase — these tests are written before implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — minimal valid Script JSON
# ---------------------------------------------------------------------------

VALID_SCRIPT_JSON = json.dumps(
    {
        "title": "테스트 제목",
        "description": "테스트 설명입니다.",
        "tags": ["태그1", "태그2"],
        "scenes": [
            {
                "narration": "첫 번째 장면 내레이션입니다.",
                "image_prompt": "A beautiful sunrise over mountains",
                "duration_seconds": 8.0,
            }
        ],
    }
)


# ---------------------------------------------------------------------------
# OllamaProvider tests
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    """Test OllamaProvider LLM client."""

    @pytest.mark.asyncio
    async def test_generate_posts_to_api_generate(self):
        """OllamaProvider.generate() POSTs to /api/generate with correct body."""
        from src.services.ollama_client import OllamaProvider

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": VALID_SCRIPT_JSON}

        mock_post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient.post", mock_post):
            provider = OllamaProvider(
                base_url="http://localhost:11434", model="qwen3:14b"
            )
            result = await provider.generate(
                prompt="Test prompt",
                system="Respond with JSON only.",
                format_schema={"type": "object"},
            )

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", call_args[0][0])
        assert "/api/generate" in str(url)

        body = call_args[1].get("json") or (call_args[0][1] if len(call_args[0]) > 1 else None)
        if body is None and call_args[0]:
            body = call_args[0][1] if len(call_args[0]) > 1 else None
        # Allow body to be in kwargs
        if body is None:
            body = call_args.kwargs.get("json")
        assert body is not None
        assert body["model"] == "qwen3:14b"
        assert body["stream"] is False
        assert body["format"] == {"type": "object"}
        assert result == VALID_SCRIPT_JSON

    @pytest.mark.asyncio
    async def test_generate_strips_markdown_json_fences(self):
        """OllamaProvider strips ```json ... ``` fences from response."""
        from src.services.ollama_client import OllamaProvider

        fenced = f"```json\n{VALID_SCRIPT_JSON}\n```"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": fenced}

        mock_post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient.post", mock_post):
            provider = OllamaProvider(
                base_url="http://localhost:11434", model="qwen3:14b"
            )
            result = await provider.generate(prompt="Test", system="")

        # Fences must be stripped — result is plain JSON
        assert result.strip().startswith("{")
        assert "```" not in result

    @pytest.mark.asyncio
    async def test_generate_strips_plain_code_fences(self):
        """OllamaProvider strips plain ``` fences from response."""
        from src.services.ollama_client import OllamaProvider

        fenced = f"```\n{VALID_SCRIPT_JSON}\n```"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": fenced}

        with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
            provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:14b")
            result = await provider.generate(prompt="Test", system="")

        assert "```" not in result
        assert result.strip().startswith("{")

    @pytest.mark.asyncio
    async def test_generate_without_format_schema_omits_format_key(self):
        """When format_schema is None, 'format' key is NOT sent in request body."""
        from src.services.ollama_client import OllamaProvider

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "hello"}

        mock_post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient.post", mock_post):
            provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:14b")
            await provider.generate(prompt="Test", system="")

        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        if body is None and mock_post.call_args[0]:
            body = mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else None
        assert "format" not in (body or {})


# ---------------------------------------------------------------------------
# generate_script activity tests
# ---------------------------------------------------------------------------


class TestGenerateScriptActivity:
    """Test generate_script Temporal activity."""

    @pytest.fixture
    def channel_config_yaml(self, tmp_path) -> Path:
        """Create a minimal channel config YAML for testing."""
        config_dir = tmp_path / "channel_configs"
        config_dir.mkdir()
        yaml_content = """\
channel_id: test_ch
niche: 금융
language: ko
llm_model: "local:qwen3:14b"
prompt_template: script_default.j2
tags:
  - 투자
  - 금융
"""
        (config_dir / "test_ch.yaml").write_text(yaml_content, encoding="utf-8")
        return config_dir

    @pytest.mark.asyncio
    async def test_activity_loads_channel_config_and_renders_template(
        self, tmp_path, channel_config_yaml
    ):
        """generate_script loads channel config, renders template, calls LLM."""
        from src.activities.script_gen import ScriptGenInput, generate_script

        run_dir = tmp_path / "run001"
        run_dir.mkdir()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": VALID_SCRIPT_JSON}

        with (
            patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.config.settings.prompt_templates_dir",
                "src/prompt_templates",
            ),
        ):
            params = ScriptGenInput(
                topic="비트코인 투자 방법",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_script(params)

        assert output.script.title == "테스트 제목"
        assert len(output.script.scenes) == 1

    @pytest.mark.asyncio
    async def test_activity_saves_script_json_to_run_dir(self, tmp_path):
        """generate_script saves script.json to {run_dir}/scripts/script.json."""
        from src.activities.script_gen import ScriptGenInput, generate_script

        run_dir = tmp_path / "run002"
        (run_dir / "scripts").mkdir(parents=True)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": VALID_SCRIPT_JSON}

        with (
            patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.config.settings.prompt_templates_dir",
                "src/prompt_templates",
            ),
        ):
            params = ScriptGenInput(
                topic="테스트 토픽",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_script(params)

        script_path = run_dir / "scripts" / "script.json"
        assert script_path.exists(), "script.json was not written"
        assert output.file_path == str(script_path)

        saved = json.loads(script_path.read_text(encoding="utf-8"))
        assert saved["title"] == "테스트 제목"

    @pytest.mark.asyncio
    async def test_activity_returns_script_gen_output(self, tmp_path):
        """generate_script returns ScriptGenOutput with script and file_path."""
        from src.activities.script_gen import ScriptGenInput, ScriptGenOutput, generate_script

        run_dir = tmp_path / "run003"
        (run_dir / "scripts").mkdir(parents=True)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": VALID_SCRIPT_JSON}

        with (
            patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.config.settings.prompt_templates_dir",
                "src/prompt_templates",
            ),
        ):
            params = ScriptGenInput(
                topic="테스트 토픽",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            output = await generate_script(params)

        assert isinstance(output, ScriptGenOutput)
        assert output.script is not None
        assert output.file_path.endswith("script.json")

    @pytest.mark.asyncio
    async def test_activity_raises_value_error_on_invalid_json(self, tmp_path):
        """generate_script raises ValueError with a descriptive message on LLM returning invalid JSON."""
        from src.activities.script_gen import ScriptGenInput, generate_script

        run_dir = tmp_path / "run004"
        (run_dir / "scripts").mkdir(parents=True)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "This is not JSON at all!"}

        with (
            patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.config.settings.prompt_templates_dir",
                "src/prompt_templates",
            ),
        ):
            params = ScriptGenInput(
                topic="테스트 토픽",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            with pytest.raises(ValueError, match="LLM returned invalid JSON"):
                await generate_script(params)

    @pytest.mark.asyncio
    async def test_topic_injected_into_rendered_prompt(self, tmp_path):
        """The topic is injected into the rendered Jinja2 prompt sent to Ollama."""
        from src.activities.script_gen import ScriptGenInput, generate_script

        run_dir = tmp_path / "run005"
        (run_dir / "scripts").mkdir(parents=True)

        captured_body = {}

        async def mock_post(self_or_url, url_or_nothing=None, **kwargs):
            # httpx.AsyncClient.post is called as client.post(url, json=...)
            # When patching the method, self is the first arg
            body = kwargs.get("json", {})
            captured_body.update(body)
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"response": VALID_SCRIPT_JSON}
            return resp

        with (
            patch("httpx.AsyncClient.post", mock_post),
            patch(
                "src.activities.script_gen.load_channel_config",
                return_value=_make_channel_config("test_ch"),
            ),
            patch(
                "src.config.settings.prompt_templates_dir",
                "src/prompt_templates",
            ),
        ):
            params = ScriptGenInput(
                topic="암호화폐 투자 전략",
                channel_id="test_ch",
                run_dir=str(run_dir),
            )
            await generate_script(params)

        assert "암호화폐 투자 전략" in captured_body.get("prompt", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_channel_config(channel_id: str):
    """Create a minimal ChannelConfig for testing."""
    from src.models.channel_config import ChannelConfig

    return ChannelConfig(
        channel_id=channel_id,
        niche="금융",
        language="ko",
        llm_model="local:qwen3:14b",
        prompt_template="script_default.j2",
        tags=["투자", "금융"],
    )
