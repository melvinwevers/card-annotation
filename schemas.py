import unicodedata
import re
from enum import Enum

class FieldType(Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    ENUM = "enum"
    
FIELD_SCHEMAS = {
    "header": {
        "street": {
            "type": FieldType.STRING.value,
            "description": "Street name",
            "autocomplete": [
                "Elisabeth Wolffstraat", "Saenredamstraat", "Spanderswoudstraat", 
                "Haarlemmerdijk", "Vossiusstraat", "Stierstraat", "Burgemeester Fockstraat"
            ],
            "min_length": 5,
            "max_length": 100
        },
        "house_number": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d+[A-Za-z]?(\s+\d+)?(\s+(I{1,3}|IV|V))?(\s+(hs|huis|bg|boven|beneden|voor|achter))?(\s+(hoog|laag))?$",
            "description": "House number with optional floor/position",
            "placeholder": "60 III hoog"
        },
        "codenummer": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{4}$",
            "description": "4-digit code number",
            "placeholder": "0465"
        },
        "buurtletter": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|[A-Z]{2}\s*[A-Z]*\s*\d*)$",
            "description": "Neighborhood code",
            "placeholder": "SO I"
        },
        "stemdistrict_nr": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{2}\s*-\s*\d{3})$",
            "description": "Voting district number",
            "placeholder": "02-485"
        }
    },
    "main_entries": {
        "record_no": {
            "type": FieldType.INT.value,
            "min": 1,
            "max": 999,
            "description": "Record number"
        },
        "datum_registration": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Registration date (DDMMYY)",
            "placeholder": "160636"
        },
        "gezinshoofd": {
            "type": FieldType.STRING.value,
            "pattern": r"^[a-zA-ZÀ-ÿ\s\-',\.]+,\s*[a-zA-ZÀ-ÿ\s\-'\.]+$",
            "description": "Head of household (Last name, First name)",
            "placeholder": "Keijzer, Tonko",
            "min_length": 3,
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{2}$",
            "description": "Year of birth (YY)",
            "placeholder": "94"
        },
        "M": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Number of males or slash, or empty",
            "placeholder": "1"
        },
        "V": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Number of females or slash, or empty",
            "placeholder": "1"
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Departure date (DDMMYY)",
            "placeholder": "090659"
        },
        "waarheen": {
            "type": FieldType.STRING.value,
            "description": "Destination address",
            "min_length": 0,
            "max_length": 200
        },
        "remarks": {
            "type": FieldType.STRING.value,
            "description": "Additional remarks",
            "max_length": 200
        }
    },
    "follow_up_entries": {
        "volg_nr": {
            "type": FieldType.INT.value,
            "min": 1,
            "max": 999,
            "description": "Follow-up number"
        },
        "datum": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Date (DDMMYY)",
            "placeholder": "211070"
        },
        "inwonenden": {
            "type": FieldType.STRING.value,
            "pattern": r"^[a-zA-ZÀ-ÿ\s\-',\.]+,\s*[a-zA-ZÀ-ÿ\s\-'\.]+$",
            "description": "Resident name (Last name, First name Middle)",
            "placeholder": "Aantjes, Robert M",
            "min_length": 3,
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{2}$",
            "description": "Year of birth (YY)",
            "placeholder": "47"
        },
        "M": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Number of males or slash, or empty",
            "placeholder": "1"
        },
        "V": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Number of females or slash, or empty",
            "placeholder": "1"
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Departure date (DDMMYY)",
            "placeholder": "260371"
        },
        "waarheen": {
            "type": FieldType.STRING.value,
            "description": "Destination or reference",
            "max_length": 200
        },
        "remarks": {
            "type": FieldType.STRING.value,
            "description": "Additional remarks",
            "max_length": 200
        }
    },
    "footer_notes": {
        "type": FieldType.STRING.value,
        "description": "Footer notes or additional information",
        "max_length": 500
    }
}