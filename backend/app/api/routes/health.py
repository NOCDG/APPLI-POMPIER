from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
@router.get("health")
async def health():
    return {"status": "ok"}
