from datetime import datetime, timezone

import pytest

from src.ingestion.orderbook_parser import OrderbookParser


@pytest.fixture()
def parser() -> OrderbookParser:
    return OrderbookParser()


def test_parse_valid_binance_diff_depth_message(parser: OrderbookParser):
    raw = {
        "e": "depthUpdate",
        "E": 1672515782136,
        "s": "BNBBTC",
        "U": 157,
        "u": 160,
        "b": [["0.0024", "10"], ["0.0025", "5"]],
        "a": [["0.0027", "50"], ["0.0026", "100"]],
    }

    snapshot = parser.parse("BNBBTC", raw)
    assert snapshot is not None

    assert snapshot.symbol == "BNBBTC"
    assert snapshot.update_id == 160
    assert snapshot.timestamp == datetime.fromtimestamp(1672515782136 / 1000, tz=timezone.utc)

    assert snapshot.bids == [(0.0025, 5.0), (0.0024, 10.0)]
    assert snapshot.asks == [(0.0026, 100.0), (0.0027, 50.0)]


def test_parse_valid_binance_partial_depth_message(parser: OrderbookParser):
    raw = {
        "lastUpdatedId": 12345,
        "bids": [["100.0", "2.0"], ["99.0", "1.0"]],
        "asks": [["101.0", "1.5"], ["102.0", "3.0"]],
    }

    snapshot = parser.parse("btcusdt", raw)
    assert snapshot is not None
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.update_id == 12345
    assert snapshot.bids == [(100.0, 2.0), (99.0, 1.0)]
    assert snapshot.asks == [(101.0, 1.5), (102.0, 3.0)]


def test_bids_sorted_descending(parser: OrderbookParser):
    raw = {
        "E": 1700000000000,
        "b": [["100.0", "1.0"], ["101.0", "1.0"], ["99.5", "1.0"]],
        "a": [["102.0", "1.0"]],
    }

    snapshot = parser.parse("BTCUSDT", raw)
    assert snapshot is not None
    assert [p for p, _ in snapshot.bids] == [101.0, 100.0, 99.5]


def test_asks_sorted_ascending(parser: OrderbookParser):
    raw = {
        "E": 1700000000000,
        "b": [["100.0", "1.0"]],
        "a": [["102.0", "1.0"], ["101.0", "1.0"], ["103.0", "1.0"]],
    }

    snapshot = parser.parse("BTCUSDT", raw)
    assert snapshot is not None
    assert [p for p, _ in snapshot.asks] == [101.0, 102.0, 103.0]


def test_invalid_levels_filtered_out(parser: OrderbookParser):
    raw = {
        "E": 1700000000000,
        "b": [
            ["2.0", "3.0"],  # valid
            ["1.5", "4.0"],  # valid
            ["0", "1"],  # invalid (price <= 0)
            ["-1", "1"],  # invalid (price <= 0)
            ["1", "0"],  # invalid (volume <= 0)
            ["1", "-2"],  # invalid (volume <= 0)
            ["abc", "1"],  # invalid (not float)
            [None, "1"],  # invalid (not float)
            ["2"],  # invalid (missing volume)
            [],  # invalid
            None,  # invalid
        ],
        "a": [
            ["3.0", "1.0"],  # valid
            ["3.5", "2.0"],  # valid
            ["0", "1"],  # invalid (price <= 0)
            ["4.0", "0"],  # invalid (volume <= 0)
            ["nope", "1.0"],  # invalid (not float)
        ],
    }

    snapshot = parser.parse("BTCUSDT", raw)
    assert snapshot is not None

    assert snapshot.bids == [(2.0, 3.0), (1.5, 4.0)]
    assert snapshot.asks == [(3.0, 1.0), (3.5, 2.0)]


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "not a dict",
        123,
        [],
        {"b": [["1.0", "1.0"]]},  # missing asks
        {"a": [["1.0", "1.0"]]},  # missing bids
        {"b": [], "a": []},  # empty sides
        {"b": [["1.0", "0.0"]], "a": [["2.0", "0.0"]]},  # filtered to empty
        {"b": [["bad", "1.0"]], "a": [["2.0", "1.0"]]},  # bids empty after parse
        {"b": [["1.0", "1.0"]], "a": [["bad", "1.0"]]},  # asks empty after parse
    ],
)
def test_returns_none_on_bad_input(parser: OrderbookParser, raw):
    assert parser.parse("BTCUSDT", raw) is None

