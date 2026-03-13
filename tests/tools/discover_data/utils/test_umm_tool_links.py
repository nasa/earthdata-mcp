"""Tests for UMM tool-link utilities."""

import logging
from datetime import UTC, datetime

from models.tools.discover_data import SpatialConstraint, TemporalConstraint
from tools.discover_data.utils.umm_tool_links import (
    _expand_url_template,
    _prioritize_tools,
    _resolve_tool_url,
    _resolve_value,
)


class TestResolveValue:
    """Tests for _resolve_value — maps ValueType URI to a concrete string."""

    def test_resolves_start_date(self):
        """Should return ISO-format start date string."""
        t = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        result = _resolve_value("https://schema.org/startDate", "C1-P", t, None)
        assert result == datetime(2020, 1, 1, tzinfo=UTC).isoformat()

    def test_resolves_start_time(self):
        """Should return ISO-format start time string."""
        t = TemporalConstraint(start_date=datetime(2020, 6, 15, tzinfo=UTC))
        result = _resolve_value("https://schema.org/startTime", "C1-P", t, None)
        assert result == datetime(2020, 6, 15, tzinfo=UTC).isoformat()

    def test_resolves_end_date(self):
        """Should return ISO-format end date string."""
        t = TemporalConstraint(end_date=datetime(2020, 12, 31, tzinfo=UTC))
        result = _resolve_value("https://schema.org/endDate", "C1-P", t, None)
        assert result == datetime(2020, 12, 31, tzinfo=UTC).isoformat()

    def test_resolves_end_time(self):
        """Should return ISO-format end time string."""
        t = TemporalConstraint(end_date=datetime(2020, 12, 31, tzinfo=UTC))
        result = _resolve_value("https://schema.org/endTime", "C1-P", t, None)
        assert result == datetime(2020, 12, 31, tzinfo=UTC).isoformat()

    def test_resolves_dataset_time_interval_with_both_bounds(self):
        """Should return start/end interval string when both bounds are set."""
        t = TemporalConstraint(
            start_date=datetime(2020, 1, 1, tzinfo=UTC),
            end_date=datetime(2020, 12, 31, tzinfo=UTC),
        )
        result = _resolve_value("https://schema.org/datasetTimeInterval", "C1-P", t, None)
        assert "/" in result
        assert "2020-01-01" in result
        assert "2020-12-31" in result

    def test_resolves_interval_with_open_end(self):
        """Open-ended interval should use '..' for the missing end bound."""
        t = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=None)
        result = _resolve_value("https://schema.org/datasetTimeInterval", "C1-P", t, None)
        assert result.endswith("/..")

    def test_resolves_interval_with_open_end_never_uses_python_none_string(self):
        """Open-ended interval serialization must not emit '/None'."""
        t = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=None)
        result = _resolve_value("https://schema.org/datasetTimeInterval", "C1-P", t, None)
        assert "/None" not in result

    def test_resolves_schema_box_from_wkt(self):
        """Should return bbox string derived from the WKT polygon."""
        s = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        result = _resolve_value("https://schema.org/box", "C1-P", None, s)
        assert result == "-10.0,20.0,30.0,60.0"

    def test_resolves_cmr_concept_id(self):
        """Should return the raw concept ID unchanged."""
        result = _resolve_value(
            "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id",
            "C9999-PROV",
            None,
            None,
        )
        assert result == "C9999-PROV"

    def test_resolves_short_name(self):
        """Should return the collection short name when provided."""
        result = _resolve_value("shortName", "C1-P", None, None, short_name="TRMM_3B42")
        assert result == "TRMM_3B42"

    def test_returns_none_for_short_name_when_not_provided(self):
        """Should return None when short_name is not supplied to the call."""
        result = _resolve_value("shortName", "C1-P", None, None)
        assert result is None

    def test_returns_none_for_unknown_value_type(self):
        """Should return None for any unrecognised ValueType URI."""
        result = _resolve_value("longName", "C1-P", None, None)
        assert result is None

    def test_returns_none_when_value_type_is_none(self):
        """Should return None immediately when value_type is None."""
        result = _resolve_value(None, "C1-P", None, None)
        assert result is None

    def test_returns_none_for_start_date_when_no_temporal_constraint(self):
        """Should return None for startDate when temporal is not set."""
        result = _resolve_value("https://schema.org/startDate", "C1-P", None, None)
        assert result is None

    def test_returns_none_for_box_when_no_wkt(self):
        """Should return None for box when the spatial constraint has no WKT."""
        result = _resolve_value("https://schema.org/box", "C1-P", None, SpatialConstraint())
        assert result is None


# ---------------------------------------------------------------------------
# _expand_url_template
# ---------------------------------------------------------------------------


class TestExpandUrlTemplate:
    """Tests for _expand_url_template — minimal RFC 6570 query-string expansion."""

    def test_expands_query_string_with_known_values(self):
        """Should produce a ?key=value query string for known vars."""
        result = _expand_url_template(
            "https://example.com{?start,end}",
            {"start": "2020-01-01", "end": "2020-12-31"},
        )
        assert result == "https://example.com?start=2020-01-01&end=2020-12-31"

    def test_omits_unknown_query_vars(self):
        """Should exclude vars not in the values dict."""
        result = _expand_url_template(
            "https://example.com{?a,b,c}",
            {"a": "1"},
        )
        assert result == "https://example.com?a=1"

    def test_returns_base_url_when_all_vars_unknown(self):
        """Should produce no '?' when nothing is resolvable."""
        result = _expand_url_template("https://example.com{?a,b}", {})
        assert result == "https://example.com"

    def test_expands_simple_path_variable(self):
        """Should substitute {var} in the path."""
        result = _expand_url_template("https://example.com/{cid}/data", {"cid": "C1-P"})
        assert result == "https://example.com/C1-P/data"

    def test_passes_through_url_without_templates(self):
        """A URL with no template expressions should be returned unchanged."""
        url = "https://static.example.com/viewer"
        assert _expand_url_template(url, {}) == url

    def test_giovanni_like_template(self):
        """Should correctly expand a template similar to the Giovanni PotentialAction."""
        template = (
            "https://giovanni.example.com/#service=TmAvMp{?dataKeyword,starttime,endtime,bbox}"
        )
        values = {
            "starttime": "2020-01-01T00:00:00+00:00",
            "endtime": "2020-12-31T00:00:00+00:00",
            "bbox": "-10.0,20.0,30.0,60.0",
        }
        result = _expand_url_template(template, values)
        assert result.startswith("https://giovanni.example.com/#service=TmAvMp?")
        assert "starttime=" in result
        assert "endtime=" in result
        assert "bbox=" in result
        assert "dataKeyword" not in result  # not in values, should be omitted

    # --- RFC 6570 reserved expansion {+var} ---

    def test_expands_reserved_var_with_known_value(self):
        """{+var} should be substituted when the value is present."""
        result = _expand_url_template(
            "https://soto.example.com/?t={+date}",
            {"date": "2020-01-15"},
        )
        assert result == "https://soto.example.com/?t=2020-01-15"

    def test_strips_empty_reserved_var_from_query(self):
        """{+var} with no value should remove the surrounding parameter entirely."""
        result = _expand_url_template(
            "https://soto.example.com/?l={+layers}&t={+date}",
            {},
        )
        # Both params have no value — query string should be gone entirely
        assert result == "https://soto.example.com/"

    def test_strips_only_missing_reserved_vars(self):
        """{+var} present values should be kept; missing ones should be dropped."""
        result = _expand_url_template(
            "https://soto.example.com/?l={+layers}&t={+date}",
            {"date": "2020-01-15"},
        )
        assert "t=2020-01-15" in result
        assert "l=" not in result

    def test_soto_url_without_temporal_strips_t_param(self):
        """The real SOTO URL template t={+date} should be removed when date is None."""
        template = "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}&t={+date}"
        result = _expand_url_template(template, {})
        assert "{+date}" not in result
        assert "{+layers}" not in result
        assert "t=" not in result
        assert "l=" not in result


# ---------------------------------------------------------------------------
# _resolve_tool_url
# ---------------------------------------------------------------------------


class TestResolveToolUrl:
    """Tests for _resolve_tool_url — maps raw tool dict + context to {name, url}."""

    def test_produces_name_and_resolved_url(self):
        """Should return a dict with name and a URL populated from context."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?starttime,endtime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
                {
                    "value_name": "endtime",
                    "value_type": "https://schema.org/endDate",
                    "required": False,
                },
            ],
        }
        temporal = TemporalConstraint(
            start_date=datetime(2020, 1, 1, tzinfo=UTC),
            end_date=datetime(2020, 12, 31, tzinfo=UTC),
        )
        result = _resolve_tool_url(tool, "C1-P", temporal, None)
        assert result["name"] == "Giovanni"
        assert "starttime=" in result["url"]
        assert "endtime=" in result["url"]

    def test_injects_single_gibs_layer_with_base_layer(self):
        """Single GIBS layer should appear followed by BlueMarble_NextGeneration."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(
            tool, "C1-P", None, None, gibs_layers=["MODIS_Terra_CorrectedReflectance_TrueColor"]
        )
        assert (
            "l=MODIS_Terra_CorrectedReflectance_TrueColor,BlueMarble_NextGeneration"
            in result["url"]
        )

    def test_multiple_gibs_layers_hidden_with_base_layer(self):
        """Secondary layers should be (hidden); BlueMarble_NextGeneration appended last."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(
            tool,
            "C1-P",
            None,
            None,
            gibs_layers=["LayerA", "LayerB", "LayerC"],
        )
        assert "l=LayerA,LayerB(hidden),LayerC(hidden),BlueMarble_NextGeneration" in result["url"]

    def test_strips_layers_param_when_gibs_layers_is_empty(self):
        """Should remove l= from URL when gibs_layers is empty."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}&t={+date}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None, gibs_layers=[])
        assert "l=" not in result["url"]
        assert "{+layers}" not in result["url"]

    def test_returns_none_url_when_no_template(self):
        """Should fall back to base_url when url_template is absent."""
        tool = {"name": "My Tool", "url_template": None, "base_url": None, "query_inputs": []}
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {"name": "My Tool", "url": None, "topic": None}

    def test_falls_back_to_base_url_when_no_template(self):
        """Should return base_url as url when url_template is absent but base_url exists."""
        tool = {
            "name": "My Tool",
            "url_template": None,
            "base_url": "https://my-tool.example.com",
            "query_inputs": [],
            "topic": "Data discovery",
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {
            "name": "My Tool",
            "url": "https://my-tool.example.com",
            "topic": "Data discovery",
        }

    def test_omits_params_with_no_context_value(self):
        """Params whose ValueType doesn't resolve should be absent from the URL."""
        tool = {
            "name": "Tool",
            "url_template": "https://tool.example.com{?longName,starttime}",
            "query_inputs": [
                {"value_name": "longName", "value_type": "longName", "required": False},
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
            ],
        }
        temporal = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        result = _resolve_tool_url(tool, "C1-P", temporal, None)
        assert "starttime=" in result["url"]
        assert "longName" not in result["url"]

    def test_falls_back_to_base_url_when_required_input_is_missing(self):
        """If any required query input cannot be resolved, skip emitting the tool link."""
        tool = {
            "name": "Required Tool",
            "base_url": "https://tool.example.com/home",
            "url_template": "https://tool.example.com{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                }
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", temporal=None, spatial=None)
        assert result is None

    def test_returns_none_url_when_required_input_missing_and_no_base_url(self):
        """If required input is missing and base_url is absent, the tool should still be skipped."""
        tool = {
            "name": "Required Tool",
            "base_url": None,
            "url_template": "https://tool.example.com{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                }
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", temporal=None, spatial=None)
        assert result is None

    def test_logs_when_required_input_is_missing(self, caplog):
        """Missing required inputs should emit a warning to support monitoring frequency."""
        tool = {
            "name": "Required Tool",
            "base_url": "https://tool.example.com/home",
            "url_template": "https://tool.example.com{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                }
            ],
        }

        with caplog.at_level(logging.WARNING):
            result = _resolve_tool_url(tool, "C1-P", temporal=None, spatial=None)

        assert result is None
        assert "Skipping tool link due to missing required inputs" in caplog.text

    def test_handles_empty_query_inputs(self):
        """A tool with no query_inputs should resolve to the template URL unchanged."""
        tool = {
            "name": "Static Tool",
            "url_template": "https://static.example.com/viewer",
            "query_inputs": [],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {
            "name": "Static Tool",
            "url": "https://static.example.com/viewer",
            "topic": None,
        }

    def test_resolves_concept_id_param(self):
        """Should fill concept_id when ValueType is the CMR concept ID URI."""
        tool = {
            "name": "Earthdata Search",
            "url_template": "https://search.earthdata.nasa.gov/search?q={cid}",
            "query_inputs": [
                {
                    "value_name": "cid",
                    "value_type": "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id",
                    "required": True,
                }
            ],
        }
        result = _resolve_tool_url(tool, "C9999-PROV", None, None)
        assert "C9999-PROV" in result["url"]

    def test_resolves_bbox_from_spatial_constraint(self):
        """Should substitute bbox when ValueType is schema.org/box."""
        tool = {
            "name": "Map Viewer",
            "url_template": "https://map.example.com{?bbox}",
            "query_inputs": [
                {"value_name": "bbox", "value_type": "https://schema.org/box", "required": False}
            ],
        }
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        result = _resolve_tool_url(tool, "C1-P", None, spatial)
        assert "bbox=" in result["url"]
        assert "-10.0" in result["url"]

    def test_topic_is_surfaced_in_resolved_link(self):
        """topic from the raw tool dict should appear in the resolved link."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com/",
            "query_inputs": [],
            "topic": "Data analysis and visualization",
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result["topic"] == "Data analysis and visualization"

    def test_resolves_short_name_param(self):
        """Should fill shortName when ValueType is 'shortName' and short_name is provided."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?dataKeyword}",
            "query_inputs": [
                {"value_name": "dataKeyword", "value_type": "shortName", "required": False}
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None, short_name="TRMM_3B42")
        assert "dataKeyword=TRMM_3B42" in result["url"]

    def test_omits_short_name_param_when_not_available(self):
        """Should omit the shortName param when no short_name is provided."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?dataKeyword}",
            "query_inputs": [
                {"value_name": "dataKeyword", "value_type": "shortName", "required": False}
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result["url"] == "https://giovanni.example.com"


# ---------------------------------------------------------------------------
# _prioritize_tools
# ---------------------------------------------------------------------------


class TestPrioritizeTools:
    """Tests for _prioritize_tools."""

    def _make_tool(
        self,
        name: str,
        topic: str | None = None,
        url_template: str | None = None,
    ) -> dict:
        return {
            "name": name,
            "topic": topic,
            "url_template": url_template,
            "base_url": "https://example.com",
            "query_inputs": [],
        }

    def test_visualization_tools_sorted_first(self):
        """Tools whose topic contains 'visualization' should appear before others."""
        tools = [
            self._make_tool("Plain Tool", topic="Data access"),
            self._make_tool("Viz Tool", topic="Data analysis and visualization"),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz Tool"
        assert result[1]["name"] == "Plain Tool"

    def test_tools_with_url_template_sorted_before_base_url_only(self):
        """Within the same topic tier, tools with a URL template rank higher."""
        tools = [
            self._make_tool("Base-URL Only", topic="Data access"),
            self._make_tool(
                "Deep Link", topic="Data access", url_template="https://example.com{?q}"
            ),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Deep Link"
        assert result[1]["name"] == "Base-URL Only"

    def test_visualization_with_template_beats_visualization_without(self):
        """Visualization + URL template beats visualization with base_url only."""
        tools = [
            self._make_tool("Viz No Template", topic="Earth science visualization"),
            self._make_tool(
                "Viz With Template",
                topic="Earth science visualization",
                url_template="https://t.example.com{?q}",
            ),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz With Template"
        assert result[1]["name"] == "Viz No Template"

    def test_returns_all_tools_regardless_of_count(self):
        """Should return all tools without truncating."""
        tools = [self._make_tool(f"Tool {i}") for i in range(6)]

        result = _prioritize_tools(tools)

        assert len(result) == 6

    def test_returns_all_when_three_or_fewer(self):
        """Should not truncate if the input has 3 or fewer tools."""
        tools = [self._make_tool(f"Tool {i}") for i in range(2)]

        result = _prioritize_tools(tools)

        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        """Should return an empty list without raising."""
        assert _prioritize_tools([]) == []

    def test_visualization_beats_non_visualization_regardless_of_template(self):
        """Visualization tools should rank above non-visualization deep links."""
        tools = [
            self._make_tool(
                "Non-Viz Deep Link", topic="Data access", url_template="https://a.com{?q}"
            ),
            self._make_tool("Viz Base Only", topic="Earth science visualization"),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz Base Only"
        assert result[1]["name"] == "Non-Viz Deep Link"
