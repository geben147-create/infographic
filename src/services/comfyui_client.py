"""
ComfyUI WebSocket image generation client.

Connects to a running ComfyUI instance via WebSocket, submits a prompt
workflow, waits for completion, then fetches the generated image via HTTP.

Supports two workflow modes:
- SDXL checkpoint (CheckpointLoaderSimple)
- Z-Image Turbo GGUF (UnetLoaderGGUF + CLIPLoader + VAELoader)
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
from typing import Any

import httpx
import websocket  # websocket-client package

from src.models.provider import ImageProvider


# ── SDXL Checkpoint workflow ──
_SDXL_WORKFLOW: dict[str, Any] = {
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["10", 1],
            "text": "__PROMPT__",
        },
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["10", 1],
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
            "cfg": 1,
            "denoise": 1.0,
            "latent_image": ["14", 0],
            "model": ["10", 0],
            "negative": ["6", 0],
            "positive": ["4", 0],
            "sampler_name": "euler_ancestral",
            "scheduler": "karras",
            "seed": 0,
            "steps": 1,
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

# ── Z-Image Turbo workflow ──
# Official Comfy-Org template: UNETLoader + CLIPLoader(lumina2) + VAELoader,
# ModelSamplingAuraFlow(shift=3), ConditioningZeroOut for negative,
# KSampler(res_multistep/simple), EmptySD3LatentImage
_ZIMAGE_WORKFLOW: dict[str, Any] = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "__UNET_NAME__",
            "weight_dtype": "default",
        },
    },
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "__CLIP_NAME__",
            "type": "lumina2",
        },
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "__VAE_NAME__",
        },
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": "__PROMPT__",
        },
    },
    "5": {
        "class_type": "ConditioningZeroOut",
        "inputs": {
            "conditioning": ["4", 0],
        },
    },
    "6": {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {
            "model": ["1", 0],
            "shift": 3,
        },
    },
    "7": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {
            "batch_size": 1,
            "height": 1024,
            "width": 1024,
        },
    },
    "8": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 1.0,
            "denoise": 1.0,
            "latent_image": ["7", 0],
            "model": ["6", 0],
            "negative": ["5", 0],
            "positive": ["4", 0],
            "sampler_name": "res_multistep",
            "scheduler": "simple",
            "seed": 0,
            "steps": 8,
        },
    },
    "9": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["8", 0],
            "vae": ["3", 0],
        },
    },
    "10": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "zimage_output",
            "images": ["9", 0],
        },
    },
}


def _build_sdxl_workflow(
    prompt: str,
    negative_prompt: str,
    checkpoint: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Return an SDXL workflow dict with user values patched in."""
    workflow = json.loads(json.dumps(_SDXL_WORKFLOW))
    workflow["4"]["inputs"]["text"] = prompt
    workflow["6"]["inputs"]["text"] = negative_prompt
    workflow["10"]["inputs"]["ckpt_name"] = checkpoint
    workflow["14"]["inputs"]["width"] = width
    workflow["14"]["inputs"]["height"] = height
    return workflow


def _build_zimage_workflow(
    prompt: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Return a Z-Image Turbo workflow dict."""
    workflow = json.loads(json.dumps(_ZIMAGE_WORKFLOW))
    workflow["1"]["inputs"]["unet_name"] = unet_name
    workflow["2"]["inputs"]["clip_name"] = clip_name
    workflow["3"]["inputs"]["vae_name"] = vae_name
    workflow["4"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["width"] = width
    workflow["7"]["inputs"]["height"] = height
    workflow["8"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
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
        workflow = _build_sdxl_workflow(
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


def _run_comfyui_zimage_sync(
    base_url: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    width: int,
    height: int,
) -> bytes:
    """Synchronous ComfyUI interaction for Z-Image Turbo workflow."""
    client_id = str(uuid.uuid4())
    host = base_url.replace("http://", "").replace("https://", "")
    ws_url = f"ws://{host}/ws?clientId={client_id}"

    ws = websocket.create_connection(ws_url)
    ws.settimeout(180)

    try:
        workflow = _build_zimage_workflow(
            prompt=prompt,
            unet_name=unet_name,
            clip_name=clip_name,
            vae_name=vae_name,
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

        output_images: list[dict[str, Any]] = []
        while True:
            raw = ws.recv()
            if isinstance(raw, bytes):
                continue
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

    if not output_images:
        history_resp = httpx.get(f"{base_url}/history/{prompt_id}", timeout=30.0)
        history_resp.raise_for_status()
        history = history_resp.json()
        images = []
        for _node_id, node_out in history.get(prompt_id, {}).get("outputs", {}).items():
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
    """ImageProvider implementation using ComfyUI's WebSocket API (SDXL checkpoint)."""

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
        """Generate an image via ComfyUI SDXL workflow."""
        return await asyncio.to_thread(
            _run_comfyui_sync,
            self._base_url,
            self._checkpoint,
            prompt,
            negative_prompt,
            width,
            height,
        )


class ComfyUIZImageProvider(ImageProvider):
    """ImageProvider for Z-Image Turbo via ComfyUI."""

    def __init__(
        self,
        base_url: str,
        unet_name: str = "z_image_turbo_bf16.safetensors",
        clip_name: str = "qwen_3_4b.safetensors",
        vae_name: str = "ae.safetensors",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._unet_name = unet_name
        self._clip_name = clip_name
        self._vae_name = vae_name

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """Generate an image via ComfyUI Z-Image Turbo workflow."""
        return await asyncio.to_thread(
            _run_comfyui_zimage_sync,
            self._base_url,
            self._unet_name,
            self._clip_name,
            self._vae_name,
            prompt,
            width,
            height,
        )
