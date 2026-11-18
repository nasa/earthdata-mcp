"""Input model for the show_map MCP tool."""

from typing import Annotated

from pydantic import Field

CollectionConceptIdParam = Annotated[
    str | None,
    Field(
        default=None,
        description=(
            "CMR collection concept ID (format: C<number>-<PROVIDER>, "
            "e.g., C1276812859-GES_DISC). When provided, terra-map automatically "
            "fetches and displays any associated GIBS imagery layers. "
            "If omitted, a bare interactive map is returned."
        ),
    ),
]
