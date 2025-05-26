import re
import unicodedata
from typing import Any

def clean_json_text(raw: str) -> str:
    cleaned = re.sub(r'(:\s*)-(\s*[,\}])', r'\1null\2', raw)
    cleaned = re.sub(r'(:\s*)(0\d+)(\s*[,\}])', r'\1"\2"\3', cleaned)
    return cleaned


def type_convert(val: str, original: Any) -> Any:
    if isinstance(original, bool):
        return val.lower() in ('true', '1', 'yes')
    if isinstance(original, int):
        try:
            return int(val)
        except ValueError:
            return None
    if isinstance(original, float):
        try:
            return float(val)
        except ValueError:
            return val
    if original is None:
        low = val.strip().lower()
        if low in ('', 'null', 'none'):
            return ''
        return val


def validate_field(value: str, schema: dict) -> tuple[bool, str]:
    if not value and schema.get('required', False):
        return False, 'This field is required'
    t = schema.get('type', 'string')
    if t == 'string':
        if 'pattern' in schema:
            if not re.fullmatch(schema['pattern'], unicodedata.normalize('NFC', value)):
                return False, f"Invalid format. Expected: {schema.get('description')}"
        if 'min_length' in schema and len(value) < schema['min_length']:
            return False, f"Minimum length is {schema['min_length']} characters"
        if 'max_length' in schema and len(value) > schema['max_length']:
            return False, f"Maximum length is {schema['max_length']} characters"
    elif t == 'float':
        try:
            num = float(value)
            if 'min' in schema and num < schema['min']:
                return False, f"Minimum value is {schema['min']}"
            if 'max' in schema and num > schema['max']:
                return False, f"Maximum value is {schema['max']}"
        except ValueError:
            return False, 'Must be a valid number'
    elif t == 'int':
        try:
            num = int(value)
            if 'min' in schema and num < schema['min']:
                return False, f"Minimum value is {schema['min']}"
            if 'max' in schema and num > schema['max']:   
                return False, f"Maximum value is {schema['max']}"
        except ValueError:
            return False, 'Must be a valid integer'
    elif t == 'enum':
        if value not in schema.get('options', []):
            return False, 'Please select a valid option'
    return True, None