"""Tests for address normalization utilities."""

import pytest
from src.utils.address import (
    normalize_address,
    normalize_state,
    normalize_zip,
    normalize_phone,
    address_fingerprint,
    parse_address_line,
)


class TestNormalizeAddress:
    def test_basic_normalization(self):
        result = normalize_address("123 Main Street")
        assert "123" in result
        assert "main" in result
        assert "st" in result
        assert "street" not in result

    def test_abbreviates_avenue(self):
        result = normalize_address("500 Grand Avenue")
        assert "ave" in result
        assert "avenue" not in result

    def test_removes_unit(self):
        result = normalize_address("123 Oak St Apt 4B")
        assert "apt" not in result
        assert "4b" not in result

    def test_empty_string(self):
        assert normalize_address("") == ""

    def test_unicode_normalization(self):
        result = normalize_address("123 Café Boulevard")
        assert "cafe" in result or "blvd" in result


class TestNormalizeState:
    def test_already_abbreviated(self):
        assert normalize_state("CA") == "ca"
        assert normalize_state("ca") == "ca"

    def test_full_name(self):
        assert normalize_state("California") == "ca"
        assert normalize_state("california") == "ca"

    def test_unknown(self):
        assert normalize_state("XX") == "xx"


class TestNormalizeZip:
    def test_five_digit(self):
        assert normalize_zip("94601") == "94601"

    def test_nine_digit(self):
        assert normalize_zip("94601-1234") == "94601"

    def test_embedded_in_string(self):
        assert normalize_zip("Oakland CA 94601") == "94601"

    def test_empty(self):
        assert normalize_zip("") == ""


class TestNormalizePhone:
    def test_formatted_number(self):
        result = normalize_phone("(510) 555-1234")
        assert result == "5105551234"

    def test_with_country_code(self):
        result = normalize_phone("+1-510-555-1234")
        assert result == "5105551234"

    def test_already_clean(self):
        assert normalize_phone("5105551234") == "5105551234"


class TestAddressFingerprint:
    def test_same_address_same_fingerprint(self):
        fp1 = address_fingerprint("123 Main St", "Oakland", "CA", "94601")
        fp2 = address_fingerprint("123 Main Street", "Oakland", "California", "94601")
        assert fp1 == fp2

    def test_different_address_different_fingerprint(self):
        fp1 = address_fingerprint("123 Main St", "Oakland", "CA", "94601")
        fp2 = address_fingerprint("456 Oak Ave", "Oakland", "CA", "94601")
        assert fp1 != fp2


class TestParseAddressLine:
    def test_full_address(self):
        result = parse_address_line("123 Main St, Oakland, CA 94601")
        assert result["zip"] == "94601"
        assert result["state"] == "ca"
        assert "oakland" in result["city"]
        assert "main" in result["street"]

    def test_empty_string(self):
        result = parse_address_line("")
        assert result == {"street": "", "city": "", "state": "", "zip": ""}
