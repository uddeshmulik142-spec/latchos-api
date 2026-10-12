def validate_uk_licence_checksum(licence_no: str, last_name: str) -> bool:
    """Validates the mathematical structure of a UK Driving Licence Number.

    The first 5 characters should match the driver's surname (padded with '9').
    Characters 7-8 encode the birth month (1-12 for male, 51-62 for female).
    """
    if not licence_no or not last_name or len(licence_no) < 16:
        return False

    expected_prefix = last_name[:5].upper().ljust(5, "9")
    actual_prefix = licence_no[:5].upper()
    if expected_prefix != actual_prefix:
        return False

    month = licence_no[6:8]
    if not month.isdigit():
        return False

    month_val = int(month)
    return 1 <= month_val <= 12 or 51 <= month_val <= 62
