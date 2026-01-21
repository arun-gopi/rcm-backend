"""
CSV import utility functions for data parsing and validation.
"""
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_bool(value: str | None) -> bool:
    """
    Determine whether a CSV string represents a true value.
    
    Recognizes 'true', 'yes', '1', 't', and 'y' (case-insensitive, surrounding whitespace ignored) as true; treats None or any other value as false.
    
    Returns:
        True if the input represents a true value, False otherwise.
    """
    if not value:
        return False
    return value.strip().lower() in ('true', 'yes', '1', 't', 'y')


def parse_decimal(value: str | None) -> Decimal | None:
    """
    Convert a string to a Decimal, returning None for empty or invalid inputs.
    
    Parameters:
        value (str | None): String containing a numeric value, or None. Blank or whitespace-only strings are treated as missing.
    
    Returns:
        Decimal | None: The parsed Decimal if parsing succeeds; `None` if `value` is `None`, blank, or not a valid decimal.
    """
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: str | None) -> int | None:
    """
    Parse a string into an int, returning None for missing, blank, or non-integer input.
    
    Parameters:
        value (str | None): The input string to parse; may be None or blank.
    
    Returns:
        int | None: The parsed integer, or None if the input is None, empty, or not a valid integer.
    """
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def safe_get(row: dict, key: str, default: Any = None) -> Any:
    """
    Safely get a value from CSV row, returning default if missing or empty.
    """
    value = row.get(key, default)
    if isinstance(value, str) and not value.strip():
        return default
    return value


def validate_required_fields(row: dict, required_fields: list[str], row_number: int) -> list[str]:
    """
    Check that each required field in a CSV row exists and contains a non-empty value.
    
    Parameters:
        row (dict): Mapping of column names to values for a single CSV row.
        required_fields (list[str]): Field names that must be present and non-blank in `row`.
        row_number (int): 1-based row number used to prefix error messages.
    
    Returns:
        list[str]: Error messages of the form "Row {row_number}: Missing required field '{field}'" for each required field that is missing or blank.
    """
    errors = []
    for field in required_fields:
        value = row.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Row {row_number}: Missing required field '{field}'")
    return errors