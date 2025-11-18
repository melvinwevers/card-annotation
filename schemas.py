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
            "description": "Huisnummer",
            "min_length": 1,
            "max_length": 100
        },
        "codenummer": {
            "type": FieldType.STRING.value,
            "pattern": r"^\d{4}$",
            "description": "Codenummer (4 cijfers)"
        },
        "buurtletter": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|[A-Z]{2}\s*[A-Z]*\s*\d*)$",
            "description": "Buurtletter (Twee karakters + cijfers)"
        },
        "stemdistrict_nr": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{2}\s*-\s*\d{3})$",
            "description": "Stemdistrict Nr."
        }
    },
    "main_entries": {
        "record_no": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{1,3})$",
            "description": "Record nummer (Optional, 1-999)"
        },
        "datum_registration": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Registratie Datum (DDMMYY)"
        },
        "gezinshoofd": {
            "type": FieldType.STRING.value,
            "pattern": r"^([a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-',\.\(\)]+)?$",
            "description": "Gezinshoofd (e.g., 'Scholten, Johannes' or 'sportzaal')",
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{2})$",
            "description": "Jaar (Geboortejaar) (YY) - Optional"
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Verhuisdatum (Datum) (DDMMYY)",
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
        },
        "datum": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Datum (Inschrijfdatum) (DDMMYY)",
        },
        "inwonenden": {
            "type": FieldType.STRING.value,
            "pattern": r"^([a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\u0300-\u036F\u1E00-\u1EFF\u2C60-\u2C7F\uA720-\uA7FF\s\-',\.\(\)]+)?$",
            "description": "Inwonenden (e.g., 'Scholten, Johannes' or other)",
            "max_length": 100
        },
        "year_of_birth": {
            "type": FieldType.STRING.value,
            "pattern": r"^(|\d{2})$",
            "description": "Jaar (Geboortejaar) (YY) - Optional",
        },
        "datum_vertrek": {
            "type": FieldType.STRING.value,
            "pattern": r"^(\d{6})?$",
            "description": "Verhuisdatum (DDMMYY)",
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
    }
}
