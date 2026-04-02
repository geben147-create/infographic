"""
Channel management API endpoints.

Reads channel configurations from YAML files and exposes them via REST.
  GET /api/channels           — list all channel configs
  GET /api/channels/{id}      — single channel config with run stats
"""
from __future__ import annotations

import pathlib
from typing import Generator

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from src.models.channel_config import ChannelConfig, load_channel_config
from src.models.pipeline_run import PipelineRun
from src.services.db_service import engine

router = APIRouter(prefix="/api/channels")


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


class ChannelResponse(BaseModel):
    channel_id: str
    niche: str
    language: str
    video_model: str
    image_model: str
    tts_model: str
    llm_model: str
    sdxl_checkpoint: str
    tts_voice_reference: str
    prompt_template: str
    thumbnail_style: str
    tags: list[str]
    vgen_enabled: bool
    quality_gate_enabled: bool
    publish_status: str
    category_id: str


class ChannelWithStats(ChannelResponse):
    total_runs: int = 0
    success_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    avg_cost_usd: float = 0.0


class ChannelListResponse(BaseModel):
    channels: list[ChannelWithStats]
    total: int


def _config_to_response(config: ChannelConfig) -> ChannelResponse:
    return ChannelResponse(
        channel_id=config.channel_id,
        niche=config.niche,
        language=config.language,
        video_model=config.video_model,
        image_model=config.image_model,
        tts_model=config.tts_model,
        llm_model=config.llm_model,
        sdxl_checkpoint=config.sdxl_checkpoint,
        tts_voice_reference=config.tts_voice_reference,
        prompt_template=config.prompt_template,
        thumbnail_style=config.thumbnail_style,
        tags=list(config.tags),
        vgen_enabled=config.vgen_enabled,
        quality_gate_enabled=config.quality_gate_enabled,
        publish_status=config.publish_status,
        category_id=config.category_id,
    )


def _list_channel_ids(config_dir: str = "src/channel_configs") -> list[str]:
    config_path = pathlib.Path(config_dir)
    if not config_path.exists():
        return []
    return sorted(
        p.stem for p in config_path.glob("*.yaml")
    )


@router.get("", response_model=ChannelListResponse)
def list_channels(
    session: Session = Depends(get_db_session),
) -> ChannelListResponse:
    channel_ids = _list_channel_ids()
    channels: list[ChannelWithStats] = []

    for cid in channel_ids:
        try:
            config = load_channel_config(cid)
        except Exception:
            continue

        base = _config_to_response(config)

        # Query run stats
        total = session.exec(
            select(func.count()).select_from(PipelineRun).where(
                PipelineRun.channel_id == cid
            )
        ).one()
        success = session.exec(
            select(func.count()).select_from(PipelineRun).where(
                PipelineRun.channel_id == cid,
                PipelineRun.status.in_(["completed", "ready_to_upload"]),  # type: ignore[union-attr]
            )
        ).one()
        failed = session.exec(
            select(func.count()).select_from(PipelineRun).where(
                PipelineRun.channel_id == cid,
                PipelineRun.status == "failed",
            )
        ).one()
        avg_cost = session.exec(
            select(func.avg(PipelineRun.total_cost_usd)).where(
                PipelineRun.channel_id == cid,
                PipelineRun.total_cost_usd.is_not(None),  # type: ignore[union-attr]
            )
        ).one()

        channels.append(
            ChannelWithStats(
                **base.model_dump(),
                total_runs=total,
                success_count=success,
                failed_count=failed,
                success_rate=round(success / total * 100, 1) if total > 0 else 0.0,
                avg_cost_usd=round(avg_cost or 0.0, 4),
            )
        )

    return ChannelListResponse(channels=channels, total=len(channels))


@router.get("/{channel_id}", response_model=ChannelWithStats)
def get_channel(
    channel_id: str,
    session: Session = Depends(get_db_session),
) -> ChannelWithStats:
    try:
        config = load_channel_config(channel_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel_id}")

    base = _config_to_response(config)

    total = session.exec(
        select(func.count()).select_from(PipelineRun).where(
            PipelineRun.channel_id == channel_id
        )
    ).one()
    success = session.exec(
        select(func.count()).select_from(PipelineRun).where(
            PipelineRun.channel_id == channel_id,
            PipelineRun.status.in_(["completed", "ready_to_upload"]),  # type: ignore[union-attr]
        )
    ).one()
    failed = session.exec(
        select(func.count()).select_from(PipelineRun).where(
            PipelineRun.channel_id == channel_id,
            PipelineRun.status == "failed",
        )
    ).one()
    avg_cost = session.exec(
        select(func.avg(PipelineRun.total_cost_usd)).where(
            PipelineRun.channel_id == channel_id,
            PipelineRun.total_cost_usd.is_not(None),  # type: ignore[union-attr]
        )
    ).one()

    return ChannelWithStats(
        **base.model_dump(),
        total_runs=total,
        success_count=success,
        failed_count=failed,
        success_rate=round(success / total * 100, 1) if total > 0 else 0.0,
        avg_cost_usd=round(avg_cost or 0.0, 4),
    )
