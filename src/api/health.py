from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:  # type: ignore[type-arg]
    return {"status": "ok"}
