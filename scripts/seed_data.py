"""Seed database with sample medicine data for demo purposes."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    Database,
    MedicineRepository,
    MedicineData,
    RoutineRepository,
    RoutineData,
    CostRepository,
    CostData,
    DrugInteractionRepository,
)


async def seed_database(db_path: str = "medi-cabinet.db"):
    """Seed database with sample medicines.

    Args:
        db_path: Path to database file
    """
    # Sample medicines (common in Bangladesh)
    sample_medicines = [
        {
            "name": "Napa",
            "quantity": 20,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=365),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Napa Extra",
            "quantity": 10,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=180),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Sergel",
            "quantity": 15,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=270),
            "location": "Bedroom Drawer",
        },
        {
            "name": "Seclo",
            "quantity": 8,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=150),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Ace",
            "quantity": 12,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=300),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Maxpro",
            "quantity": 2,  # Low stock
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=90),
            "location": "Kitchen Shelf",
        },
        {
            "name": "Alatrol",
            "quantity": 6,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=400),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Fexo",
            "quantity": 1,  # Very low stock
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=200),
            "location": "Bedroom Drawer",
        },
        {
            "name": "Virux Syrup",
            "quantity": 1,
            "unit": "bottle",
            "expiry_date": datetime.now() + timedelta(days=120),
            "location": "Refrigerator",
        },
        {
            "name": "Histacin",
            "quantity": 18,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=450),
            "location": "Medicine Cabinet",
        },
        {
            "name": "Fexo One",
            "quantity": 5,
            "unit": "tablets",
            "expiry_date": datetime.now() + timedelta(days=25),  # Expiring soon
            "location": "Kitchen Shelf",
        },
    ]

    async with Database(db_path) as db:
        medicine_repo = MedicineRepository(db)

        print(f"Seeding database: {db_path}")
        print("-" * 50)

        for med in sample_medicines:
            medicine_data = MedicineData(
                name=med["name"],
                quantity=med["quantity"],
                unit=med["unit"],
                expiry_date=med["expiry_date"],
                location=med["location"],
                added_by_user_id=123456,  # Demo user ID
                added_by_username="Demo User",
                group_chat_id=111111,  # Demo group ID
            )

            medicine = await medicine_repo.add_medicine(medicine_data)
            print(
                f"✅ Added: {medicine.name} ({medicine.quantity} {medicine.unit}) - Expires: {medicine.expiry_date.strftime('%b %Y') if medicine.expiry_date else 'N/A'}"
            )

    # Seed drug interactions
    interactions_file = Path(__file__).parent.parent / "data" / "drug_interactions.json"
    if interactions_file.exists():
        async with Database(db_path) as db:
            interaction_repo = DrugInteractionRepository(db)
            with open(interactions_file) as f:
                interactions = json.load(f)
            count = await interaction_repo.seed_interactions(interactions)
            print(f"\nSeeded {count} drug interactions")

    # Seed sample routines
    sample_routines = [
        {
            "medicine_name": "Napa",
            "dosage_quantity": 1,
            "dosage_unit": "tablets",
            "frequency": "daily",
            "times_of_day": ["08:00", "20:00"],
            "meal_relation": "after_meal",
        },
        {
            "medicine_name": "Sergel",
            "dosage_quantity": 1,
            "dosage_unit": "tablets",
            "frequency": "daily",
            "times_of_day": ["07:00"],
            "meal_relation": "before_meal",
        },
    ]

    async with Database(db_path) as db:
        routine_repo = RoutineRepository(db)
        for rtn in sample_routines:
            try:
                data = RoutineData(
                    medicine_name=rtn["medicine_name"],
                    dosage_quantity=rtn["dosage_quantity"],
                    dosage_unit=rtn["dosage_unit"],
                    frequency=rtn["frequency"],
                    times_of_day=rtn["times_of_day"],
                    meal_relation=rtn.get("meal_relation"),
                    created_by_user_id=123456,
                    created_by_username="Demo User",
                    group_chat_id=111111,
                )
                routine = await routine_repo.create(data)
                print(
                    f"Added routine: {routine.medicine_name} "
                    f"at {', '.join(routine.times_of_day)} {routine.frequency}"
                )
            except Exception as e:
                print(f"Could not seed routine (table may not exist): {e}")
                break

    # Seed sample cost entries
    async with Database(db_path) as db:
        medicine_repo = MedicineRepository(db)
        cost_repo = CostRepository(db)
        for name, cost in [("Napa", 30), ("Sergel", 120), ("Alatrol", 50)]:
            try:
                med = await medicine_repo.find_by_exact_name(name, 111111)
                if med:
                    data = CostData(
                        medicine_id=med.id,
                        total_cost=cost,
                        user_id=123456,
                        username="Demo User",
                        group_chat_id=111111,
                    )
                    await cost_repo.add_cost(data)
                    print(f"Added cost: {name} = {cost} BDT")
            except Exception as e:
                print(f"Could not seed cost (table may not exist): {e}")
                break

    print("-" * 50)
    print(f"Successfully seeded {len(sample_medicines)} medicines!")
    print(f"Database: {db_path}")
    print("\nDemo features:")
    print("  - 2 low stock medicines (< 3 units)")
    print("  - 1 expiring soon (< 30 days)")
    print("  - Various locations")
    print("  - Drug interaction data")
    print("  - Sample routines")
    print("  - Sample cost entries")
    print("\nTry these commands in your bot:")
    print("  ?all - List all medicines")
    print("  ?Napa - Search for Napa")
    print("  -Napa 2 - Use 2 Napa tablets")
    print("  /routine list - View routines")
    print("  /costs - View cost summary")
    print("  /analytics - View analytics")
    print("  /stats - View statistics")


def main():
    """Run seed script."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with sample data")
    parser.add_argument(
        "--db",
        type=str,
        default="medi-cabinet.db",
        help="Database path (default: medi-cabinet.db)",
    )

    args = parser.parse_args()

    asyncio.run(seed_database(args.db))


if __name__ == "__main__":
    main()
