import re


def validate_uk_licence_checksum(licence_no: str, last_name: str) -> bool:
    """Validates the mathematical structure of a UK Driving Licence Number.

    The first 5 characters match the driver's surname (padded with '9').
    Characters 7-8 encode the birth month (1-12 for male, 51-62 for female).

    Robust against spaces, issue numbers, or trailing suffix digits
    commonly returned by OCR (e.g. 'MORGA753116SM9IJ 35' or 'SMITH 705234 JD9IJ').
    """
    if not licence_no or not last_name:
        return False

    # Strip any non-alphanumeric characters (spaces, hyphens)
    clean_licence = re.sub(r"[^A-Z0-9]", "", licence_no.upper())
    clean_surname = re.sub(r"[^A-Z]", "", last_name.upper())

    if len(clean_licence) < 16 or not clean_surname:
        return False

    # Surnames shorter than 5 chars are padded with '9'
    expected_prefix = clean_surname[:5].ljust(5, "9")
    actual_prefix = clean_licence[:5]

    if expected_prefix != actual_prefix:
        return False

    # Month is encoded at positions 7-8 (index 5-7, 0-indexed: index 5 is decade, index 6-7 is month)
    # Standard format: NNNNN YYMMDD SSSSS
    # index 0..4: Surname (5 chars)
    # index 5: Decade digit
    # index 6..7: Month (01-12 male, 51-62 female)
    month = clean_licence[6:8]
    if not month.isdigit():
        return False

    month_val = int(month)
    return 1 <= month_val <= 12 or 51 <= month_val <= 62
