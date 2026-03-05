"""Drug interaction checking service."""

import json
from pathlib import Path
from typing import List

from loguru import logger

from src.database import Database, DrugInteractionRepository, DrugInteraction


class InteractionService:
    """Checks for drug interactions when adding medicines."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def check_against_cabinet(
        self, drug_name: str, group_chat_id: int
    ) -> List[DrugInteraction]:
        """Check a drug against all medicines currently in the cabinet."""
        async with Database(self.db_path) as db:
            repo = DrugInteractionRepository(db)
            return await repo.check_against_cabinet(drug_name, group_chat_id)

    async def check_pair(self, drug_a: str, drug_b: str) -> List[DrugInteraction]:
        """Check if two specific drugs interact."""
        async with Database(self.db_path) as db:
            repo = DrugInteractionRepository(db)
            result = await repo.check_interaction(drug_a, drug_b)
            return [result] if result else []

    async def seed_from_file(self, filepath: str = "data/drug_interactions.json") -> int:
        """Seed interactions from JSON file."""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Drug interactions file not found: {filepath}")
            return 0

        with open(path) as f:
            interactions = json.load(f)

        async with Database(self.db_path) as db:
            repo = DrugInteractionRepository(db)
            count = await repo.seed_interactions(interactions)

        logger.info(f"Seeded {count} drug interactions from {filepath}")
        return count

    @staticmethod
    def format_warnings(interactions: List[DrugInteraction]) -> str:
        """Format interaction warnings for display."""
        if not interactions:
            return ""

        severity_emoji = {
            "mild": "",
            "moderate": "",
            "severe": "",
            "contraindicated": "",
        }

        lines = ["*Drug Interaction Warning!*\n"]
        for interaction in interactions:
            emoji = severity_emoji.get(interaction.severity, "")
            lines.append(
                f"{emoji} *{interaction.drug_a_name}* + *{interaction.drug_b_name}* "
                f"({interaction.severity.upper()})"
            )
            lines.append(f"   {interaction.description}")

        return "\n".join(lines)
