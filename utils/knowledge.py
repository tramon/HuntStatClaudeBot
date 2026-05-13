"""
Knowledge base loader.

Reads knowledge/index.yaml to map topic keywords to .md files.
To add new knowledge: drop a .md file in knowledge/ and add an entry
to index.yaml -- no code changes needed.
"""

import logging
import os

logger = logging.getLogger(__name__)

_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
_INDEX_PATH = os.path.join(_BASE, "index.yaml")

# Cache: list of {"file": str, "keywords": list[str]}
_index_cache: list | None = None


def _load_index() -> list:
    """Load and cache index.yaml. Returns list of topic entries."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    try:
        import yaml
    except ImportError:
        logger.error("PyYAML not installed. Run: pip install pyyaml")
        _index_cache = []
        return _index_cache

    try:
        with open(_INDEX_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        _index_cache = data
        logger.info(f"Knowledge index loaded: {len(data)} topic(s)")
    except FileNotFoundError:
        logger.warning(f"knowledge/index.yaml not found")
        _index_cache = []
    except Exception as e:
        logger.error(f"Failed to load knowledge index: {e}")
        _index_cache = []

    return _index_cache


def _load_file(filename: str) -> str:
    path = os.path.join(_BASE, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Knowledge file not found: {path}")
        return ""
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return ""


def get_relevant_knowledge(text: str) -> str:
    """Return knowledge file content relevant to the query, or empty string.

    Matches keywords case-insensitively against index.yaml.
    Multiple matching files are joined with a separator.
    """
    lower = text.lower()
    index = _load_index()
    matched_files: list[str] = []

    for entry in index:
        filename = entry.get("file", "")
        keywords = entry.get("keywords", [])
        if not filename or filename in matched_files:
            continue
        if any(kw.lower() in lower for kw in keywords):
            matched_files.append(filename)

    if not matched_files:
        return ""

    parts = []
    for filename in matched_files:
        content = _load_file(filename)
        if content:
            parts.append(content)
            logger.info(f"Knowledge loaded: {filename}")

    return "\n\n---\n\n".join(parts)
