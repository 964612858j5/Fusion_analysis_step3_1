"""Small immutable-ish data records used by the Step3.1 comparator."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RoiRecord:
    roi_id: str
    display_name: str
    roi_dir: str
    manifest_path: str
    bbox_fullres: Optional[List[int]] = None
    shape: Optional[List[int]] = None
    fusion_zarr: Optional[str] = None
    corrected_zarr: Optional[str] = None
    raw_ome: Optional[str] = None


@dataclass
class RunRecord:
    run_id: str
    roi_id: str
    method: str
    display_name: str
    created_at: str
    run_dir: str
    meta_path: str
    dapi_ome: str
    mask_ome: str
    mask_zarr: Optional[str] = None
    cell_count: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        stamp = self.created_at or self.run_id
        return f"{self.display_name} - {stamp}"


@dataclass
class ChannelRecord:
    name: str
    source: str
    color: str = "#ffffff"
    alpha: float = 0.65
    visible: bool = False
