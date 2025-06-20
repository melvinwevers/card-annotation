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
            "description": "Straat",
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
            "description": "Huisnummer",
            "placeholder": "60 III hoog"
        },
        "codenummer": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{4}$",
            "description": "Codenummer (4 cijfers)",
            "placeholder": "0465"
        },
        "buurtletter": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|[A-Z]{2}\s*[A-Z]*\s*\d*)$",
            "description": "Buurtletter (Twee karakters + cijfers)",
            "placeholder": "SO I"
        },
        "stemdistrict_nr": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{2}\s*-\s*\d{3})$",
            "description": "Stemdistrict Nr.",
            "placeholder": "02-485"
        }
    },
    "main_entries": {
        "record_no": {
            "type": FieldType.INT.value,
            "min": 1,
            "max": 999,
            "description": "Record nummer"
        },
        "datum_registration": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Registratie Datum (DDMMYY)",
            "placeholder": "160636"
        },
        "gezinshoofd": {
            "type": FieldType.STRING.value,
            "pattern": r"^[a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-',\.]+,\s*[a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-'\.]+$",
            "description": "Gezinshoofd (Last name, First name)",
            "placeholder": "Keijzer, Tonko",
            "min_length": 3,
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{2}$",
            "description": "Jaar (Geboortejaar) (YY)",
            "placeholder": "94"
        },
        "M": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Aantal mannen (M) (Cijfers, Slash, Dash of leeg)",
            "placeholder": "1"
        },
        "V": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Aantal vrouwen (V) (Cijfers, Slash, Dash of leeg)",
            "placeholder": "1"
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Verhuisdatum (Datum) (DDMMYY)",
            "placeholder": "090659"
        },
        "waarheen": {
            "type": FieldType.STRING.value,
            "description": "Waarheen",
            "min_length": 0,
            "max_length": 200
        },
        "remarks": {
            "type": FieldType.STRING.value,
            "description": "Opmerkingen",
            "max_length": 200
        }
    },
    "follow_up_entries": {
        "volg_nr": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{1,3})$",
            "description": "Volgnr. (Optional, 1-999)",
            "placeholder": "1"
        },
        "datum": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Datum (Inschrijfdatum) (DDMMYY)",
            "placeholder": "211070"
        },
        "inwonenden": {
            "type": FieldType.STRING.value,
            "pattern": r"^[a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-',\.]+,\s*[a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-'\.]+$",
            "description": "Inwonenden (Last name, First name Middle)",
            "placeholder": "Aantjes, Robert M",
            "min_length": 3,
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{2}$",
            "description": "Jaar (Geboortejaar) (YY)",
            "placeholder": "47"
        },
        "M": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Aantal mannen (M) (Cijfers, Slash, Dash of leeg",
            "placeholder": "1"
        },
        "V": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d+|/|-)$",
            "description": "Aantal vrouwen (V) (Cijfers, Slash, Dash of leeg",
            "placeholder": "1"
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Verhuisdatum (DDMMYY)",
            "placeholder": "260371"
        },
        "waarheen": {
            "type": FieldType.STRING.value,
            "description": "Waarheen",
            "max_length": 200
        },
        "remarks": {
            "type": FieldType.STRING.value,
            "description": "Opmerkingen",
            "max_length": 200
        }
    },
    "footer_notes": {
        "type": FieldType.STRING.value,
        "description": "Aantekeningen",
        "max_length": 500
    }
}