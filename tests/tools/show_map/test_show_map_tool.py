"""Tests for the show_map tool."""

from tools.show_map.tool import show_map


def _structured_html(result) -> str:
    """Find the embedded iframe HTML in a ToolResult structured_content dict."""
    def _search(obj):
        if isinstance(obj, dict):
            if "html" in obj and isinstance(obj["html"], str):
                return obj["html"]
            for v in obj.values():
                found = _search(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _search(item)
                if found:
                    return found
        return ""
    return _search(result.structured_content)


def test_show_map_no_collection_text():
    """With no collection ID, text content indicates a bare map."""
    result = show_map()
    assert result.content[0].text == "Rendered interactive map."


def test_show_map_with_collection_id_text():
    """With a collection ID, text content references the collection."""
    cid = "C1276812859-GES_DISC"
    result = show_map(collection_concept_id=cid)
    assert result.content[0].text == f"Rendered map for collection {cid}."


def test_show_map_returns_structured_content():
    """show_map must return a serialized PrefabApp in structured_content."""
    result = show_map()
    assert isinstance(result.structured_content, dict)
    assert "$prefab" in result.structured_content


def test_show_map_html_contains_terra_map():
    """Embedded iframe HTML must include a terra-map element."""
    assert "terra-map" in _structured_html(show_map())


def test_show_map_html_includes_collection_id_attribute():
    """When a collection ID is given, the iframe HTML must carry the collection-id attribute."""
    cid = "C1276812859-GES_DISC"
    assert f'collection-id="{cid}"' in _structured_html(show_map(collection_concept_id=cid))
