from app.services.validation import validate_uk_licence_checksum


def test_valid_male_licence():
    # Surname SMITH -> SMITH prefix, month 05 (May)
    assert validate_uk_licence_checksum("SMITH705234JD9IJ", "SMITH") is True


def test_valid_female_licence():
    # Female month has +50 added: June = 06 + 50 = 56
    assert validate_uk_licence_checksum("JONES756234JD9IJ", "JONES") is True


def test_short_surname_padded_with_9s():
    # Surname LEE -> LEE99
    assert validate_uk_licence_checksum("LEE99705234JD9IJ", "LEE") is True


def test_mismatched_surname():
    assert validate_uk_licence_checksum("SMITH705234JD9IJ", "BROWN") is False


def test_invalid_month():
    # Month 13 is invalid (neither 1-12 nor 51-62)
    assert validate_uk_licence_checksum("SMITH713234JD9IJ", "SMITH") is False


def test_licence_too_short():
    assert validate_uk_licence_checksum("SMITH705", "SMITH") is False


def test_empty_inputs():
    assert validate_uk_licence_checksum("", "") is False
    assert validate_uk_licence_checksum("SMITH705234JD9IJ", "") is False
