"""FCC LMS extractor (Layer 1). extract(frn) + resolve(entity)."""
from pipeline.extractors.fcc.extract import extract
from pipeline.extractors.fcc.resolve import resolve

__all__ = ["extract", "resolve"]
