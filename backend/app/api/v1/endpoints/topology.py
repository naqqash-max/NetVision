from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.device import Device
from app.models.link import Link
from app.schemas.topology import TopologyResponse, TopologyNode, TopologyEdge
from app.api.deps import require_viewer
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=TopologyResponse)
def get_topology(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve devices and links structured as nodes and edges for topology graphs.
    """
    try:
        devices = db.query(Device).all()
        links = db.query(Link).all()

        nodes = [
            TopologyNode(
                id=d.id,
                name=d.name,
                hostname=d.hostname,
                ip_address=d.ip_address,
                device_type=d.device_type,
                status=d.status,
                is_authorized=d.is_authorized
            )
            for d in devices
        ]

        edges = [
            TopologyEdge(
                id=l.id,
                source=l.source_device_id,
                target=l.target_device_id,
                source_interface=l.source_interface,
                target_interface=l.target_interface,
                link_type=l.link_type,
                status=l.status
            )
            for l in links
        ]

        return TopologyResponse(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred while retrieving topology: {str(e)}"
        )
