from fastapi import APIRouter

from app.schemas.path import StateUpdateRequest, StateUpdateResponse

router = APIRouter(tags=["state"])


@router.post("/state/update", response_model=StateUpdateResponse)
def state_update(payload: StateUpdateRequest) -> StateUpdateResponse:
    return StateUpdateResponse(message="state update endpoint placeholder", payload=payload)
