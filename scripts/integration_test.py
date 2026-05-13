#!/usr/bin/env python3
"""Earthdata MCP Server Integration Tests

Verifies all functionality added in CMRNLP-103: pagination (limit/cursor/next_cursor),
field filtering, new search parameters, and new response fields across all 7 tools.

Usage:
    uv run python scripts/integration_test.py
    uv run python scripts/integration_test.py --url http://your-server:port/mcp/v1
"""

# pylint: disable=missing-docstring

import argparse
import asyncio
import base64
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# ── Default configuration ──────────────────────────────────────────────────────

DEFAULT_URL = "http://127.0.0.1:5001/mcp/v1"

# Stable CMR concept IDs used as test fixtures
COLLECTION_WITH_CITATIONS = "C3540909104-ESDIS"  # Known to have ≥12 citations
COLLECTION_WITH_GRANULES = (
    "C2036881712-POCLOUD"  # GHRSST L4 AVHRR_OI SST (daily, 32+ granules/month)
)


# ── Cursor helpers (mirrors models/pagination.py without importing it) ─────────


def encode_cursor(backend: str, value: Any) -> str:
    payload = json.dumps({"backend": backend, "value": value})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> dict:
    padding = 4 - len(cursor) % 4
    if padding != 4:
        cursor += "=" * padding
    return json.loads(base64.urlsafe_b64decode(cursor))


# ── Result types ───────────────────────────────────────────────────────────────


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Group:
    name: str
    checks: list[Check] = field(default_factory=list)


@dataclass
class Suite:
    name: str
    groups: list[Group] = field(default_factory=lambda: [Group("General")])
    error: str = ""  # set when the whole suite fails to run

    def group(self, name: str) -> None:
        self.groups.append(Group(name))

    def ok(self, name: str) -> None:
        self.groups[-1].checks.append(Check(name=name, passed=True))

    def fail(self, name: str, detail: str = "") -> None:
        self.groups[-1].checks.append(Check(name=name, passed=False, detail=detail))

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        self.groups[-1].checks.append(
            Check(name=name, passed=bool(condition), detail=detail if not condition else "")
        )
        return bool(condition)

    @property
    def checks(self) -> list[Check]:
        return [c for g in self.groups for c in g.checks]

    @property
    def n_passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def all_passed(self) -> bool:
        return not self.error and self.n_failed == 0


# ── MCP call helper ────────────────────────────────────────────────────────────


async def call(session: ClientSession, tool: str, **kwargs: Any) -> dict:
    """Call an MCP tool (stripping None values) and return the parsed JSON result."""
    args = {k: v for k, v in kwargs.items() if v is not None}
    result = await session.call_tool(tool, args)
    for block in result.content:
        if hasattr(block, "text"):
            return json.loads(block.text)
    raise ValueError(f"No text content returned by '{tool}'")


# ── Test suites ────────────────────────────────────────────────────────────────


async def suite_get_collections(session: ClientSession) -> Suite:
    s = Suite("get_collections")

    s.group("Pagination — first page")
    # Pagination — first page
    r = await call(session, "get_collections", keyword="sea surface temperature", limit=3)
    if not s.check(
        "status success", r["status"] == "success", f"got '{r['status']}': {r.get('error_message')}"
    ):
        return s

    items = r["collections"]
    s.check("limit=3 returns ≤3 items", len(items) <= 3, f"got {len(items)}")
    s.check(
        "next_cursor present on full page",
        r.get("next_cursor") is not None,
        "was None — unexpected for large result set",
    )
    s.check("total_hits > limit", r.get("total_hits", 0) > 3, f"total_hits={r.get('total_hits')}")

    s.group("Pagination — cursor advances")
    # Pagination — cursor advances
    if r.get("next_cursor"):
        r2 = await call(
            session,
            "get_collections",
            keyword="sea surface temperature",
            limit=3,
            cursor=r["next_cursor"],
        )
        ids1 = {c["concept_id"] for c in items}
        ids2 = {c["concept_id"] for c in r2.get("collections", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )

    s.group("Cursor format: value must be a dict with token + params (self-describing)")
    # Cursor format: value must be a dict with token + params (self-describing)
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    # Old-format scalar cursor returns error with 'outdated'
    r_old = await call(
        session,
        "get_collections",
        keyword="sea surface temperature",
        cursor=encode_cursor("cmr", "some-legacy-token"),
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(
        session,
        "get_collections",
        keyword="sea surface temperature",
        cursor=encode_cursor("kms", 5),
    )
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("Fields filtering")
    # Fields filtering
    rf = await call(
        session,
        "get_collections",
        keyword="sea surface temperature",
        limit=2,
        fields=["entry_title"],
    )
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("collections"):
        item = rf["collections"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested entry_title returned", "entry_title" in item)
        extra = [k for k in item if k not in ("concept_id", "entry_title")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    s.group("New search parameters")
    # New search parameters
    rp = await call(session, "get_collections", keyword="vegetation", platform=["Terra"], limit=3)
    s.check(
        "platform[] param accepted (no error)",
        rp["status"] != "error",
        f"error: {rp.get('error_message')}",
    )

    rh = await call(
        session, "get_collections", keyword="sea surface temperature", has_granules=True, limit=2
    )
    s.check(
        "has_granules param accepted (no error)",
        rh["status"] != "error",
        f"error: {rh.get('error_message')}",
    )

    s.group("New response fields")
    # New response fields
    rn = await call(session, "get_collections", keyword="sea surface temperature", limit=1)
    if s.check(
        "new response fields call succeeded", rn["status"] == "success", rn.get("error_message", "")
    ) and rn.get("collections"):
        c = rn["collections"][0]
        for fname in (
            "science_keywords",
            "collection_progress",
            "bounding_box",
            "data_centers",
            "archive_and_distribution_information",
        ):
            s.check(f"response field '{fname}' present", fname in c)

    if r.get("next_cursor"):
        err = await call(
            session,
            "get_collections",
            keyword="sea surface temperature",
            short_name="OVERRIDE",
            limit=3,
            cursor=r["next_cursor"],
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_granules(session: ClientSession) -> Suite:
    s = Suite("get_granules")

    base_args = {
        "collection_concept_id": COLLECTION_WITH_GRANULES,
        "temporal_start_date": "2024-01-01T00:00:00Z",
        "temporal_end_date": "2024-01-31T23:59:59Z",
    }

    s.group("Pagination — first page")
    # Pagination — first page
    r = await call(session, "get_granules", **base_args, limit=2)
    if not s.check(
        "status success", r["status"] == "success", f"got '{r['status']}': {r.get('error_message')}"
    ):
        return s

    granules = r["granules"]
    s.check("limit=2 returns ≤2 items", len(granules) <= 2, f"got {len(granules)}")
    s.check("next_cursor present on full page", r.get("next_cursor") is not None)

    s.group("Pagination — cursor advances")
    # Pagination — cursor advances
    if r.get("next_cursor"):
        r2 = await call(session, "get_granules", **base_args, limit=2, cursor=r["next_cursor"])
        ids1 = {g["concept_id"] for g in granules}
        ids2 = {g["concept_id"] for g in r2.get("granules", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )

    s.group("Cursor format: value must be a dict with token + params")
    # Cursor format: value must be a dict with token + params
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    # Old-format scalar cursor returns error with 'outdated'
    r_old = await call(
        session, "get_granules", **base_args, cursor=encode_cursor("cmr", "some-legacy-token")
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(session, "get_granules", **base_args, cursor=encode_cursor("kms", 5))
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("Fields filtering")
    # Fields filtering
    rf = await call(session, "get_granules", **base_args, limit=2, fields=["granule_ur"])
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("granules"):
        item = rf["granules"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested granule_ur returned", "granule_ur" in item)
        extra = [k for k in item if k not in ("concept_id", "granule_ur")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    s.group("New search parameters")
    # New search parameters
    rd = await call(session, "get_granules", **base_args, day_night_flag="DAY", limit=2)
    s.check(
        "day_night_flag param accepted (no error)",
        rd["status"] != "error",
        f"error: {rd.get('error_message')}",
    )

    rs = await call(session, "get_granules", **base_args, sort_key="-start_date", limit=2)
    s.check(
        "sort_key param accepted (no error)",
        rs["status"] != "error",
        f"error: {rs.get('error_message')}",
    )

    s.group("New response fields (check on un-filtered first-page result)")
    # New response fields (check on un-filtered first-page result)
    if granules:
        g = granules[0]
        for fname in ("production_date", "orbit_info", "additional_attributes"):
            s.check(f"response field '{fname}' present", fname in g)

    if r.get("next_cursor"):
        err = await call(
            session,
            "get_granules",
            collection_concept_id=COLLECTION_WITH_GRANULES,
            limit=2,
            temporal_start_date="2020-01-01T00:00:00Z",
            cursor=r["next_cursor"],
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_keywords(session: ClientSession) -> Suite:
    s = Suite("get_keywords")

    s.group("Pagination — first page")
    # Pagination — first page
    r = await call(session, "get_keywords", query="temperature", limit=3)
    if not s.check(
        "status success", r["status"] == "success", f"got '{r['status']}': {r.get('error_message')}"
    ):
        return s

    keywords = r["keywords"]
    s.check("limit=3 returns ≤3 items", len(keywords) <= 3, f"got {len(keywords)}")
    s.check(
        "total_hits reflects full count (> limit)",
        r.get("total_hits", 0) > 3,
        f"total_hits={r.get('total_hits')}",
    )
    s.check("next_cursor present when total_hits > limit", r.get("next_cursor") is not None)

    s.group("Pagination — cursor advances, total_hits stable")
    # Pagination — cursor advances, total_hits stable
    if r.get("next_cursor"):
        r2 = await call(
            session, "get_keywords", query="temperature", limit=3, cursor=r["next_cursor"]
        )
        labels1 = {kw["prefLabel"] for kw in keywords}
        labels2 = {kw["prefLabel"] for kw in r2.get("keywords", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            labels1.isdisjoint(labels2),
            f"overlap: {labels1 & labels2}",
        )
        s.check(
            "total_hits identical across pages",
            r.get("total_hits") == r2.get("total_hits"),
            f"page1={r.get('total_hits')}, page2={r2.get('total_hits')}",
        )

    s.group("KMS cursor format: value must be a dict with offset/query/scheme")
    # KMS cursor format: value must be a dict with offset/query/scheme
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "KMS cursor value is dict (self-describing)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("KMS cursor has 'offset' key", isinstance(cv, dict) and "offset" in cv)
        s.check("KMS cursor has 'query' key", isinstance(cv, dict) and "query" in cv)
        s.check("KMS cursor has 'scheme' key", isinstance(cv, dict) and "scheme" in cv)

    # Old-format scalar KMS cursor returns error with 'outdated'
    r_old = await call(
        session, "get_keywords", query="temperature", cursor=encode_cursor("kms", 20)
    )
    s.check(
        "old-format KMS cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Self-describing cursor: changed query on page 2 must be ignored

    # Cross-backend cursor rejected (keywords uses "kms"; send a "cmr" cursor)
    r_bad = await call(
        session, "get_keywords", query="temperature", cursor=encode_cursor("cmr", "tok-xyz")
    )
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    if r.get("next_cursor"):
        err = await call(
            session,
            "get_keywords",
            query="temperature",
            scheme="instruments",
            limit=2,
            cursor=r["next_cursor"],
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_citations(session: ClientSession) -> Suite:
    s = Suite("get_citations")

    s.group("Collection flow — first page")
    # Collection flow — first page
    r = await call(
        session, "get_citations", collection_concept_id=COLLECTION_WITH_CITATIONS, limit=5
    )
    if not s.check(
        "collection flow status success",
        r["status"] == "success",
        f"got '{r['status']}': {r.get('error_message')}",
    ):
        return s

    citations = r["citations"]
    s.check("limit=5 returns ≤5 citations", len(citations) <= 5, f"got {len(citations)}")
    s.check("total_hits > 0", r.get("total_hits", 0) > 0, f"total_hits={r.get('total_hits')}")
    s.check("next_cursor present (collection has >5 citations)", r.get("next_cursor") is not None)

    s.group("Pagination — cursor advances")
    # Pagination — cursor advances
    if r.get("next_cursor"):
        r2 = await call(
            session,
            "get_citations",
            collection_concept_id=COLLECTION_WITH_CITATIONS,
            limit=5,
            cursor=r["next_cursor"],
        )
        ids1 = {c["concept_id"] for c in citations}
        ids2 = {c["concept_id"] for c in r2.get("citations", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )

    s.group("Cursor format: value must be dict with token + params")
    # Cursor format: value must be dict with token + params
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    s.group("total_hits consistent on page 2 (Phase 1 skipped should not zero out total_hits)")
    # total_hits consistent on page 2 (Phase 1 skipped should not zero out total_hits)
    if r.get("next_cursor"):
        r2 = await call(
            session,
            "get_citations",
            collection_concept_id=COLLECTION_WITH_CITATIONS,
            limit=5,
            cursor=r["next_cursor"],
        )
        s.check(
            "total_hits on page 2 matches page 1 (not zeroed by Phase 1 skip)",
            r2.get("total_hits", 0) == r.get("total_hits", 0),
            f"page1={r.get('total_hits')}, page2={r2.get('total_hits')}",
        )

    # Old-format scalar cursor returns 'outdated' error
    r_old = await call(
        session,
        "get_citations",
        collection_concept_id=COLLECTION_WITH_CITATIONS,
        cursor=encode_cursor("cmr", "some-legacy-token"),
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(
        session,
        "get_citations",
        collection_concept_id=COLLECTION_WITH_CITATIONS,
        cursor=encode_cursor("kms", 5),
    )
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("Fields filtering (new in Phase 6)")
    # Fields filtering (new in Phase 6)
    rf = await call(
        session,
        "get_citations",
        collection_concept_id=COLLECTION_WITH_CITATIONS,
        limit=3,
        fields=["name"],
    )
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("citations"):
        item = rf["citations"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested name returned", "name" in item)
        extra = [k for k in item if k not in ("concept_id", "name")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    s.group("Provider filter (new in Phase 6)")
    # Provider filter (new in Phase 6)
    rp = await call(
        session,
        "get_citations",
        collection_concept_id=COLLECTION_WITH_CITATIONS,
        provider="ESDIS",
        limit=5,
    )
    s.check(
        "provider filter accepted (no error)",
        rp["status"] != "error",
        f"error: {rp.get('error_message')}",
    )
    if s.check(
        "provider filter call succeeded", rp["status"] == "success", rp.get("error_message", "")
    ):
        s.check("provider filter returns citations", len(rp.get("citations", [])) > 0)

    s.group("Identifier flow")
    # Identifier flow
    if citations:
        doi = citations[0].get("identifier")
        if doi:
            ri = await call(session, "get_citations", identifier=doi)
            s.check(
                "identifier flow: status success or no_results",
                ri["status"] in ("success", "no_results"),
                f"error: {ri.get('error_message')}",
            )

    if r.get("next_cursor"):
        err = await call(
            session,
            "get_citations",
            collection_concept_id=COLLECTION_WITH_CITATIONS,
            provider="OVERRIDE",
            limit=2,
            cursor=r["next_cursor"],
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_services(session: ClientSession) -> Suite:
    s = Suite("get_services")

    s.group("Keyword-only discovery (no collection_concept_id)")
    # Keyword-only discovery (no collection_concept_id)
    r = await call(session, "get_services", keyword="OPeNDAP", limit=3)
    if not s.check(
        "keyword-only status success",
        r["status"] == "success",
        f"got '{r['status']}': {r.get('error_message')}",
    ):
        return s

    services = r["services"]
    s.check("keyword-only: returns ≤3 items", len(services) <= 3, f"got {len(services)}")
    s.check("next_cursor present", r.get("next_cursor") is not None)

    s.group("Pagination — cursor advances")
    # Pagination — cursor advances
    if r.get("next_cursor"):
        r2 = await call(
            session, "get_services", keyword="OPeNDAP", limit=3, cursor=r["next_cursor"]
        )
        ids1 = {sv["concept_id"] for sv in services}
        ids2 = {sv["concept_id"] for sv in r2.get("services", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )

    s.group("Cursor format: value must be dict with token + params")
    # Cursor format: value must be dict with token + params
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    # Old-format scalar cursor returns 'outdated' error
    r_old = await call(
        session, "get_services", keyword="OPeNDAP", cursor=encode_cursor("cmr", "some-legacy-token")
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(session, "get_services", keyword="OPeNDAP", cursor=encode_cursor("kms", 5))
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("Type-only discovery")
    # Type-only discovery
    rt = await call(session, "get_services", type="OPeNDAP", limit=3)
    s.check(
        "type-only: returns results (no error)",
        rt["status"] != "error",
        f"error: {rt.get('error_message')}",
    )

    s.group("No-args validation")
    # No-args validation
    r_none = await call(session, "get_services")
    s.check("no-args returns validation error", r_none["status"] == "error")

    s.group("Fields filtering")
    # Fields filtering
    rf = await call(session, "get_services", keyword="OPeNDAP", limit=3, fields=["name", "url"])
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("services"):
        item = rf["services"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested name returned", "name" in item)
        s.check("fields: requested url returned", "url" in item)
        extra = [k for k in item if k not in ("concept_id", "name", "url")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    s.group("New response fields (new in Phase 4)")
    # New response fields (new in Phase 4)
    if services:
        svc = services[0]
        s.check("response field 'service_keywords' present", "service_keywords" in svc)
        s.check("response field 'service_organizations' present", "service_organizations" in svc)

    if r.get("next_cursor"):
        err = await call(
            session,
            "get_services",
            collection_concept_id=COLLECTION_WITH_GRANULES,
            keyword="OVERRIDE",
            limit=2,
            cursor=r["next_cursor"],
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_tools(session: ClientSession) -> Suite:
    s = Suite("get_tools")

    # NOTE: CMR's tools endpoint does NOT support a `type` parameter (unlike services).
    s.group("All discovery tests use `keyword` instead.")
    # All discovery tests use `keyword` instead.

    s.group("Keyword-only discovery — first page")
    # Keyword-only discovery — first page
    r = await call(session, "get_tools", keyword="Giovanni", limit=3)
    if not s.check(
        "keyword-only status success",
        r["status"] == "success",
        f"got '{r['status']}': {r.get('error_message')}",
    ):
        return s

    tools = r["tools"]
    s.check("keyword-only: returns ≤3 items", len(tools) <= 3, f"got {len(tools)}")

    s.group("Pagination — cursor advances (use a broader keyword to get enough results)")
    # Pagination — cursor advances (use a broader keyword to get enough results)
    r_broad = await call(session, "get_tools", keyword="data", limit=3)
    if r_broad.get("next_cursor"):
        r2 = await call(
            session, "get_tools", keyword="data", limit=3, cursor=r_broad["next_cursor"]
        )
        ids1 = {t["concept_id"] for t in r_broad["tools"]}
        ids2 = {t["concept_id"] for t in r2.get("tools", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )
    else:
        s.check("next_cursor present or result set small", r_broad.get("total_hits", 0) <= 3)

    s.group("Cursor format: value must be dict with token + params")
    # Cursor format: value must be dict with token + params
    if s.check(
        "next_cursor present for cursor format test", r_broad.get("next_cursor") is not None
    ):
        parsed = decode_cursor(r_broad["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    # Old-format scalar cursor returns 'outdated' error
    r_old = await call(
        session, "get_tools", keyword="Giovanni", cursor=encode_cursor("cmr", "some-legacy-token")
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(session, "get_tools", keyword="Giovanni", cursor=encode_cursor("kms", 5))
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("No-args validation")
    # No-args validation
    r_none = await call(session, "get_tools")
    s.check("no-args returns validation error", r_none["status"] == "error")

    s.group("Fields filtering (new in Phase 4 cleanup)")
    # Fields filtering (new in Phase 4 cleanup)
    rf = await call(session, "get_tools", keyword="Giovanni", limit=3, fields=["name"])
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("tools"):
        item = rf["tools"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested name returned", "name" in item)
        extra = [k for k in item if k not in ("concept_id", "name")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    if r_broad.get("next_cursor"):
        err = await call(
            session, "get_tools", keyword="OVERRIDE", limit=2, cursor=r_broad["next_cursor"]
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


async def suite_get_variables(session: ClientSession) -> Suite:
    s = Suite("get_variables")

    s.group("Keyword search — first page")
    # Keyword search — first page
    r = await call(session, "get_variables", keyword="sea_surface_temperature", limit=3)
    if not s.check(
        "keyword search status success",
        r["status"] == "success",
        f"got '{r['status']}': {r.get('error_message')}",
    ):
        return s

    variables = r["variables"]
    s.check("limit=3 returns ≤3 items", len(variables) <= 3, f"got {len(variables)}")

    s.group("Pagination — cursor advances when more exist")
    # Pagination — cursor advances when more exist
    if r.get("next_cursor"):
        r2 = await call(
            session,
            "get_variables",
            keyword="sea_surface_temperature",
            limit=3,
            cursor=r["next_cursor"],
        )
        ids1 = {v["concept_id"] for v in variables}
        ids2 = {v["concept_id"] for v in r2.get("variables", [])}
        s.check(
            "cursor: page 2 is distinct from page 1",
            ids1.isdisjoint(ids2),
            f"overlap: {ids1 & ids2}",
        )
    else:
        s.check(
            "next_cursor absent when all results fit on one page",
            r.get("total_hits", 0) <= 3,
            f"total_hits={r.get('total_hits')} but no cursor",
        )

    s.group("Cursor format: value must be dict with token + params")
    # Cursor format: value must be dict with token + params
    if r.get("next_cursor"):
        parsed = decode_cursor(r["next_cursor"])
        cv = parsed.get("value")
        s.check(
            "cursor value is dict (self-describing format)", isinstance(cv, dict), f"got {type(cv)}"
        )
        s.check("cursor value has 'token' key", isinstance(cv, dict) and "token" in cv)
        s.check("cursor value has 'params' key", isinstance(cv, dict) and "params" in cv)

    # Old-format scalar cursor returns 'outdated' error
    r_old = await call(
        session,
        "get_variables",
        keyword="sea_surface_temperature",
        cursor=encode_cursor("cmr", "some-legacy-token"),
    )
    s.check(
        "old-format cursor returns 'outdated' error",
        r_old["status"] == "error" and "outdated" in r_old.get("error_message", "").lower(),
        r_old.get("error_message", ""),
    )

    # Cross-backend cursor rejected
    r_bad = await call(
        session, "get_variables", keyword="sea_surface_temperature", cursor=encode_cursor("kms", 5)
    )
    s.check(
        "cross-backend cursor returns error",
        r_bad["status"] == "error" and "cursor" in r_bad.get("error_message", "").lower(),
    )

    s.group("Fields filtering (new in Phase 4 cleanup)")
    # Fields filtering (new in Phase 4 cleanup)
    rf = await call(
        session, "get_variables", keyword="sea_surface_temperature", limit=3, fields=["long_name"]
    )
    if s.check(
        "fields call succeeded", rf["status"] == "success", rf.get("error_message", "")
    ) and rf.get("variables"):
        item = rf["variables"][0]
        s.check("fields: concept_id always returned", "concept_id" in item)
        s.check("fields: requested long_name returned", "long_name" in item)
        extra = [k for k in item if k not in ("concept_id", "name", "long_name")]
        s.check("fields: unrequested keys absent", not extra, f"unexpected keys: {extra}")

    s.group("Collection flow")
    # Collection flow
    rc = await call(
        session, "get_variables", collection_concept_id=COLLECTION_WITH_GRANULES, limit=3
    )
    s.check(
        "collection flow: no error", rc["status"] != "error", f"error: {rc.get('error_message')}"
    )

    s.group("No-args validation")
    # No-args validation
    r_none = await call(session, "get_variables")
    s.check("no-args returns validation error", r_none["status"] == "error")

    if r.get("next_cursor"):
        err = await call(
            session, "get_variables", keyword="OVERRIDE", limit=2, cursor=r["next_cursor"]
        )
        s.check(
            "rejects cursor override",
            err.get("status") == "error" and "query-scoped" in err.get("error_message", ""),
            f"got: {err}",
        )

    return s


# ── Output ─────────────────────────────────────────────────────────────────────

BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

WIDTH = 72


def print_summary(url: str, suites: list[Suite], elapsed: float) -> None:
    total_checks = sum(len(s.checks) for s in suites)
    total_passed = sum(s.n_passed for s in suites)
    total_failed = total_checks - total_passed

    print()
    print("═" * WIDTH)
    print(f"{BOLD}  EARTHDATA MCP — INTEGRATION TESTS{RESET}  {DIM}{url}{RESET}")
    print("═" * WIDTH)

    for s in suites:
        if s.error:
            print(
                f"\n  {YELLOW}⊘{RESET}  {BOLD}{s.name}{RESET}  {DIM}suite error — {s.error}{RESET}"
            )
            continue

        icon = f"{GREEN}✅{RESET}" if s.all_passed else f"{RED}❌{RESET}"
        frac = f"{DIM}{s.n_passed}/{len(s.checks)}{RESET}"
        print(f"\n  {icon}  {BOLD}{s.name}{RESET}  {frac}")

        for c in s.checks:
            if c.passed:
                print(f"        {GREEN}✓{RESET}  {c.name}")
            else:
                print(f"        {RED}✗{RESET}  {BOLD}{c.name}{RESET}")
                if c.detail:
                    print(f"           {DIM}→ {c.detail}{RESET}")

    print()
    print("─" * WIDTH)
    color = GREEN if total_failed == 0 else RED
    print(
        f"  {color}{BOLD}{total_passed}/{total_checks} checks passed{RESET}  {DIM}({elapsed:.1f}s){RESET}"
    )
    if total_failed:
        print(f"  {RED}{total_failed} check{'s' if total_failed > 1 else ''} failed{RESET}")
    print("─" * WIDTH)
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

SUITES = [
    suite_get_collections,
    suite_get_granules,
    suite_get_keywords,
    suite_get_citations,
    suite_get_services,
    suite_get_tools,
    suite_get_variables,
]


async def main(url: str) -> int:
    suites: list[Suite] = []
    start = time.monotonic()

    try:
        # pylint: disable=used-before-assignment
        async with (
            streamablehttp_client(url) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            for fn in SUITES:
                name = fn.__name__.removeprefix("suite_")
                print(f"  {DIM}running {name}…{RESET}", end="\r", flush=True)
                try:
                    suite = await fn(session)
                except Exception as exc:  # noqa: BLE001
                    suite = Suite(name)
                    suite.error = str(exc)
                suites.append(suite)
    except Exception as exc:  # noqa: BLE001
        print(f"\n{RED}Could not connect to {url}{RESET}")
        print(f"  {exc}\n")
        return 1

    elapsed = time.monotonic() - start
    print(" " * WIDTH, end="\r")  # clear the running line
    print_summary(url, suites, elapsed)

    return 1 if any(s.n_failed > 0 or s.error for s in suites) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Earthdata MCP integration tests")
    parser.add_argument("--url", default=DEFAULT_URL, help="MCP server URL")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.url)))
