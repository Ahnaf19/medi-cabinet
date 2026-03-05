# Data

Static seed data for the application.

## Files

- **`drug_interactions.json`** — 30 common drug interaction pairs relevant to Bangladeshi medicine brands. Used by `InteractionService.seed_from_file()` and `scripts/seed_data.py`.

## Format

Each interaction entry:
```json
{
  "drug_a": "Napa",
  "drug_b": "Warfarin",
  "severity": "moderate",
  "description": "Paracetamol may enhance the anticoagulant effect of warfarin.",
  "source": "BNFC"
}
```

Severity levels: `mild`, `moderate`, `severe`, `contraindicated`.
