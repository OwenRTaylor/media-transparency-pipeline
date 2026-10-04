"""Shared dataclasses — the only abstraction crossing layers.

Entity, Relationship, ProvenanceRecord, CoverageLog,
ResolutionResult, ExtractorResult. Imported by every layer.

These are the *in-memory* contract between Layer 1 (extractors),
Layer 2 (traversal), and Layer 3 (staging/export). They mirror the
locked SQLite schema (data-model.md, ADR-0011..0017) but are NOT the
DB rows themselves: extractors emit these objects; Layer 3 assigns DB
ids, dedupes source_documents, and writes the 8 production tables.

Design note (flagged for possible ADR): ProvenanceRecord *embeds* its
SourceDocument + AccessLink objects rather than referencing by id.
Extractor authors build whole evidence objects; id-linking + document
dedupe is a Layer-3 concern. Keeps extractor code local and honest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Controlled vocabularies (locked taxonomies — enum'd so a typo in one layer
# can't silently diverge from another). Values match data-model.md exactly.
# --------------------------------------------------------------------------

class EntityType(str, Enum):
    OUTLET = "outlet"                 # news source (brand + domains)
    COMPANY = "company"               # parent, holding, media group
    FUND = "fund"                     # PE, hedge fund, investment firm
    TRUST = "trust"                   # family trusts, foundations, endowments
    NATURAL_PERSON = "natural_person" # a real human
    GOV = "gov"                       # FCC, state agencies (Phase 2 — schema allows)


class RelationshipType(str, Enum):
    DIRECT_OWNERSHIP = "direct_ownership"   # A owns B outright / controlling
    PARENT_COMPANY = "parent_company"       # A is corporate parent of B
    FAMILY_CONTROL = "family_control"       # person/family documented control
    PRIVATE_EQUITY = "private_equity"       # PE firm owns or controls
    MAJOR_SHAREHOLDER = "major_shareholder" # significant non-controlling (5%+)
    NONPROFIT_FUNDING = "nonprofit_funding" # foundation/nonprofit funds
    TRUST_STRUCTURE = "trust_structure"     # held through trust
    GOVERNANCE = "governance"               # nonprofit board — NOT ownership (INV-5)
    UNKNOWN_OPAQUE = "unknown_opaque"       # exists but type/party undeterminable


class Confidence(str, Enum):
    """Probabilistic grade for a *Likely* inference (INV-9, never NULL).

    NOTE: `official` is deliberately NOT here. Official is a categorical
    tier the server reads on the source/extraction axes, never a point on
    this probability scale (design/entity-discovery.md, Trust Tiers).
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Status(str, Enum):
    ACTIVE = "active"
    HISTORICAL = "historical"
    UNCERTAIN = "uncertain"


class ExtractionMethod(str, Enum):
    """Two-axis tier, extraction axis (data-model.md). v1 emits AUTOMATED only."""
    AUTOMATED = "automated"
    LLM = "llm"
    HUMAN_CURATED = "human-curated"


class AccessTier(str, Enum):
    """How to reach a document. All reachable tiers stored (INV-35, capture-or-lose)."""
    A = "A"  # public URL
    B = "B"  # bulk-download URL + row id
    C = "C"  # local document cache (file path to original-format copy)


class RecordType(str, Enum):
    EXTRACTION = "extraction"  # an extracted fact
    GAP = "gap"                # data exists in source but not yet extractable (ADR-0016)


class TargetType(str, Enum):
    """What a provenance record sources (polymorphic, ADR-0013)."""
    RELATIONSHIP = "relationship"
    ENTITY_ATTRIBUTE = "entity_attribute"
    EXTERNAL_ID = "external_id"
    ENTITY = "entity"  # used for gap records


# ID types that live in entity_external_ids (M:N, ADR-0013). Not exhaustive —
# additive per source. String values are the id_type column.
class IdType(str, Enum):
    CIK = "cik"
    EIN = "ein"
    FRN = "frn"
    FACILITY_ID = "facility_id"
    CRD = "crd"
    LEI = "lei"


# --------------------------------------------------------------------------
# Entity + its external identifiers
# --------------------------------------------------------------------------

@dataclass
class ExternalId:
    """One (id_type, id_value) for an entity. Row in entity_external_ids.

    INV-1: never used AS the entity id. FRN<->entity is M:N.
    The cross-source identity-merge that attaches an id from another source
    MUST carry its own provenance + tier (design/entity-discovery.md rule 3):
    set `merge_confidence` + `merge_method` when this id came from a
    cross-source match rather than the entity's own source. Never merge silently.
    """
    id_type: IdType
    id_value: str
    # Set only when this id was attached by a cross-source merge (else None =
    # native to the entity's own source, deterministic).
    merge_confidence: Optional[Confidence] = None
    merge_method: Optional[str] = None  # e.g. "rapidfuzz_wratio+address", free text


@dataclass
class Entity:
    """A node in the ownership graph.

    `id` is a pipeline-assigned stable unique id (INV-1) — NEVER a name or FRN.
    Extractors that don't yet know the canonical id may leave it "" and let
    Layer-3 resolution assign/merge; `external_ids` is how they're matched.
    """
    id: str
    type: EntityType
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)  # sourced facts (see provenance)
    external_ids: List[ExternalId] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)  # outlets only
    raw_source_row: Optional[Dict[str, Any]] = None  # verbatim (INV-28), verification backup


# --------------------------------------------------------------------------
# Relationship (first-class edge, INV-2)
# --------------------------------------------------------------------------

@dataclass
class Relationship:
    """A directed edge. Invalid without >=1 provenance record (INV-3).

    Universal fields are columns; source-specific detail goes in
    detail_payload (ADR-0015). raw_source_row lives on provenance, not here.
    """
    source_entity_id: str
    target_entity_id: str
    type: RelationshipType
    confidence: Confidence
    last_verified: date          # source filing date, NOT run date (INV-6)
    status: Status = Status.ACTIVE
    qualifier: Optional[str] = None                 # e.g. "dual-class voting"
    detail_type: Optional[str] = None               # discriminator for detail_payload
    detail_payload: Optional[Dict[str, Any]] = None
    detail_schema_version: Optional[int] = None


# --------------------------------------------------------------------------
# Evidence subsystem (four tables → nested objects here, ADR-0013)
# --------------------------------------------------------------------------

@dataclass
class AccessLink:
    """One way to reach a source_document. Many per document, all tiers (INV-35)."""
    tier: AccessTier
    location: str                    # URL (A/B) or file path (C)
    row_id: Optional[str] = None     # for tier B: primary key / row id within the bulk file


@dataclass
class SourceDocument:
    """One specific filing/document (a DEF 14A, an FCC ownership report, a 990).

    filing_date feeds INV-6 last_verified. Referenced by many provenance rows;
    Layer-3 dedupes identical documents when assigning ids.
    """
    source: str                      # source system key: "sec_edgar" | "fcc_lms" | "irs_990"
    doc_type: str                    # e.g. "DEF 14A", "fcc_ownership_report", "form_990"
    filing_date: Optional[date]      # publication/filing date (None if genuinely unknown)
    access_links: List[AccessLink] = field(default_factory=list)
    document_id: Optional[str] = None  # source-native id (accession no. / filename), if any


@dataclass
class ProvenanceRecord:
    """Binds one extracted fact — or one documented gap — to one SourceDocument.

    Per-detail grain (ADR-0013). record_type=GAP => extraction_method/confidence
    are None and anchor_payload carries {data_point, gap_reason} (ADR-0016).
    """
    record_type: RecordType
    target_type: TargetType
    target_id: str                       # id of the relationship/entity/attr/external_id sourced
    source_document: SourceDocument      # embedded (see module docstring)
    anchor_type: str                     # pipeline-controlled enum, e.g. "sec_accession"
    anchor_payload: Dict[str, Any]       # in-document locator; shape per anchor_type
    anchor_schema_version: int
    extraction_code_sha: str             # git SHA of producing code (reproducibility)
    created_at: datetime                 # run timestamp; immutable snapshot (ADR-0016)
    # Extractions only (None for gaps):
    extraction_method: Optional[ExtractionMethod] = None
    confidence: Optional[Confidence] = None
    raw_source_row: Optional[Dict[str, Any]] = None  # Tenet-3 audit anchor; backup only

    def __post_init__(self) -> None:
        # Cheap contract guard — full validation lives in staging/validate.py.
        if self.record_type is RecordType.EXTRACTION:
            if self.extraction_method is None or self.confidence is None:
                raise ValueError("extraction records require extraction_method + confidence (INV-9)")
        elif self.record_type is RecordType.GAP:
            if self.extraction_method is not None or self.confidence is not None:
                raise ValueError("gap records must have NULL extraction_method + confidence")


# --------------------------------------------------------------------------
# Coverage + resolution + the extractor return contract
# --------------------------------------------------------------------------

@dataclass
class CoverageLog:
    """What an extractor queried, found, and did not find — for trail-end honesty (INV-19)."""
    source: str
    queried: List[str] = field(default_factory=list)     # e.g. entity ids / keys attempted
    found: List[str] = field(default_factory=list)
    not_found: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """entity -> source-local key (Resolution #2, ADR-0011). Returned by each extractor's resolve()."""
    source_key: Optional[str]                       # CIK/FRN/EIN, or None if unresolved
    confidence: Confidence
    method: str                                     # how resolved, e.g. "external_id_exact"
    candidates: List[Dict[str, Any]] = field(default_factory=list)  # rejected/ambiguous alternatives
    provenance: Optional[ProvenanceRecord] = None


@dataclass
class ExtractorResult:
    """The common Layer-1 return contract (data-model.md).

    Every extractor's extract() returns this tuple-of-lists shape.
    No base class — this dataclass + resolve() signature are the only abstraction.
    """
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    provenance: List[ProvenanceRecord] = field(default_factory=list)
    coverage_log: Optional[CoverageLog] = None
