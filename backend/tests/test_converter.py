import pytest
from decimal import Decimal
from app.services.route.converter import to_paise

def test_paise_conversion_whole_rupees():
    assert to_paise(Decimal("100.00")) == 10000

def test_paise_conversion_paise():
    assert to_paise(Decimal("90.50")) == 9050
    assert to_paise(Decimal("0.99")) == 99

def test_paise_conversion_zero():
    assert to_paise(Decimal("0.00")) == 0

def test_paise_conversion_large():
    assert to_paise(Decimal("99999999.99")) == 9999999999

def test_paise_conversion_negative():
    with pytest.raises(ValueError, match="cannot be negative"):
        to_paise(Decimal("-10.00"))

def test_paise_conversion_fractional_paise():
    with pytest.raises(ValueError, match="sub-paise precision"):
        to_paise(Decimal("10.123"))
