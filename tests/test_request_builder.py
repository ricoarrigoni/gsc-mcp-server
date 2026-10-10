from datetime import date

import pytest

from gsc_mcp_server.constants import MAX_ROW_LIMIT
from gsc_mcp_server.gsc.request import (
    RequestValidationError,
    build_search_analytics_request,
)

TODAY = date(2026, 10, 10)


def build(**kwargs):
    kwargs.setdefault("today", TODAY)
    return build_search_analytics_request(**kwargs)


def test_flat_filters_are_wrapped_in_dimension_filter_groups():
    # A top-level "filters" key is silently ignored by Search Console, which
    # returns unfiltered data that looks correct.
    body = build(
        dimensions=["query"],
        filters=[
            {
                "dimension": "page",
                "operator": "equals",
                "expression": "https://example.com/post",
            }
        ],
    )
    assert "filters" not in body
    assert body["dimensionFilterGroups"] == [
        {
            "groupType": "and",
            "filters": [
                {
                    "dimension": "page",
                    "operator": "equals",
                    "expression": "https://example.com/post",
                }
            ],
        }
    ]


def test_no_filter_key_when_no_filters_given():
    body = build(dimensions=["query"])
    assert "dimensionFilterGroups" not in body


def test_search_appearance_cannot_combine_with_other_dimensions():
    with pytest.raises(RequestValidationError, match="only dimension"):
        build(dimensions=["searchAppearance", "query"])


def test_search_appearance_alone_is_fine():
    body = build(dimensions=["searchAppearance"])
    assert body["dimensions"] == ["searchAppearance"]


def test_row_limit_is_clamped_to_the_context_safe_cap():
    body = build(row_limit=20_000)
    assert body["rowLimit"] == MAX_ROW_LIMIT


def test_row_limit_floor_is_one():
    assert build(row_limit=0)["rowLimit"] >= 1


def test_unknown_dimension_is_rejected():
    with pytest.raises(RequestValidationError, match="Unknown dimension"):
        build(dimensions=["querystring"])


def test_unknown_filter_operator_is_rejected():
    with pytest.raises(RequestValidationError, match="operator"):
        build(
            filters=[
                {"dimension": "query", "operator": "startsWith", "expression": "x"}
            ]
        )


def test_defaults():
    body = build()
    assert body["dimensions"] == ["query"]
    assert body["type"] == "web"
    assert body["dataState"] == "all"
    assert "startRow" not in body
