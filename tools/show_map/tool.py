"""Tool: render a terra-map, optionally loading GIBS imagery for a CMR collection."""

from fastmcp.tools.base import ToolResult
from mcp.types import TextContent
from prefab_ui import PrefabApp

from models.tools.show_map import CollectionConceptIdParam
from util.visualization import MapSpec, map_card


def show_map(collection_concept_id: CollectionConceptIdParam = None) -> ToolResult:
    """Show an interactive terra-map.

    If a CMR collection concept ID is provided, terra-map loads associated
    GIBS imagery automatically. Without one, a bare world map is returned.
    """
    title = f"Map — {collection_concept_id}" if collection_concept_id else "Map"
    spec = MapSpec(title=title, collection_id=collection_concept_id)
    text = (
        f"Rendered map for collection {collection_concept_id}."
        if collection_concept_id
        else "Rendered interactive map."
    )
    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=PrefabApp(title=spec.title, view=map_card(spec)),
    )
