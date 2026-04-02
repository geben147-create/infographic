"""
Script generation Temporal activity.

Generates a full video script from a topic + channel config using the
Ollama LLM provider. The script is validated against the Script Pydantic
model and saved as JSON to the pipeline run directory.
"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel
from temporalio import activity

from src.config import settings
from src.models.channel_config import load_channel_config
from src.models.provider import ModelSpec, ProviderType
from src.models.script import Script
from src.services.ollama_client import OllamaProvider


class ScriptGenInput(BaseModel):
    """Input parameters for the generate_script activity."""

    topic: str
    channel_id: str
    run_dir: str


class ScriptGenOutput(BaseModel):
    """Output from the generate_script activity."""

    script: Script
    file_path: str


# JSON Schema for the Script model — used for Ollama structured output mode.
_SCRIPT_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["title", "description", "tags", "scenes"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["narration", "image_prompt", "duration_seconds"],
                "properties": {
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                },
            },
        },
    },
}


@activity.defn
async def generate_script(params: ScriptGenInput) -> ScriptGenOutput:
    """Generate a video script from a topic using Ollama.

    Steps:
    1. Load channel config for the given channel_id.
    2. Parse the LLM model spec from config (e.g. "local:qwen3:14b").
    3. Create the appropriate LLM provider.
    4. Render the Jinja2 prompt template with topic + channel metadata.
    5. Call provider.generate() with the JSON schema format constraint.
    6. Validate the response as a Script model.
    7. Save the script to {run_dir}/scripts/script.json.

    Args:
        params: ScriptGenInput with topic, channel_id, and run_dir.

    Returns:
        ScriptGenOutput with validated Script and file_path.

    Raises:
        ValueError: If the LLM returns invalid JSON (not a valid Script).
        NotImplementedError: If the channel's llm_model uses a non-local provider.
    """
    config = load_channel_config(params.channel_id)
    spec = ModelSpec.parse(config.llm_model)

    if spec.provider != ProviderType.local:
        raise NotImplementedError(
            f"LLM provider '{spec.provider}' is not yet implemented. "
            "Only 'local' (Ollama) providers are supported in Plan 03. "
            "Cloud LLM providers will be added in Plan 07."
        )

    provider = OllamaProvider(
        base_url=settings.ollama_url,
        model=spec.model,
    )

    # Render Jinja2 template
    templates_dir = str(settings.prompt_templates_dir)
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,
        autoescape=False,
    )
    template = env.get_template(config.prompt_template)
    rendered_prompt = template.render(
        topic=params.topic,
        niche=config.niche,
        tags=config.tags,
    )

    # Call LLM
    raw_response = await provider.generate(
        prompt=rendered_prompt,
        system="Respond ONLY with valid JSON. No markdown, no explanations.",
        format_schema=_SCRIPT_JSON_SCHEMA,
    )

    # Validate JSON → Script model
    try:
        script = Script.model_validate_json(raw_response)
    except Exception as exc:
        raise ValueError(
            f"LLM returned invalid JSON that could not be parsed as a Script. "
            f"Raw response (first 200 chars): {raw_response[:200]!r}. "
            f"Parse error: {exc}"
        ) from exc

    # Save to run directory
    script_path = Path(params.run_dir) / "scripts" / "script.json"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        json.dumps(json.loads(script.model_dump_json()), indent=2),
        encoding="utf-8",
    )

    return ScriptGenOutput(script=script, file_path=str(script_path))
