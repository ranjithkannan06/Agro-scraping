"""Dataclasses for validation, duplicate, and analytics reports."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ValidationIssue:
    row_index: int
    reason: str
    record: Dict[str, Any]


@dataclass
class ValidationReport:
    total: int
    valid: int
    duplicate: int
    invalid: int
    validity_percentage: float
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeduplicationReport:
    total: int
    new: int
    duplicate: int
    duplicates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
