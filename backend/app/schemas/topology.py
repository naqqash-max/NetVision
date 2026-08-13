from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class TopologyNode(BaseModel):
    id: UUID
    name: Optional[str]
    hostname: str
    ip_address: str
    device_type: str
    status: str
    is_authorized: bool

class TopologyEdge(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    link_type: str
    status: str

class TopologyResponse(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
