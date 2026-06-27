"""Mapeo de títulos Conectate/LD → claves internas (La Suerte, King Lottery)."""
import pytest


@pytest.mark.parametrize(
    "title,expected",
    [
        ("La Suerte Día", "La Suerte MD"),
        ("La Suerte Dia", "La Suerte MD"),
        ("La Suerte Tarde", "La Suerte 6PM"),
        ("La Suerte 12:30", "La Suerte MD"),
        ("La Suerte 18:00", "La Suerte 6PM"),
        ("La Suerte MD", "La Suerte MD"),
        ("La Suerte 6PM", "La Suerte 6PM"),
        ("King Lottery Día", "King Lottery 12:30"),
        ("King Lottery Dia", "King Lottery 12:30"),
        ("King Lottery Noche", "King Lottery 7:30"),
        ("King Lottery 12:30", "King Lottery 12:30"),
        ("King Lottery 7:30", "King Lottery 7:30"),
        ("Quiniela Real", "Quiniela Real"),
        ("Florida Día", "Florida Día"),
    ],
)
def test_conectate_label_to_internal_key(app_mod, title, expected):
    assert app_mod._conectate_label_to_internal_key(title) == expected


@pytest.mark.parametrize(
    "title,loteria,sorteo",
    [
        ("La Suerte Día", "La Suerte Dominicana", "12:30 PM"),
        ("La Suerte Tarde", "La Suerte Dominicana", "6:00 PM"),
        ("King Lottery Día", "King Lottery", "12:30 PM"),
        ("King Lottery Noche", "King Lottery", "7:30 PM"),
    ],
)
def test_conectate_mapeo_diagnostico_bd(app_mod, title, loteria, sorteo):
    d = app_mod._conectate_title_mapeo_diagnostico(title)
    assert d["mapeado"] is True
    assert d["loteria_bd"] == loteria
    assert d["sorteo_bd"] == sorteo
    assert d["motivo_ignorado"] is None


def test_conectate_titulo_desconocido_sin_mapeo(app_mod):
    d = app_mod._conectate_title_mapeo_diagnostico("Lotería Inventada XYZ")
    assert d["mapeado"] is False
    assert d["motivo_ignorado"] == "titulo_sin_mapeo_clave_interna"
