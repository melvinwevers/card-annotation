import re
import unicodedata
from typing import Any

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


def validate_field(value: str, schema: dict, field_name: str = None, section: str = None) -> tuple[bool, str]:
    """Validate a field value against its schema, focusing on priority fields"""
    from schemas import PRIORITY_FIELDS
    
    # Return early if no schema provided
    if not schema:
        return True, None
    
    # Skip validation if this field is not a priority field
    if field_name and section:
        priority_fields = PRIORITY_FIELDS.get(section, [])
        if field_name not in priority_fields:
            return True, None  # Skip validation for non-priority fields
    
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