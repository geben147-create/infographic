"""
Script data models — the output contract from the LLM script generation step.

Script and ScriptScene define the pipeline's internal data contract.
They are produced by the script activity and consumed by image/TTS/video activities.
"""
from pydantic import BaseModel


class ScriptScene(BaseModel):
    """A single scene in the generated video script."""

    narration: str
    image_prompt: str
    duration_seconds: float


class Script(BaseModel):
    """Full video script produced by the LLM generation activity."""

    title: str
    description: str
    tags: list[str]
    scenes: list[ScriptScene]
