"""Knowledge graph over extracted entities (Phase 12).

The graph is a plain JSON-serializable dict with three parts:

- ``documents``      -- document_id -> {title, source_file}
- ``entities``       -- entity name -> {type, documents}
- ``co_occurrences`` -- [{source, target, weight}], where weight is the
  number of documents mentioning both entities

Built from the metadata index (`kiaf metadata`) and the extracted entities
(`kiaf enrich`).
"""

from __future__ import annotations

import json
import logging
from itertools import combinations
from pathlib import Path

from know_it_all_friend.enrichment.extractor import DocumentEntities
from know_it_all_friend.metadata.extractor import DocumentMetadata

logger = logging.getLogger(__name__)


def build_graph(
    docs: list[DocumentMetadata],
    enriched: list[DocumentEntities],
) -> dict:
    """Build the document/entity graph from enriched metadata.

    An entity appearing under multiple types keeps the first type seen;
    its document lists are merged. Co-occurrence edges connect entities
    mentioned in the same document, weighted by how many documents share
    them.
    """
    dates = {e.document_id: getattr(e, "document_date", "") for e in enriched}
    documents = {
        doc.document_id: {"title": doc.title, "source_file": doc.source_file, "document_date": dates.get(doc.document_id, "")} for doc in docs
    }

    entities: dict[str, dict] = {}
    weights: dict[tuple[str, str], int] = {}
    for entry in enriched:
        names_in_doc: set[str] = set()
        for entity_type, names in entry.entities.items():
            for name in names:
                node = entities.setdefault(name, {"type": entity_type, "documents": []})
                if entry.document_id not in node["documents"]:
                    node["documents"].append(entry.document_id)
                names_in_doc.add(name)
        for pair in combinations(sorted(names_in_doc), 2):
            weights[pair] = weights.get(pair, 0) + 1

    co_occurrences = [
        {"source": source, "target": target, "weight": weight}
        for (source, target), weight in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    logger.info(
        "Built graph: %d document(s), %d entit(ies), %d co-occurrence edge(s)",
        len(documents),
        len(entities),
        len(co_occurrences),
    )
    return {"documents": documents, "entities": entities, "co_occurrences": co_occurrences}


def write_graph(graph: dict, output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    logger.info("Wrote graph to %s", output_path)


from typing import cast

def load_graph(graph_path: Path) -> dict:
    return cast(dict, json.loads(Path(graph_path).read_text(encoding="utf-8")))


def _resolve_entity(graph: dict, name: str) -> str | None:
    """Find an entity by name, case-insensitively."""
    if name in graph["entities"]:
        return name
    lowered = name.lower()
    for candidate in graph["entities"]:
        if candidate.lower() == lowered:
            return str(candidate)
    return None


def related_to_entity(graph: dict, name: str) -> dict | None:
    """Return the documents mentioning ``name`` and its co-occurring entities.

    Returns ``None`` when the entity is not in the graph. Co-occurring
    entities are sorted by descending shared-document weight.
    """
    resolved = _resolve_entity(graph, name)
    if resolved is None:
        return None

    node = graph["entities"][resolved]
    related = [
        {
            "name": edge["target"] if edge["source"] == resolved else edge["source"],
            "weight": edge["weight"],
        }
        for edge in graph["co_occurrences"]
        if resolved in (edge["source"], edge["target"])
    ]
    return {
        "name": resolved,
        "type": node["type"],
        "documents": [
            {"document_id": doc_id, **graph["documents"].get(doc_id, {})}
            for doc_id in node["documents"]
        ],
        "related_entities": related,
    }


def entities_of_document(graph: dict, document_id: str) -> dict[str, list[str]] | None:
    """Return the entities mentioned in ``document_id``, grouped by type.

    Returns ``None`` when the document is not in the graph.
    """
    if document_id not in graph["documents"]:
        return None
    grouped: dict[str, list[str]] = {}
    for name, node in graph["entities"].items():
        if document_id in node["documents"]:
            grouped.setdefault(node["type"], []).append(name)
    return grouped
