from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize Temporal client at startup, clean up at shutdown (per Pattern 2)."""
    app.state.temporal_client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    yield


app = FastAPI(
    title="YouTube Pipeline API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Netlify and local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.health import router as health_router  # noqa: E402
from src.api.sync import router as sync_router  # noqa: E402
from src.api import pipeline  # noqa: E402
from src.api import dashboard  # noqa: E402
from src.api import channels  # noqa: E402
from src.api import system  # noqa: E402

app.include_router(health_router)
app.include_router(sync_router)
app.include_router(pipeline.router)
app.include_router(dashboard.router)
app.include_router(channels.router)
app.include_router(system.router)
