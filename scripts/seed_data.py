"""Seed database with sample medicine data for demo purposes."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database, MedicineRepository, MedicineData


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

    print("-" * 50)
    print(f"✨ Successfully seeded {len(sample_medicines)} medicines!")
    print(f"📊 Database: {db_path}")
    print("\nDemo features:")
    print("  - 2 low stock medicines (< 3 units)")
    print("  - 1 expiring soon (< 30 days)")
    print("  - Various locations")
    print("\nTry these commands in your bot:")
    print("  ?all - List all medicines")
    print("  ?Napa - Search for Napa")
    print("  -Napa 2 - Use 2 Napa tablets")
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
