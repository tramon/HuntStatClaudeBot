"""
Web search via Tavily API.

Returns a short text summary suitable for passing to Claude as tool result.
If TAVILY_API_KEY is not set, search is silently disabled.
"""

import logging

import config

logger = logging.getLogger(__name__)


def web_search(query: str, max_results: int = 5) -> str:
    """Run a web search and return a plain-text summary of results.

    Returns an empty string if search is disabled or fails.
    """
    if not config.TAVILY_API_KEY:
        logger.debug("TAVILY_API_KEY not set -- search disabled")
        return ""

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )
        results = response.get("results", [])
        if not results:
            return "No results found."

        lines = []
        for r in results:
            title = r.get("title", "")
            url   = r.get("url", "")
            content = r.get("content", "").strip()
            lines.append(f"**{title}**\n{url}\n{content}")

        return "\n\n".join(lines)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search failed: {e}"
