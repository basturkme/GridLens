"""Smoke tests — verify the package and skeleton modules import cleanly."""


def test_package_imports() -> None:
    import gridlens  # noqa: F401
    from gridlens import core, utils  # noqa: F401
    from gridlens.core import models  # noqa: F401


def test_models_construct() -> None:
    from gridlens.core.models import Bus, Network

    n = Network(name="t", base_mva=10.0, buses=[Bus(id="B1", is_slack=True)])
    assert n.buses[0].id == "B1"
    assert n.buses[0].is_slack is True


def test_validator() -> None:
    from gridlens.utils.validators import parse_float

    assert parse_float("12.5").ok is True
    assert parse_float("abc").ok is False
    assert parse_float("", allow_empty=True).ok is True
    assert parse_float("-1", minimum=0).ok is False
