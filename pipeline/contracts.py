"""Shared dataclasses — the only abstraction crossing layers.

Entity, Relationship, ProvenanceRecord, CoverageLog,
ResolutionResult, ExtractorResult. Imported by every layer.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

@dataclass
class Entity:
    id: str
    type: str
    attributes: Dict[str, Any]