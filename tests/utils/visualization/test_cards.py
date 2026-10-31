"""Tests for the map card renderer."""

from prefab_ui import PrefabApp

from util.visualization.map_card import map_card, map_html
from util.visualization.specs import MapSpec


def _spec(**overrides):
    base = {"title": "Test Map"}
    base.update(overrides)
    return MapSpec(**base)


def test_map_html_injects_collection_id():
    spec = _spec(collection_id="C1276812859-GES_DISC")
    html = map_html(spec)
    assert 'collection-id="C1276812859-GES_DISC"' in html
    assert "terra-map" in html
    assert "show-layer-picker" in html


def test_map_html_no_collection_omits_attribute():
    html = map_html(_spec())
    assert "collection-id" not in html
    assert "terra-map" in html


def test_map_html_injects_height():
    assert "600px" in map_html(_spec(height=600))


def test_map_card_renders_to_prefab():
    card = map_card(_spec(collection_id="C1-GES_DISC"))
    html = PrefabApp(title="t", view=card).html()
    assert "terra-map" in html


def test_map_card_includes_notes():
    card = map_card(_spec(notes=["A caveat"]), extra_notes=["Another"])
    html = PrefabApp(title="t", view=card).html()
    assert "caveat" in html and "Another" in html


def test_map_card_no_notes_when_empty():
    card = map_card(_spec())
    html = PrefabApp(title="t", view=card).html()
    assert "terra-map" in html
