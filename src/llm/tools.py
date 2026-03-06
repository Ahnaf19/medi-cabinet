"""Tool schemas for structured LLM extraction."""

MEDICINE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_medicine_command",
        "description": (
            "Extract a medicine command from natural language text. "
            "Identify the command type (add, use, search, list) and medicine details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command_type": {
                    "type": "string",
                    "enum": ["add", "use", "search", "list"],
                    "description": "The type of command the user intends",
                },
                "medicine_name": {
                    "type": "string",
                    "description": "Name of the medicine (use common BD brand names when possible)",
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of units (tablets, capsules, etc.)",
                },
                "unit": {
                    "type": "string",
                    "enum": ["tablets", "capsules", "ml", "mg", "strips", "bottles", "pieces"],
                    "description": "Unit of measurement",
                },
                "expiry_date": {
                    "type": "string",
                    "description": "Expiry date in ISO format (YYYY-MM-DD) if mentioned",
                },
                "location": {
                    "type": "string",
                    "description": "Storage location if mentioned",
                },
            },
            "required": ["command_type"],
        },
    },
}

IMAGE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_medicine_from_image",
        "description": (
            "Extract medicine information from a photo of a medicine packet or prescription."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "medicines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Medicine brand name",
                            },
                            "generic_name": {
                                "type": "string",
                                "description": "Generic/chemical name if visible",
                            },
                            "dosage": {
                                "type": "string",
                                "description": "Dosage strength (e.g., 500mg)",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Number of units visible",
                            },
                            "unit": {
                                "type": "string",
                                "enum": [
                                    "tablets",
                                    "capsules",
                                    "ml",
                                    "strips",
                                    "bottles",
                                    "pieces",
                                ],
                            },
                            "expiry_date": {
                                "type": "string",
                                "description": "Expiry date in ISO format if visible",
                            },
                            "manufacturer": {
                                "type": "string",
                                "description": "Manufacturer name if visible",
                            },
                        },
                        "required": ["name"],
                    },
                    "description": "List of medicines identified in the image",
                },
            },
            "required": ["medicines"],
        },
    },
}

ROUTINE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_routine",
        "description": "Extract medicine routine/schedule information from natural language.",
        "parameters": {
            "type": "object",
            "properties": {
                "medicine_name": {
                    "type": "string",
                    "description": "Name of the medicine",
                },
                "dosage_quantity": {
                    "type": "integer",
                    "description": "Number of units per dose",
                },
                "dosage_unit": {
                    "type": "string",
                    "enum": ["tablets", "capsules", "ml", "mg", "strips"],
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "every_other_day", "custom"],
                    "description": "How often to take the medicine",
                },
                "times_of_day": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Times in HH:MM format (24h), e.g. ['08:00', '20:00']",
                },
                "days_of_week": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Days for weekly routines, e.g. ['monday', 'wednesday']",
                },
                "meal_relation": {
                    "type": "string",
                    "enum": ["before_meal", "after_meal", "with_meal"],
                    "description": "When to take relative to meals",
                },
            },
            "required": ["medicine_name", "frequency", "times_of_day"],
        },
    },
}
