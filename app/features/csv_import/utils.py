"""
CSV import utility functions for data parsing and validation.
"""
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_bool(value: str | None) -> bool:
    """
    Parse various boolean representations from CSV.
    
    Accepts: 'true', 'yes', '1', 't', 'y' (case-insensitive) as True
    Everything else is False
    """
    if not value:
        return False
    return value.strip().lower() in ('true', 'yes', '1', 't', 'y')


def parse_decimal(value: str | None) -> Decimal | None:
    """
    Parse decimal value from CSV, handling empty strings and invalid formats.
    """
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: str | None) -> int | None:
    """
    Parse integer value from CSV, handling empty strings and invalid formats.
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
    Validate that all required fields are present and non-empty.
    
    Returns:
        List of error messages for missing fields
    """
    errors = []
    for field in required_fields:
        value = row.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Row {row_number}: Missing required field '{field}'")
    return errors
