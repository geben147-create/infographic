"""
Ollama LLM client — implements LLMProvider ABC for local Qwen3 inference.

The Ollama server exposes an OpenAI-compatible API plus its native /api/generate
endpoint. We use the native endpoint for structured JSON output via the `format`
field (JSON Schema mode), which ensures the model responds with valid JSON.
"""
from __future__ import annotations

import httpx

from src.models.provider import LLMProvider


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama server.

    Args:
        base_url: Base URL of the Ollama server (e.g. "http://localhost:11434").
        model: Model name as registered in Ollama (e.g. "qwen3:14b").
    """

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(
        self,
        prompt: str,
        system: str = "",
        format_schema: dict | None = None,
    ) -> str:
        """Generate text via Ollama /api/generate.

        Posts to {base_url}/api/generate with stream=False.
        When format_schema is provided it is passed as the 'format' field,
        enabling Ollama's JSON Schema structured-output mode.

        Markdown code fences (```json or ```) are stripped from the response
        before returning so callers always receive plain text / JSON.

        Args:
            prompt: User prompt sent to the model.
            system: System instruction appended to the Ollama request.
            format_schema: Optional JSON Schema dict for structured output.

        Returns:
            Cleaned response text with markdown fences stripped.

        Raises:
            httpx.HTTPStatusError: On non-2xx response from Ollama.
        """
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        if format_schema is not None:
            body["format"] = format_schema

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=body,
            )
            response.raise_for_status()

        raw: str = response.json()["response"]
        return self._strip_fences(raw)

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences from LLM response.

        Handles:
        - ```json\\n...\\n```
        - ```\\n...\\n```
        """
        stripped = text.strip()

        # Remove opening fence (```json or ```)
        if stripped.startswith("```json"):
            stripped = stripped[len("```json"):]
        elif stripped.startswith("```"):
            stripped = stripped[len("```"):]

        # Remove closing fence
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]

        return stripped.strip()
