"""
CMR Utilities Module

This module provides utility functions for working with CMR search results,
including reordering results and converting geometries to CMR-compatible formats.
"""

import shapely.wkt
from shapely.geometry import Point, Polygon, MultiPolygon


def reorder_results(response, concept_ids, response_format, similarity_scores):
    """
    Reorder CMR results to match the order from Postgres and filter by granule count.

    Args:
        response (dict): The response from CMR
        concept_ids (list): The list of concept IDs in the order returned by Postgres
        response_format (str): The format of the response ('json' or 'umm_json')
        similarity_scores (list): The list of similarity scores in the order returned by Postgres

    Returns:
        list: Reordered list of items with granule_count > 0
    """
    concept_id_place = {}

    items = []
    concept_id_key = None
    granule_count_key = None

    if response_format == "umm_json":
        items = response["data"]["items"]
        concept_id_key = "meta.concept-id"
        granule_count_key = "meta.granule-count"
    elif response_format == "json":
        items = response["data"]["feed"]["entry"]
        concept_id_key = "id"
        granule_count_key = "granule_count"

    # Build a mapping of concept_id to its position in the CMR response
    # Only include items with granule count > 0
    for idx, item in enumerate(items):
        concept_id = (
            item["meta"]["concept-id"]
            if response_format == "umm_json"
            else item[concept_id_key]
        )
        granule_count = (
            item["meta"].get("granule-count", 0)
            if response_format == "umm_json"
            else int(item.get(granule_count_key, 0))
        )

        # Only include items with granule count > 0
        if granule_count > 0:
            concept_id_place[concept_id] = idx

    ordered_items = []

    # Build a new ordered list of items based on the Postgres concept ID order
    # and append the corresponding similarity score
    for cid, score in zip(concept_ids, similarity_scores):
        # Some concept IDs may have been removed from CMR but still exist in Postgres
        # Only append those that are present in the CMR response
        if cid in concept_id_place:
            item_idx = concept_id_place[cid]
            # Append the similarity score to the item
            if response_format == "umm_json":
                items[item_idx]["meta"]["similarity-score"] = score
            else:
                items[item_idx]["similarity_score"] = score

            ordered_items.append(items[item_idx])

    return ordered_items


def wkt_to_cmr_params(wkt_string):
    """Convert a WKT string to CMR-compatible spatial query parameters.

    This function takes a WKT string representing a geometric shape,
    simplifies it if necessary, and converts it into a format suitable for
    use in CMR spatial queries.

    Args:
        wkt_string (str): A Well-Known Text string representing a geometric
            shape.

    Returns:
        dict: A dictionary containing CMR-compatible spatial query parameters.
              For a Point, it returns {'point': 'lon,lat'}.
              For Polygons or MultiPolygons, it returns
              {'polygon[]': ['lon1,lat1,lon2,lat2,...']}.

    Raises:
        ValueError: If the WKT string does not represent a Point, Polygon,
            or MultiPolygon.

    Note:
        The function simplifies complex geometries to ensure they fit within
        CMR POST request limitations.
    """
    # Convert the geometry string to a Shapely geometry object
    geometry = shapely.wkt.loads(str(wkt_string))

    # Further simplify the geometry while preserving topological properties.
    # This step helps ensure the geometry fits within CMR POST request
    # limitations.
    simplified_geometry = geometry.simplify(0.5, preserve_topology=True)

    # Convert the final simplified geometry back to Well-Known Text (WKT) format
    simplified_geom = simplified_geometry.wkt

    # Parse the WKT string
    geom = shapely.wkt.loads(simplified_geom)

    if isinstance(geom, Point):
        # For a point, return the coordinates in the format "lon,lat"
        return {"point": f"{geom.x},{geom.y}"}
    if isinstance(geom, Polygon):
        polygons = [geom]
    elif isinstance(geom, MultiPolygon):
        polygons = list(geom.geoms)
    else:
        raise ValueError("The WKT must represent a Point, Polygon, or MultiPolygon")

    # Format coordinates for CMR (lon1,lat1,lon2,lat2,...)
    polygon_coords = []
    for polygon in polygons:
        # Get coordinates and reverse their order to ensure counter-clockwise orientation
        coords = list(polygon.exterior.coords)[::-1]
        polygon_coords.append(",".join(f"{lon},{lat}" for lon, lat in coords))

    return {"polygon[]": polygon_coords}
