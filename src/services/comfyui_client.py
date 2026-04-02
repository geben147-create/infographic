"""
ComfyUI WebSocket image generation client.

Connects to a running ComfyUI instance via WebSocket, submits a prompt
workflow, waits for completion, then fetches the generated image via HTTP.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx
import websocket  # websocket-client package

from src.models.provider import ImageProvider


# Minimal SDXL base workflow template.
# Node 4 = CLIPTextEncode (positive), Node 6 = CLIPTextEncode (negative),
# Node 4's inputs.text is patched with the user prompt at runtime.
_BASE_WORKFLOW: dict[str, Any] = {
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["10", 0],
            "text": "__PROMPT__",
        },
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["10", 0],
            "text": "__NEGATIVE__",
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["13", 0],
            "vae": ["10", 2],
        },
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "gsd_output",
            "images": ["8", 0],
        },
    },
    "10": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "__CHECKPOINT__",
        },
    },
    "13": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 7,
            "denoise": 1.0,
            "latent_image": ["14", 0],
            "model": ["10", 0],
            "negative": ["6", 0],
            "positive": ["4", 0],
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 0,
            "steps": 20,
        },
    },
    "14": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "batch_size": 1,
            "height": 1024,
            "width": 1024,
        },
    },
}


def _build_workflow(
    prompt: str,
    negative_prompt: str,
    checkpoint: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Return a workflow dict with user values patched in."""
    workflow = json.loads(json.dumps(_BASE_WORKFLOW))  # deep copy
    workflow["4"]["inputs"]["text"] = prompt
    workflow["6"]["inputs"]["text"] = negative_prompt
    workflow["10"]["inputs"]["ckpt_name"] = checkpoint
    workflow["14"]["inputs"]["width"] = width
    workflow["14"]["inputs"]["height"] = height
    return workflow


def _run_comfyui_sync(
    base_url: str,
    checkpoint: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
) -> bytes:
    """Synchronous ComfyUI interaction (called via asyncio.to_thread).

    1. Open WebSocket for execution events.
    2. POST the workflow to /prompt.
    3. Wait for 'executing' event with node=None (signals completion).
    4. Fetch the generated image via /view.
    """
    client_id = str(uuid.uuid4())
    host = base_url.replace("http://", "").replace("https://", "")
    ws_url = f"ws://{host}/ws?clientId={client_id}"

    ws = websocket.create_connection(ws_url)
    ws.settimeout(120)

    try:
        workflow = _build_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            checkpoint=checkpoint,
            width=width,
            height=height,
        )

        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }
        resp = httpx.post(f"{base_url}/prompt", json=payload, timeout=30.0)
        resp.raise_for_status()
        prompt_id: str = resp.json()["prompt_id"]

        # Wait for completion signal
        output_images: list[dict[str, Any]] = []
        while True:
            raw = ws.recv()
            if isinstance(raw, bytes):
                continue  # skip binary preview frames
            msg = json.loads(raw)
            msg_type = msg.get("type")
            data = msg.get("data", {})

            if msg_type == "executing":
                if data.get("node") is None and data.get("prompt_id") == prompt_id:
                    break

            if msg_type == "executed":
                node_output = data.get("output", {})
                if "images" in node_output:
                    output_images.extend(node_output["images"])

    finally:
        ws.close()

    # Fetch the first output image
    if not output_images:
        # Fallback: fetch via history endpoint
        history_resp = httpx.get(f"{base_url}/history/{prompt_id}", timeout=30.0)
        history_resp.raise_for_status()
        history = history_resp.json()
        images = []
        for node_id, node_out in history.get(prompt_id, {}).get("outputs", {}).items():
            images.extend(node_out.get("images", []))
        output_images = images

    if not output_images:
        raise RuntimeError(f"ComfyUI returned no images for prompt_id={prompt_id}")

    image_info = output_images[0]
    params = {
        "filename": image_info["filename"],
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    }
    img_resp = httpx.get(f"{base_url}/view", params=params, timeout=60.0)
    img_resp.raise_for_status()
    return img_resp.content


class ComfyUIProvider(ImageProvider):
    """ImageProvider implementation using ComfyUI's WebSocket API."""

    def __init__(self, base_url: str, checkpoint: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._checkpoint = checkpoint

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """Generate an image via ComfyUI and return raw PNG bytes."""
        return await asyncio.to_thread(
            _run_comfyui_sync,
            self._base_url,
            self._checkpoint,
            prompt,
            negative_prompt,
            width,
            height,
        )
