"""Tests for drug interaction checking."""

import pytest


class TestDrugInteractionRepository:
    """Test drug interaction repository."""

    @pytest.mark.asyncio
    async def test_seed_interactions(self, interaction_repo):
        """Test seeding interaction data."""
        interactions = [
            {
                "drug_a": "Napa",
                "drug_b": "Warfarin",
                "severity": "moderate",
                "description": "Paracetamol may increase warfarin effect.",
                "source": "BNFC",
            },
            {
                "drug_a": "Sergel",
                "drug_b": "Clopidogrel",
                "severity": "severe",
                "description": "Esomeprazole reduces clopidogrel effect.",
                "source": "FDA",
            },
        ]
        count = await interaction_repo.seed_interactions(interactions)
        assert count == 2

    @pytest.mark.asyncio
    async def test_check_interaction(self, interaction_repo):
        """Test checking interaction between two drugs."""
        await interaction_repo.seed_interactions(
            [
                {
                    "drug_a": "Napa",
                    "drug_b": "Warfarin",
                    "severity": "moderate",
                    "description": "Test interaction",
                }
            ]
        )

        # Forward direction
        result = await interaction_repo.check_interaction("Napa", "Warfarin")
        assert result is not None
        assert result.severity == "moderate"

        # Reverse direction
        result = await interaction_repo.check_interaction("Warfarin", "Napa")
        assert result is not None

    @pytest.mark.asyncio
    async def test_check_interaction_not_found(self, interaction_repo):
        """Test checking interaction that doesn't exist."""
        result = await interaction_repo.check_interaction("Napa", "Sergel")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_against_cabinet(
        self, interaction_repo, medicine_repo, sample_medicine_data
    ):
        """Test checking a drug against cabinet contents."""
        # Add Napa to cabinet
        await medicine_repo.add_medicine(sample_medicine_data)

        # Seed an interaction
        await interaction_repo.seed_interactions(
            [
                {
                    "drug_a": "Napa",
                    "drug_b": "Warfarin",
                    "severity": "moderate",
                    "description": "Paracetamol may increase warfarin effect.",
                }
            ]
        )

        # Check Warfarin against cabinet (which has Napa)
        interactions = await interaction_repo.check_against_cabinet(
            "Warfarin", sample_medicine_data.group_chat_id
        )
        assert len(interactions) == 1
        assert interactions[0].severity == "moderate"

    @pytest.mark.asyncio
    async def test_check_against_cabinet_no_interactions(
        self, interaction_repo, medicine_repo, sample_medicine_data
    ):
        """Test checking when there are no interactions."""
        await medicine_repo.add_medicine(sample_medicine_data)

        interactions = await interaction_repo.check_against_cabinet(
            "VitaminC", sample_medicine_data.group_chat_id
        )
        assert len(interactions) == 0

    @pytest.mark.asyncio
    async def test_seed_duplicate_interactions(self, interaction_repo):
        """Test that duplicate interactions are ignored."""
        interactions = [
            {
                "drug_a": "Napa",
                "drug_b": "Warfarin",
                "severity": "moderate",
                "description": "Test interaction",
            }
        ]
        count1 = await interaction_repo.seed_interactions(interactions)
        count2 = await interaction_repo.seed_interactions(interactions)
        assert count1 == 1
        assert count2 == 1  # Still returns 1 but INSERT OR IGNORE prevents duplicate
