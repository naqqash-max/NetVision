from fastapi import APIRouter
from app.api.v1.endpoints import devices, topology, alerts, auth, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(topology.router, prefix="/topology", tags=["topology"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
