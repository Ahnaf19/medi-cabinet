"""Database operations using repository pattern with async SQLite."""

import aiosqlite
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from fuzzywuzzy import fuzz


@dataclass
class Medicine:
    """Medicine entity."""

    id: int
    name: str
    quantity: int
    unit: str
    expiry_date: Optional[datetime]
    location: Optional[str]
    added_by_user_id: int
    added_by_username: str
    added_date: datetime
    group_chat_id: int
    last_updated: datetime


@dataclass
class Activity:
    """Activity log entity."""

    id: int
    medicine_id: int
    action: str
    quantity_change: Optional[int]
    user_id: int
    username: str
    timestamp: datetime
    group_chat_id: int


@dataclass
class MedicineData:
    """Data transfer object for creating/updating medicines."""

    name: str
    quantity: int
    unit: str
    expiry_date: Optional[datetime]
    location: Optional[str]
    added_by_user_id: int
    added_by_username: str
    group_chat_id: int


class DatabaseError(Exception):
    """Base exception for database errors."""

    pass


class InsufficientStockError(DatabaseError):
    """Exception raised when trying to use more medicine than available."""

    def __init__(self, available: int, requested: int):
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock: {available} available, {requested} requested"
        )


class Database:
    """Database connection manager with async context support."""

    def __init__(self, db_path: str):
        """Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def __aenter__(self):
        """Open database connection."""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        # Enable foreign key support
        await self.conn.execute("PRAGMA foreign_keys = ON")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if self.conn:
            await self.conn.close()

    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a query and commit.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cursor object
        """
        if not self.conn:
            raise DatabaseError("Database connection not opened")
        cursor = await self.conn.execute(query, params)
        await self.conn.commit()
        return cursor

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetch one row from database.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Row object or None
        """
        if not self.conn:
            raise DatabaseError("Database connection not opened")
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchone()

    async def fetch_all(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        """Fetch all rows from database.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of Row objects
        """
        if not self.conn:
            raise DatabaseError("Database connection not opened")
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchall()


class MedicineRepository:
    """Repository for medicine CRUD operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db

    @staticmethod
    def _row_to_medicine(row: aiosqlite.Row) -> Medicine:
        """Convert database row to Medicine entity.

        Args:
            row: Database row

        Returns:
            Medicine entity
        """
        return Medicine(
            id=row["id"],
            name=row["name"],
            quantity=row["quantity"],
            unit=row["unit"],
            expiry_date=datetime.fromisoformat(row["expiry_date"])
            if row["expiry_date"]
            else None,
            location=row["location"],
            added_by_user_id=row["added_by_user_id"],
            added_by_username=row["added_by_username"],
            added_date=datetime.fromisoformat(row["added_date"]),
            group_chat_id=row["group_chat_id"],
            last_updated=datetime.fromisoformat(row["last_updated"]),
        )

    async def add_medicine(self, data: MedicineData) -> Medicine:
        """Add a new medicine or update existing one.

        Args:
            data: Medicine data

        Returns:
            Created or updated Medicine entity
        """
        # Check if medicine already exists in this group
        existing = await self.find_by_exact_name(data.name, data.group_chat_id)

        if existing:
            # Update existing medicine quantity
            new_quantity = existing.quantity + data.quantity
            await self.db.execute(
                """
                UPDATE medicines
                SET quantity = ?,
                    last_updated = CURRENT_TIMESTAMP,
                    expiry_date = COALESCE(?, expiry_date),
                    location = COALESCE(?, location)
                WHERE id = ?
                """,
                (new_quantity, data.expiry_date, data.location, existing.id),
            )
            # Fetch and return updated medicine
            row = await self.db.fetch_one(
                "SELECT * FROM medicines WHERE id = ?", (existing.id,)
            )
        else:
            # Insert new medicine
            cursor = await self.db.execute(
                """
                INSERT INTO medicines (
                    name, quantity, unit, expiry_date, location,
                    added_by_user_id, added_by_username, group_chat_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.name,
                    data.quantity,
                    data.unit,
                    data.expiry_date,
                    data.location,
                    data.added_by_user_id,
                    data.added_by_username,
                    data.group_chat_id,
                ),
            )
            # Fetch newly created medicine
            row = await self.db.fetch_one(
                "SELECT * FROM medicines WHERE id = ?", (cursor.lastrowid,)
            )

        if not row:
            raise DatabaseError("Failed to create/update medicine")

        return self._row_to_medicine(row)

    async def update_quantity(self, medicine_id: int, delta: int, group_chat_id: int) -> Medicine:
        """Update medicine quantity (can be positive or negative).

        Args:
            medicine_id: Medicine ID
            delta: Quantity change (positive for add, negative for use)
            group_chat_id: Group chat ID for isolation

        Returns:
            Updated Medicine entity

        Raises:
            InsufficientStockError: If trying to use more than available
            DatabaseError: If medicine not found
        """
        # Get current medicine with row lock
        row = await self.db.fetch_one(
            """
            SELECT * FROM medicines
            WHERE id = ? AND group_chat_id = ?
            """,
            (medicine_id, group_chat_id),
        )

        if not row:
            raise DatabaseError(f"Medicine with ID {medicine_id} not found")

        new_quantity = row["quantity"] + delta

        if new_quantity < 0:
            raise InsufficientStockError(available=row["quantity"], requested=abs(delta))

        # Update quantity
        await self.db.execute(
            """
            UPDATE medicines
            SET quantity = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_quantity, medicine_id),
        )

        # Fetch updated medicine
        updated_row = await self.db.fetch_one(
            "SELECT * FROM medicines WHERE id = ?", (medicine_id,)
        )

        if not updated_row:
            raise DatabaseError("Failed to fetch updated medicine")

        return self._row_to_medicine(updated_row)

    async def find_by_exact_name(
        self, name: str, group_chat_id: int
    ) -> Optional[Medicine]:
        """Find medicine by exact name (case-insensitive).

        Args:
            name: Medicine name
            group_chat_id: Group chat ID for isolation

        Returns:
            Medicine entity or None
        """
        row = await self.db.fetch_one(
            """
            SELECT * FROM medicines
            WHERE LOWER(name) = LOWER(?) AND group_chat_id = ?
            """,
            (name, group_chat_id),
        )

        return self._row_to_medicine(row) if row else None

    async def find_by_name_fuzzy(
        self, name: str, group_chat_id: int, threshold: int = 80
    ) -> List[Tuple[Medicine, int]]:
        """Find medicines by fuzzy name matching.

        Args:
            name: Medicine name to search
            group_chat_id: Group chat ID for isolation
            threshold: Minimum fuzzy match score (0-100)

        Returns:
            List of (Medicine, confidence_score) tuples, sorted by score descending
        """
        # Get all medicines in the group
        rows = await self.db.fetch_all(
            "SELECT * FROM medicines WHERE group_chat_id = ?", (group_chat_id,)
        )

        # Calculate fuzzy match scores
        matches: List[Tuple[Medicine, int]] = []
        for row in rows:
            medicine = self._row_to_medicine(row)
            score = fuzz.ratio(name.lower(), medicine.name.lower())

            if score >= threshold:
                matches.append((medicine, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    async def get_by_id(self, medicine_id: int, group_chat_id: int) -> Optional[Medicine]:
        """Get medicine by ID with group isolation.

        Args:
            medicine_id: Medicine ID
            group_chat_id: Group chat ID for isolation

        Returns:
            Medicine entity or None
        """
        row = await self.db.fetch_one(
            """
            SELECT * FROM medicines
            WHERE id = ? AND group_chat_id = ?
            """,
            (medicine_id, group_chat_id),
        )

        return self._row_to_medicine(row) if row else None

    async def get_all(self, group_chat_id: int) -> List[Medicine]:
        """Get all medicines for a group.

        Args:
            group_chat_id: Group chat ID for isolation

        Returns:
            List of Medicine entities
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM medicines
            WHERE group_chat_id = ?
            ORDER BY name
            """,
            (group_chat_id,),
        )

        return [self._row_to_medicine(row) for row in rows]

    async def get_low_stock(self, group_chat_id: int, threshold: int = 3) -> List[Medicine]:
        """Get medicines with low stock.

        Args:
            group_chat_id: Group chat ID for isolation
            threshold: Stock threshold

        Returns:
            List of Medicine entities with quantity < threshold
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM medicines
            WHERE group_chat_id = ? AND quantity < ?
            ORDER BY quantity ASC
            """,
            (group_chat_id, threshold),
        )

        return [self._row_to_medicine(row) for row in rows]

    async def get_expiring_soon(
        self, group_chat_id: int, days: int = 30
    ) -> List[Medicine]:
        """Get medicines expiring within specified days.

        Args:
            group_chat_id: Group chat ID for isolation
            days: Number of days to check

        Returns:
            List of Medicine entities expiring soon
        """
        cutoff_date = datetime.now() + timedelta(days=days)

        rows = await self.db.fetch_all(
            """
            SELECT * FROM medicines
            WHERE group_chat_id = ?
              AND expiry_date IS NOT NULL
              AND expiry_date <= ?
            ORDER BY expiry_date ASC
            """,
            (group_chat_id, cutoff_date.isoformat()),
        )

        return [self._row_to_medicine(row) for row in rows]

    async def delete_medicine(self, medicine_id: int, group_chat_id: int) -> bool:
        """Delete a medicine.

        Args:
            medicine_id: Medicine ID
            group_chat_id: Group chat ID for isolation

        Returns:
            True if deleted, False if not found
        """
        cursor = await self.db.execute(
            """
            DELETE FROM medicines
            WHERE id = ? AND group_chat_id = ?
            """,
            (medicine_id, group_chat_id),
        )

        return cursor.rowcount > 0


class ActivityLogRepository:
    """Repository for activity log operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db

    @staticmethod
    def _row_to_activity(row: aiosqlite.Row) -> Activity:
        """Convert database row to Activity entity.

        Args:
            row: Database row

        Returns:
            Activity entity
        """
        return Activity(
            id=row["id"],
            medicine_id=row["medicine_id"],
            action=row["action"],
            quantity_change=row["quantity_change"],
            user_id=row["user_id"],
            username=row["username"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            group_chat_id=row["group_chat_id"],
        )

    async def log_activity(
        self,
        medicine_id: int,
        action: str,
        user_id: int,
        username: str,
        group_chat_id: int,
        quantity_change: Optional[int] = None,
    ) -> Activity:
        """Log an activity.

        Args:
            medicine_id: Medicine ID
            action: Action type ('added', 'used', 'searched', 'deleted')
            user_id: User ID who performed the action
            username: Username who performed the action
            group_chat_id: Group chat ID
            quantity_change: Quantity change (optional)

        Returns:
            Created Activity entity
        """
        cursor = await self.db.execute(
            """
            INSERT INTO activity_log (
                medicine_id, action, quantity_change,
                user_id, username, group_chat_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (medicine_id, action, quantity_change, user_id, username, group_chat_id),
        )

        # Fetch newly created activity
        row = await self.db.fetch_one(
            "SELECT * FROM activity_log WHERE id = ?", (cursor.lastrowid,)
        )

        if not row:
            raise DatabaseError("Failed to create activity log")

        return self._row_to_activity(row)

    async def get_history(
        self, medicine_id: int, limit: int = 50
    ) -> List[Activity]:
        """Get activity history for a medicine.

        Args:
            medicine_id: Medicine ID
            limit: Maximum number of activities to return

        Returns:
            List of Activity entities, most recent first
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM activity_log
            WHERE medicine_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (medicine_id, limit),
        )

        return [self._row_to_activity(row) for row in rows]

    async def get_stats(self, group_chat_id: int, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for a group.

        Args:
            group_chat_id: Group chat ID
            days: Number of days to include in stats

        Returns:
            Dictionary with statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Total activities
        total_row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM activity_log
            WHERE group_chat_id = ? AND timestamp >= ?
            """,
            (group_chat_id, cutoff_date.isoformat()),
        )

        # Activities by action
        action_rows = await self.db.fetch_all(
            """
            SELECT action, COUNT(*) as count
            FROM activity_log
            WHERE group_chat_id = ? AND timestamp >= ?
            GROUP BY action
            """,
            (group_chat_id, cutoff_date.isoformat()),
        )

        # Most active users
        user_rows = await self.db.fetch_all(
            """
            SELECT username, COUNT(*) as count
            FROM activity_log
            WHERE group_chat_id = ? AND timestamp >= ?
            GROUP BY username
            ORDER BY count DESC
            LIMIT 5
            """,
            (group_chat_id, cutoff_date.isoformat()),
        )

        # Most used medicines
        medicine_rows = await self.db.fetch_all(
            """
            SELECT m.name, COUNT(a.id) as usage_count
            FROM activity_log a
            JOIN medicines m ON a.medicine_id = m.id
            WHERE a.group_chat_id = ? AND a.timestamp >= ? AND a.action = 'used'
            GROUP BY m.name
            ORDER BY usage_count DESC
            LIMIT 5
            """,
            (group_chat_id, cutoff_date.isoformat()),
        )

        return {
            "total_activities": total_row["count"] if total_row else 0,
            "activities_by_action": {
                row["action"]: row["count"] for row in action_rows
            },
            "most_active_users": [
                {"username": row["username"], "count": row["count"]}
                for row in user_rows
            ],
            "most_used_medicines": [
                {"name": row["name"], "usage_count": row["usage_count"]}
                for row in medicine_rows
            ],
            "period_days": days,
        }
