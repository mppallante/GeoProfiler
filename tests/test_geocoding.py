"""Tests for src/geocoding.py."""

from __future__ import annotations

import requests

from src.geo_analysis import Coordinate
from src.geocoding import geocode_address


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_geocode_address_returns_none_for_empty_input():
    assert geocode_address("   ") is None


def test_geocode_address_parses_first_result(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _FakeResponse([{"lat": "-23.550520", "lon": "-46.633308"}])

    monkeypatch.setattr("src.geocoding.requests.get", fake_get)

    result = geocode_address("Praça da Sé, São Paulo")
    assert result == Coordinate(latitude=-23.550520, longitude=-46.633308)


def test_geocode_address_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr("src.geocoding.requests.get", lambda *a, **k: _FakeResponse([]))
    assert geocode_address("endereço inexistente") is None


def test_geocode_address_returns_none_on_network_error(monkeypatch):
    def raise_error(*args, **kwargs):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr("src.geocoding.requests.get", raise_error)
    assert geocode_address("qualquer endereço") is None
