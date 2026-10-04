"""Synthetic Fox ExtractorResult — a stand-in until real extractor output lands.

Exercises the whole Layer-3 path deliberately:
  * two sources (SEC EDGAR + FCC LMS) -> `sources` table has 2 rows,
  * one SEC DEF 14A cited by TWO provenance records -> source_document dedupe,
  * provenance targets of every polymorphic kind: relationship,
    entity_attribute, external_id, and a `gap` record against an entity,
  * a cross-source merged external id carrying merge_confidence/merge_method.

All rows are v1-tier: source_official=true, extraction_method=automated.
"""
from __future__ import annotations

from datetime import date, datetime

from pipeline.contracts import (
    AccessLink, AccessTier, Confidence, Entity, EntityType, ExternalId,
    ExtractionMethod, ExtractorResult, IdType, ProvenanceRecord, RecordType,
    Relationship, RelationshipType, SourceDocument, Status, TargetType,
)
from pipeline.staging.keys import rel_natural_key

_SHA = "abc1234def5678"          # stand-in git SHA of the producing extractor
_RUN = datetime(2026, 9, 19, 12, 0, 0)


def fox_result() -> ExtractorResult:
    # --- entities ------------------------------------------------------------
    fox_corp = Entity(
        id="fox_corp",
        type=EntityType.COMPANY,
        canonical_name="Fox Corporation",
        aliases=["Fox Corp", "FOXA"],
        attributes={"state_of_incorporation": "DE"},
        external_ids=[
            ExternalId(IdType.CIK, "0001754301"),
            # cross-source merge (SEC entity matched to an FCC party): carries tier.
            ExternalId(IdType.FRN, "0026internal", merge_confidence=Confidence.HIGH,
                       merge_method="rapidfuzz_wratio+address"),
        ],
    )
    fox_news = Entity(
        id="fox_news_outlet",
        type=EntityType.OUTLET,
        canonical_name="Fox News",
        aliases=["Fox News Channel", "FNC"],
        domains=["foxnews.com", "foxbusiness.com"],
    )
    wnyw = Entity(
        id="wnyw_station",
        type=EntityType.OUTLET,
        canonical_name="WNYW",
        domains=["fox5ny.com"],
        external_ids=[ExternalId(IdType.FACILITY_ID, "22206")],
    )
    murdoch = Entity(
        id="rupert_murdoch",
        type=EntityType.NATURAL_PERSON,
        canonical_name="Rupert Murdoch",
    )

    # --- relationships -------------------------------------------------------
    r_corp_news = Relationship(
        source_entity_id="fox_corp", target_entity_id="fox_news_outlet",
        type=RelationshipType.DIRECT_OWNERSHIP, confidence=Confidence.HIGH,
        last_verified=date(2024, 11, 1),
    )
    r_corp_wnyw = Relationship(
        source_entity_id="fox_corp", target_entity_id="wnyw_station",
        type=RelationshipType.DIRECT_OWNERSHIP, confidence=Confidence.HIGH,
        last_verified=date(2024, 4, 15),
    )
    r_murdoch_corp = Relationship(
        source_entity_id="rupert_murdoch", target_entity_id="fox_corp",
        type=RelationshipType.FAMILY_CONTROL, confidence=Confidence.HIGH,
        last_verified=date(2024, 11, 1), qualifier="dual-class voting",
        detail_type="sec_voting_control", detail_schema_version=1,
        detail_payload={"class_b_voting_pct": 79.0, "instrument": "Class B common"},
    )

    # --- source documents (one SEC filing reused by two provenance records) --
    def def14a() -> SourceDocument:
        return SourceDocument(
            source="sec_edgar", doc_type="DEF 14A", filing_date=date(2024, 11, 1),
            document_id="0001193125-24-255000",
            access_links=[
                AccessLink(AccessTier.A,
                           "https://www.sec.gov/Archives/edgar/data/1754301/"
                           "000119312524255000/d123456ddef14a.htm"),
                AccessLink(AccessTier.B,
                           "https://www.sec.gov/Archives/edgar/full-index/2024/",
                           row_id="0001193125-24-255000"),
                AccessLink(AccessTier.C,
                           "data/cache/sec_edgar/0001193125-24-255000.htm"),
            ],
        )

    fcc_report = SourceDocument(
        source="fcc_lms", doc_type="fcc_ownership_report",
        filing_date=date(2024, 4, 15), document_id="LMS-2024-0022060",
        access_links=[
            AccessLink(AccessTier.B, "https://enterpriseefiling.fcc.gov/dataentry/",
                       row_id="22206|2024"),
            AccessLink(AccessTier.C, "data/cache/fcc_lms/LMS-2024-0022060.dat"),
        ],
    )

    def anchor(**kw):
        return {"anchor_schema_version": 1, "extraction_code_sha": _SHA,
                "created_at": _RUN, "extraction_method": ExtractionMethod.AUTOMATED,
                "confidence": Confidence.HIGH, **kw}

    provenance = [
        # relationship targets (two facts, same DEF 14A -> dedupes to one doc)
        ProvenanceRecord(
            record_type=RecordType.EXTRACTION, target_type=TargetType.RELATIONSHIP,
            target_id=rel_natural_key(r_corp_news), source_document=def14a(),
            anchor_type="sec_accession",
            anchor_payload={"accession": "0001193125-24-255000",
                            "section": "Item 12 — Security Ownership"},
            **anchor()),
        ProvenanceRecord(
            record_type=RecordType.EXTRACTION, target_type=TargetType.RELATIONSHIP,
            target_id=rel_natural_key(r_murdoch_corp), source_document=def14a(),
            anchor_type="sec_accession",
            anchor_payload={"accession": "0001193125-24-255000",
                            "section": "Beneficial Ownership table"},
            raw_source_row={"holder": "Murdoch, K.R.", "class_b_pct": "79.0"},
            **anchor()),
        # FCC relationship
        ProvenanceRecord(
            record_type=RecordType.EXTRACTION, target_type=TargetType.RELATIONSHIP,
            target_id=rel_natural_key(r_corp_wnyw), source_document=fcc_report,
            anchor_type="fcc_lms_row",
            anchor_payload={"table": "interest_holders", "pk": "22206|2024"},
            **anchor()),
        # entity_attribute target (Fox Corp state of incorporation, from the DEF 14A)
        ProvenanceRecord(
            record_type=RecordType.EXTRACTION,
            target_type=TargetType.ENTITY_ATTRIBUTE, target_id="fox_corp",
            source_document=def14a(), anchor_type="sec_accession",
            anchor_payload={"accession": "0001193125-24-255000",
                            "attribute": "state_of_incorporation"},
            **anchor()),
        # external_id target (Fox Corp CIK)
        ProvenanceRecord(
            record_type=RecordType.EXTRACTION, target_type=TargetType.EXTERNAL_ID,
            target_id="fox_corp", source_document=def14a(),
            anchor_type="sec_accession",
            anchor_payload={"accession": "0001193125-24-255000", "id_type": "cik"},
            **anchor()),
        # gap record (data exists but not yet extractable) — NULL method/confidence
        ProvenanceRecord(
            record_type=RecordType.GAP, target_type=TargetType.ENTITY,
            target_id="fox_news_outlet", source_document=fcc_report,
            anchor_type="fcc_lms_row",
            anchor_payload={"data_point": "ultimate_parent_chain",
                            "gap_reason": "party listed by FRN, no SEC bridge"},
            anchor_schema_version=1, extraction_code_sha=_SHA, created_at=_RUN),
    ]

    return ExtractorResult(
        entities=[fox_corp, fox_news, wnyw, murdoch],
        relationships=[r_corp_news, r_corp_wnyw, r_murdoch_corp],
        provenance=provenance,
    )
