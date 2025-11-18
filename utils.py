import re
import unicodedata
from typing import Any, Dict, List, Union

def clean_none_values(data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Recursively replace "none" string values and None with empty strings.
    This handles cases where the model has entered "none" or None instead of leaving fields empty.

    Note: We do NOT remove leading zeros from numeric strings as they may be significant
    (e.g., dates like "080883" or codes like "0001").
    """
    # Handle None values - convert to empty string
    if data is None:
        return ""

    if isinstance(data, dict):
        return {
            key: clean_none_values(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [clean_none_values(item) for item in data]
    elif isinstance(data, str):
        # Replace "none" (case-insensitive) with empty string
        if data.lower() == "none":
            return ""
        # Keep the string as-is, including any leading zeros
        return data
    else:
        return data


def clean_json_text(raw: str) -> str:
    cleaned = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    cleaned = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', cleaned)
    return cleaned


def type_convert(val: str, original: Any) -> Any:
    """Convert string input to the appropriate type based on original value"""
    if val is None:
        return None if original is None else original
    
    # Normalize whitespace
    val_stripped = val.strip() if isinstance(val, str) else str(val).strip()
    
    if isinstance(original, bool):
        return val_stripped.lower() in ('true', '1', 'yes', 'on')
    
    if isinstance(original, int):
        if not val_stripped:  # Handle empty strings for integer fields
            return 0 if original == 0 else None
        try:
            return int(float(val_stripped))  # Handle "5.0" -> 5
        except (ValueError, TypeError):
            return original  # Return original value if conversion fails
    
    if isinstance(original, float):
        if not val_stripped:  # Handle empty strings for float fields
            return 0.0 if original == 0.0 else None
        try:
            return float(val_stripped)
        except (ValueError, TypeError):
            return original  # Return original value if conversion fails
    
    if original is None:
        # Handle various null representations
        low = val_stripped.lower()
        if low in ('', 'null', 'none', 'nil', 'undefined'):
            return ''
        return val_stripped
    
    # For strings and other types, return the stripped value
    return val_stripped


def parse_date_ddmmyy(date_str: str) -> tuple[bool, int]:
    """
    Parse a date in DDMMYY format and return (is_valid, comparable_value).
    Returns a comparable integer value for date comparison.
    Format: DDMMYY (e.g., "010175" = January 1, 1975)
    """
    if not date_str or not isinstance(date_str, str):
        return False, 0

    date_str = date_str.strip()
    if len(date_str) != 6 or not date_str.isdigit():
        return False, 0

    try:
        day = int(date_str[0:2])
        month = int(date_str[2:4])
        year = int(date_str[4:6])

        # Basic validation
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return False, 0

        # Assume dates < 30 are 2000s, >= 30 are 1900s
        full_year = 1900 + year if year >= 30 else 2000 + year

        # Create comparable value: YYYYMMDD
        comparable = full_year * 10000 + month * 100 + day
        return True, comparable
    except (ValueError, IndexError):
        return False, 0


def validate_field(
    value: str, schema: dict, field_name: str = None, section: str = None
) -> tuple[bool, str]:
    """Validate a field value against its schema"""
    # Return early if no schema provided
    if not schema:
        return True, None

    # Normalize value
    value = value.strip() if isinstance(value, str) else str(value).strip()

    # Check required fields
    if not value and schema.get('required', False):
        field_desc = schema.get('description', field_name or 'This field')
        return False, f'{field_desc} is required'

    # Allow empty values for non-required fields
    if not value and not schema.get('required', False):
        return True, None

    field_type = schema.get('type', 'string')
    field_desc = schema.get('description', field_name or 'Field')

    # String validation
    if field_type == 'string':
        # Pattern validation
        if 'pattern' in schema:
            try:
                normalized_value = unicodedata.normalize('NFC', value)
                if not re.fullmatch(schema['pattern'], normalized_value):
                    example = schema.get('placeholder', 'see format guidelines')
                    return False, f"{field_desc}: Invalid format. Example: {example}"
            except re.error:
                return False, f"{field_desc}: Invalid validation pattern"

        # Length validation
        if 'min_length' in schema and len(value) < schema['min_length']:
            return False, f"{field_desc}: Minimum {schema['min_length']} characters required"
        if 'max_length' in schema and len(value) > schema['max_length']:
            return False, f"{field_desc}: Maximum {schema['max_length']} characters allowed"

    # Float validation
    elif field_type == 'float':
        try:
            num = float(value)
            if 'min' in schema and num < schema['min']:
                return False, f"{field_desc}: Minimum value is {schema['min']}"
            if 'max' in schema and num > schema['max']:
                return False, f"{field_desc}: Maximum value is {schema['max']}"
        except (ValueError, TypeError):
            return False, f'{field_desc}: Must be a valid decimal number'

    # Integer validation
    elif field_type == 'int':
        try:
            num = int(float(value))  # Allow "5.0" format
            if 'min' in schema and num < schema['min']:
                return False, f"{field_desc}: Minimum value is {schema['min']}"
            if 'max' in schema and num > schema['max']:
                return False, f"{field_desc}: Maximum value is {schema['max']}"
        except (ValueError, TypeError):
            return False, f'{field_desc}: Must be a valid whole number'

    # Enum validation
    elif field_type == 'enum':
        options = schema.get('options', [])
        if value not in options:
            options_str = ', '.join(options[:3])  # Show first 3 options
            return False, f'{field_desc}: Must be one of: {options_str}...'

    return True, None


def validate_entry_dates(entry: Dict, section: str) -> tuple[bool, str]:
    """
    Validate that departure date is later than registration date in an entry.

    Args:
        entry: Dictionary containing the entry data
        section: Section name ("main_entries" or "follow_up_entries")

    Returns:
        (is_valid, error_message)
    """
    # Determine which date fields to check based on section
    if section == "main_entries":
        reg_field = "datum_registration"
        dep_field = "datum_vertrek"
    elif section == "follow_up_entries":
        reg_field = "datum"
        dep_field = "datum_vertrek"
    else:
        return True, None

    reg_date = entry.get(reg_field, "").strip()
    dep_date = entry.get(dep_field, "").strip()

    # If either date is empty, skip validation
    if not reg_date or not dep_date:
        return True, None

    # Parse both dates
    reg_valid, reg_value = parse_date_ddmmyy(reg_date)
    dep_valid, dep_value = parse_date_ddmmyy(dep_date)

    # If either date is invalid format, the field validation will catch it
    if not reg_valid or not dep_valid:
        return True, None

    # Check if departure is later than registration
    if dep_value <= reg_value:
        return False, f"Departure date ({dep_date}) must be later than registration date ({reg_date})"

    return True, None