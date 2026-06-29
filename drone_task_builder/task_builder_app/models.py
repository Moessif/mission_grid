from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TaskTemplate:
    task_id: str
    name: str
    description: str
    category: str
    default_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionTask:
    task_id: str
    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionPlan:
    mission_name: str
    tasks: List[MissionTask] = field(default_factory=list)


@dataclass
class ExportResult:
    bundle_type: str
    bundle_dir: str
    entry_script: str
    generated_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
