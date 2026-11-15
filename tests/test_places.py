"""Place names (analogatlas/places.py): formatting, and the export never calls the network."""
from analogatlas import places


def test_format_state_and_country():
    addr = {"state_district": "Departamento Antofagasta de la Sierra", "state": "Catamarca",
            "country": "Argentina"}
    assert places._format(addr) == "Catamarca, Argentina"
    assert places._format({"country": "Australia"}) == "Australia"
    assert places._format({}) is None


def test_name_reads_the_cache_only(monkeypatch):
    monkeypatch.setattr(places, "_cache", {"-26.50,-67.70": "Catamarca, Argentina"})
    monkeypatch.setattr(places, "_reverse", lambda *a: (_ for _ in ()).throw(AssertionError("network")))
    assert places.name(-26.5, -67.7) == "Catamarca, Argentina"
    assert places.name(10.0, 10.0) is None
