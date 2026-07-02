from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple, Dict


class FieldSource(Enum):
    """Enumeration of valid resolution sources for flow requested fields."""
    PAYLOAD = "payload"
    DEFAULT = "default"
    BIGQUERY = "bigquery"


@dataclass(frozen=True)
class FieldConfig:
    """
    Purpose: Represents an immutable schema definition for a single requested field.
    Responsibility: Stores field name, sourcing strategy, default fallback, and validation rules.
    Inputs: name (str), source (FieldSource), required (bool), default_value (Any), validation_regex (str).
    Outputs: Immutable FieldConfig instance.
    """
    name: str
    source: FieldSource
    required: bool = False
    default_value: Any = None
    validation_regex: Optional[str] = None


@dataclass(frozen=True)
class FlowConfig:
    """
    Purpose: Represents an immutable configuration definition for a Glific Flow webhook handler.
    Responsibility: Enforces flow metadata, BigQuery TVF routing, cache TTLs, and requested field schemas.
    Inputs: flow_id (str), flow_name (str), category (str), bq_routine (str), cache_ttl (int), bypass_cache (bool), fields (Tuple[FieldConfig, ...]).
    Outputs: Immutable FlowConfig instance.
    """
    flow_id: str
    flow_name: str
    category: str
    bq_routine: Optional[str] = None
    cache_ttl: int = 300
    bypass_cache: bool = False
    fields: Tuple[FieldConfig, ...] = field(default_factory=tuple)


@dataclass
class ResolutionContext:
    """
    Purpose: Request-scoped mutable execution context during context resolution.
    Responsibility: Carries raw payload, contact phone number, execution flags, and aggregates resolved fields.
    Inputs: flow_id (str), phone (str), raw_payload (Dict[str, Any]), resolved_fields (Dict[str, Any]), mock_mode (bool).
    Outputs: Mutable execution state passed across data providers.
    """
    flow_id: str
    phone: str
    raw_payload: Dict[str, Any]
    resolved_fields: Dict[str, Any] = field(default_factory=dict)
    mock_mode: bool = False
