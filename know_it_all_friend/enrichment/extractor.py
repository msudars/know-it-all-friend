"""Knowledge enrichment: entity and topic extraction from document content (Phase 4)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from know_it_all_friend.metadata.extractor import DocumentMetadata
from know_it_all_friend.rag.base import BaseLLM

logger = logging.getLogger(__name__)

ENTITY_TYPES = (
    "people",
    "organizations",
    "projects",
    "products",
    "datasets",
    "technologies",
    "publications",
    "locations",
    "topics",
)

# Only the leading slice of each document is sent to the model: entity-dense
# front matter (title, authors, abstract, intro) fits comfortably, and whole
# documents would blow past small local models' context windows.
DEFAULT_MAX_CHARS = 8000

SYSTEM_PROMPT = (
    "You extract named entities from documents. "
    "Respond with a single JSON object and nothing else."
)


@dataclass(frozen=True)
class DocumentEntities:
    document_id: str
    entities: dict[str, list[str]]


def build_enrichment_prompt(text: str) -> str:
    keys = ", ".join(f'"{t}"' for t in ENTITY_TYPES)
    return (
        f"Extract the entities mentioned in the document below into a JSON object "
        f"with exactly these keys: {keys}. Each value is a list of distinct strings; "
        f"use an empty list when nothing of that type is mentioned. "
        f"Do not invent entities that are not in the text.\n\n"
        f"Document:\n{text}"
    )


def _parse_entities(response: str) -> dict[str, list[str]]:
    """Parse the model's JSON reply into a clean entity mapping.

    Local models occasionally wrap JSON in prose or code fences, so parsing
    starts at the first ``{`` and ends at the last ``}``. Unknown keys and
    non-string values are dropped; values are deduplicated preserving order.
    An unparseable reply yields an empty mapping rather than an error.
    """
    start, end = response.find("{"), response.rfind("}")
    if start == -1 or end <= start:
        logger.warning("Entity reply contained no JSON object")
        return {entity_type: [] for entity_type in ENTITY_TYPES}
    try:
        raw = json.loads(response[start : end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse entity reply as JSON: %s", exc)
        return {entity_type: [] for entity_type in ENTITY_TYPES}

    entities: dict[str, list[str]] = {}
    for entity_type in ENTITY_TYPES:
        values = raw.get(entity_type, [])
        if not isinstance(values, list):
            values = []
        seen: list[str] = []
        for value in values:
            if isinstance(value, str) and (cleaned := " ".join(value.split())) and cleaned not in seen:
                seen.append(cleaned)
        entities[entity_type] = seen
    return entities


def extract_entities(
    markdown_text: str,
    llm: BaseLLM,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, list[str]]:
    """Extract typed entities from one document's Markdown via the LLM."""
    response = llm.generate(build_enrichment_prompt(markdown_text[:max_chars]), system=SYSTEM_PROMPT)
    return _parse_entities(response)


def enrich_documents(
    docs: list[DocumentMetadata],
    llm: BaseLLM,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[DocumentEntities]:
    """Extract entities for every document in the metadata index.

    A document whose Markdown cannot be read or whose model call fails is
    logged and skipped; the rest of the collection is still enriched.
    """
    enriched: list[DocumentEntities] = []
    for doc in docs:
        try:
            markdown_text = Path(doc.markdown_file).read_text(encoding="utf-8")
            entities = extract_entities(markdown_text, llm, max_chars=max_chars)
        except Exception as exc:  # noqa: BLE001 - must not abort the batch
            logger.warning("Skipping %s: enrichment failed: %s", doc.document_id, exc)
            continue
        enriched.append(DocumentEntities(document_id=doc.document_id, entities=entities))
        found = sum(len(v) for v in entities.values())
        logger.info("Enriched %s: %d entit(ies)", doc.document_id, found)
    return enriched


def write_entities(enriched: list[DocumentEntities], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in enriched], f, indent=2)
    logger.info("Wrote entities for %d document(s) to %s", len(enriched), output_path)


def load_entities(entities_path: Path) -> list[DocumentEntities]:
    entities_path = Path(entities_path)
    data = json.loads(entities_path.read_text(encoding="utf-8"))
    return [DocumentEntities(**entry) for entry in data]
