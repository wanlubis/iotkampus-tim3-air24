
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/api/v1/air",
    tags=["Air Quality"]
)

# Data awal sementara.
# Nanti akan diisi dari database dan simulator.
AIR_ROOMS = {}


@router.get("/rooms")
def get_rooms():
    return {
        "total": len(AIR_ROOMS),
        "rooms": list(AIR_ROOMS.values())
    }


@router.get("/rooms/{ruang}")
def get_room(ruang: str):
    room = AIR_ROOMS.get(ruang)

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found"
        )

    return room
