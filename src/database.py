"""Database operations using repository pattern with async SQLite."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiosqlite
from fuzzywuzzy import fuzz


@dataclass
class Medicine:
    """Medicine entity."""

    id: int
    name: str
    quantity: int
    unit: str
    expiry_date: datetime | None
    location: str | None
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
    quantity_change: int | None
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
    expiry_date: datetime | None
    location: str | None
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
        super().__init__(f"Insufficient stock: {available} available, {requested} requested")


class Database:
    """Database connection manager with async context support."""

    def __init__(self, db_path: str):
        """Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

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

    async def fetch_one(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
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

    async def fetch_all(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
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
            expiry_date=datetime.fromisoformat(row["expiry_date"]) if row["expiry_date"] else None,
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
            row = await self.db.fetch_one("SELECT * FROM medicines WHERE id = ?", (existing.id,))
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

    async def find_by_exact_name(self, name: str, group_chat_id: int) -> Medicine | None:
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
    ) -> list[tuple[Medicine, int]]:
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
        matches: list[tuple[Medicine, int]] = []
        for row in rows:
            medicine = self._row_to_medicine(row)
            score = fuzz.ratio(name.lower(), medicine.name.lower())

            if score >= threshold:
                matches.append((medicine, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    async def get_by_id(self, medicine_id: int, group_chat_id: int) -> Medicine | None:
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

    async def get_all(self, group_chat_id: int) -> list[Medicine]:
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

    async def get_low_stock(self, group_chat_id: int, threshold: int = 3) -> list[Medicine]:
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

    async def get_expiring_soon(self, group_chat_id: int, days: int = 30) -> list[Medicine]:
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
        quantity_change: int | None = None,
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

    async def get_history(self, medicine_id: int, limit: int = 50) -> list[Activity]:
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
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (medicine_id, limit),
        )

        return [self._row_to_activity(row) for row in rows]

    async def get_stats(self, group_chat_id: int, days: int = 30) -> dict[str, Any]:
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
            "activities_by_action": {row["action"]: row["count"] for row in action_rows},
            "most_active_users": [
                {"username": row["username"], "count": row["count"]} for row in user_rows
            ],
            "most_used_medicines": [
                {"name": row["name"], "usage_count": row["usage_count"]} for row in medicine_rows
            ],
            "period_days": days,
        }


# --- Phase 4: Routine entities ---


@dataclass
class Routine:
    """Routine entity."""

    id: int
    medicine_id: int | None
    medicine_name: str
    dosage_quantity: int
    dosage_unit: str
    frequency: str
    times_of_day: list[str]
    days_of_week: list[str] | None
    meal_relation: str | None
    status: str
    notes: str | None
    created_by_user_id: int
    created_by_username: str
    group_chat_id: int
    created_at: datetime
    updated_at: datetime
    start_date: datetime | None
    end_date: datetime | None


@dataclass
class RoutineLog:
    """Routine log entry."""

    id: int
    routine_id: int
    scheduled_time: datetime
    actual_time: datetime | None
    status: str
    group_chat_id: int
    created_at: datetime


@dataclass
class RoutineData:
    """DTO for creating routines."""

    medicine_name: str
    dosage_quantity: int = 1
    dosage_unit: str = "tablets"
    frequency: str = "daily"
    times_of_day: list[str] = field(default_factory=lambda: ["08:00"])
    days_of_week: list[str] | None = None
    meal_relation: str | None = None
    notes: str | None = None
    created_by_user_id: int = 0
    created_by_username: str = ""
    group_chat_id: int = 0
    medicine_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass
class DrugInteraction:
    """Drug interaction entity."""

    id: int
    drug_a_name: str
    drug_b_name: str
    severity: str
    description: str
    source: str | None


@dataclass
class MedicineCost:
    """Medicine cost entity."""

    id: int
    medicine_id: int
    cost_per_unit: float | None
    currency: str
    purchase_date: datetime | None
    total_quantity: int | None
    total_cost: float
    user_id: int
    username: str
    group_chat_id: int
    created_at: datetime


@dataclass
class CostData:
    """DTO for adding cost entries."""

    medicine_id: int
    total_cost: float
    user_id: int
    username: str
    group_chat_id: int
    currency: str = "BDT"
    cost_per_unit: float | None = None
    total_quantity: int | None = None
    purchase_date: datetime | None = None


class RoutineRepository:
    """Repository for routine CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row_to_routine(row: aiosqlite.Row) -> Routine:
        """Convert database row to Routine entity."""
        return Routine(
            id=row["id"],
            medicine_id=row["medicine_id"],
            medicine_name=row["medicine_name"],
            dosage_quantity=row["dosage_quantity"],
            dosage_unit=row["dosage_unit"],
            frequency=row["frequency"],
            times_of_day=json.loads(row["times_of_day"]),
            days_of_week=json.loads(row["days_of_week"]) if row["days_of_week"] else None,
            meal_relation=row["meal_relation"],
            status=row["status"],
            notes=row["notes"],
            created_by_user_id=row["created_by_user_id"],
            created_by_username=row["created_by_username"],
            group_chat_id=row["group_chat_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            start_date=(datetime.fromisoformat(row["start_date"]) if row["start_date"] else None),
            end_date=datetime.fromisoformat(row["end_date"]) if row["end_date"] else None,
        )

    async def create(self, data: RoutineData) -> Routine:
        """Create a new routine."""
        cursor = await self.db.execute(
            """
            INSERT INTO routines (
                medicine_id, medicine_name, dosage_quantity, dosage_unit,
                frequency, times_of_day, days_of_week, meal_relation,
                notes, created_by_user_id, created_by_username, group_chat_id,
                start_date, end_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.medicine_id,
                data.medicine_name,
                data.dosage_quantity,
                data.dosage_unit,
                data.frequency,
                json.dumps(data.times_of_day),
                json.dumps(data.days_of_week) if data.days_of_week else None,
                data.meal_relation,
                data.notes,
                data.created_by_user_id,
                data.created_by_username,
                data.group_chat_id,
                data.start_date,
                data.end_date,
            ),
        )
        row = await self.db.fetch_one("SELECT * FROM routines WHERE id = ?", (cursor.lastrowid,))
        if not row:
            raise DatabaseError("Failed to create routine")
        return self._row_to_routine(row)

    async def get_by_id(self, routine_id: int) -> Routine | None:
        """Get routine by ID."""
        row = await self.db.fetch_one("SELECT * FROM routines WHERE id = ?", (routine_id,))
        return self._row_to_routine(row) if row else None

    async def get_active_routines(self, group_chat_id: int | None = None) -> list[Routine]:
        """Get all active routines, optionally filtered by group."""
        if group_chat_id is not None:
            rows = await self.db.fetch_all(
                "SELECT * FROM routines WHERE status = 'active' AND group_chat_id = ? ORDER BY medicine_name",
                (group_chat_id,),
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM routines WHERE status = 'active' ORDER BY medicine_name"
            )
        return [self._row_to_routine(row) for row in rows]

    async def get_user_routines(self, user_id: int, group_chat_id: int) -> list[Routine]:
        """Get routines created by a specific user in a group."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM routines
            WHERE created_by_user_id = ? AND group_chat_id = ?
            ORDER BY status, medicine_name
            """,
            (user_id, group_chat_id),
        )
        return [self._row_to_routine(row) for row in rows]

    async def update_status(self, routine_id: int, status: str) -> Routine | None:
        """Update routine status (active/paused/completed)."""
        await self.db.execute(
            "UPDATE routines SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, routine_id),
        )
        return await self.get_by_id(routine_id)

    async def delete(self, routine_id: int) -> bool:
        """Delete a routine."""
        cursor = await self.db.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
        return cursor.rowcount > 0

    async def link_medicine(self, routine_id: int, medicine_id: int) -> None:
        """Link a routine to a medicine inventory entry."""
        await self.db.execute(
            "UPDATE routines SET medicine_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (medicine_id, routine_id),
        )


class RoutineLogRepository:
    """Repository for routine log operations."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row_to_log(row: aiosqlite.Row) -> RoutineLog:
        return RoutineLog(
            id=row["id"],
            routine_id=row["routine_id"],
            scheduled_time=datetime.fromisoformat(row["scheduled_time"]),
            actual_time=(
                datetime.fromisoformat(row["actual_time"]) if row["actual_time"] else None
            ),
            status=row["status"],
            group_chat_id=row["group_chat_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def create_log(
        self, routine_id: int, scheduled_time: datetime, group_chat_id: int
    ) -> RoutineLog:
        """Create a pending log entry for a scheduled reminder."""
        cursor = await self.db.execute(
            """
            INSERT INTO routine_logs (routine_id, scheduled_time, status, group_chat_id)
            VALUES (?, ?, 'pending', ?)
            """,
            (routine_id, scheduled_time.isoformat(), group_chat_id),
        )
        row = await self.db.fetch_one(
            "SELECT * FROM routine_logs WHERE id = ?", (cursor.lastrowid,)
        )
        if not row:
            raise DatabaseError("Failed to create routine log")
        return self._row_to_log(row)

    async def mark_taken(self, log_id: int) -> RoutineLog | None:
        """Mark a routine log as taken."""
        await self.db.execute(
            "UPDATE routine_logs SET status = 'taken', actual_time = CURRENT_TIMESTAMP WHERE id = ?",
            (log_id,),
        )
        row = await self.db.fetch_one("SELECT * FROM routine_logs WHERE id = ?", (log_id,))
        return self._row_to_log(row) if row else None

    async def mark_missed(self, log_id: int) -> None:
        """Mark a routine log as missed."""
        await self.db.execute("UPDATE routine_logs SET status = 'missed' WHERE id = ?", (log_id,))

    async def mark_skipped(self, log_id: int) -> None:
        """Mark a routine log as skipped."""
        await self.db.execute("UPDATE routine_logs SET status = 'skipped' WHERE id = ?", (log_id,))

    async def mark_old_pending_as_missed(self, routine_id: int) -> int:
        """Mark old pending logs as missed (before creating new ones)."""
        cursor = await self.db.execute(
            """
            UPDATE routine_logs
            SET status = 'missed'
            WHERE routine_id = ? AND status = 'pending'
              AND scheduled_time < datetime('now', '-1 hour')
            """,
            (routine_id,),
        )
        return cursor.rowcount

    async def get_pending_log(self, routine_id: int) -> RoutineLog | None:
        """Get the most recent pending log for a routine."""
        row = await self.db.fetch_one(
            """
            SELECT * FROM routine_logs
            WHERE routine_id = ? AND status = 'pending'
            ORDER BY scheduled_time DESC
            LIMIT 1
            """,
            (routine_id,),
        )
        return self._row_to_log(row) if row else None

    async def get_adherence_stats(self, group_chat_id: int, days: int = 30) -> dict[str, Any]:
        """Get adherence statistics for routines in a group."""
        cutoff = datetime.now() - timedelta(days=days)

        total_row = await self.db.fetch_one(
            """
            SELECT COUNT(*) as total FROM routine_logs
            WHERE group_chat_id = ? AND scheduled_time >= ?
            """,
            (group_chat_id, cutoff.isoformat()),
        )

        status_rows = await self.db.fetch_all(
            """
            SELECT status, COUNT(*) as count FROM routine_logs
            WHERE group_chat_id = ? AND scheduled_time >= ?
            GROUP BY status
            """,
            (group_chat_id, cutoff.isoformat()),
        )

        total = total_row["total"] if total_row else 0
        by_status = {row["status"]: row["count"] for row in status_rows}
        taken = by_status.get("taken", 0)
        adherence_rate = (taken / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "adherence_rate": round(adherence_rate, 1),
            "period_days": days,
        }


class DrugInteractionRepository:
    """Repository for drug interaction checking."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row_to_interaction(row: aiosqlite.Row) -> DrugInteraction:
        return DrugInteraction(
            id=row["id"],
            drug_a_name=row["drug_a_name"],
            drug_b_name=row["drug_b_name"],
            severity=row["severity"],
            description=row["description"],
            source=row["source"],
        )

    async def check_interaction(self, drug_a: str, drug_b: str) -> DrugInteraction | None:
        """Check if two drugs have a known interaction."""
        row = await self.db.fetch_one(
            """
            SELECT * FROM drug_interactions
            WHERE (LOWER(drug_a_name) = LOWER(?) AND LOWER(drug_b_name) = LOWER(?))
               OR (LOWER(drug_a_name) = LOWER(?) AND LOWER(drug_b_name) = LOWER(?))
            """,
            (drug_a, drug_b, drug_b, drug_a),
        )
        return self._row_to_interaction(row) if row else None

    async def check_against_cabinet(
        self, drug_name: str, group_chat_id: int
    ) -> list[DrugInteraction]:
        """Check a drug against all medicines in the cabinet."""
        rows = await self.db.fetch_all(
            """
            SELECT di.* FROM drug_interactions di
            JOIN medicines m ON (
                LOWER(m.name) = LOWER(di.drug_a_name)
                OR LOWER(m.name) = LOWER(di.drug_b_name)
            )
            WHERE m.group_chat_id = ?
              AND m.quantity > 0
              AND (LOWER(di.drug_a_name) = LOWER(?) OR LOWER(di.drug_b_name) = LOWER(?))
            """,
            (group_chat_id, drug_name, drug_name),
        )
        return [self._row_to_interaction(row) for row in rows]

    async def seed_interactions(self, interactions: list[dict[str, str]]) -> int:
        """Seed the database with known drug interactions.

        Args:
            interactions: List of dicts with keys: drug_a, drug_b, severity, description, source

        Returns:
            Number of interactions inserted
        """
        count = 0
        for item in interactions:
            try:
                await self.db.execute(
                    """
                    INSERT OR IGNORE INTO drug_interactions
                        (drug_a_name, drug_b_name, severity, description, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        item["drug_a"],
                        item["drug_b"],
                        item["severity"],
                        item["description"],
                        item.get("source", ""),
                    ),
                )
                count += 1
            except Exception:
                continue
        return count


class CostRepository:
    """Repository for medicine cost tracking."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row_to_cost(row: aiosqlite.Row) -> MedicineCost:
        return MedicineCost(
            id=row["id"],
            medicine_id=row["medicine_id"],
            cost_per_unit=row["cost_per_unit"],
            currency=row["currency"],
            purchase_date=(
                datetime.fromisoformat(row["purchase_date"]) if row["purchase_date"] else None
            ),
            total_quantity=row["total_quantity"],
            total_cost=row["total_cost"],
            user_id=row["user_id"],
            username=row["username"],
            group_chat_id=row["group_chat_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def add_cost(self, data: CostData) -> MedicineCost:
        """Add a cost entry for a medicine."""
        cursor = await self.db.execute(
            """
            INSERT INTO medicine_costs (
                medicine_id, cost_per_unit, currency, purchase_date,
                total_quantity, total_cost, user_id, username, group_chat_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.medicine_id,
                data.cost_per_unit,
                data.currency,
                data.purchase_date,
                data.total_quantity,
                data.total_cost,
                data.user_id,
                data.username,
                data.group_chat_id,
            ),
        )
        row = await self.db.fetch_one(
            "SELECT * FROM medicine_costs WHERE id = ?", (cursor.lastrowid,)
        )
        if not row:
            raise DatabaseError("Failed to create cost entry")
        return self._row_to_cost(row)

    async def get_total_spent(self, group_chat_id: int, days: int | None = None) -> float:
        """Get total amount spent on medicines."""
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            row = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(total_cost), 0) as total
                FROM medicine_costs
                WHERE group_chat_id = ? AND created_at >= ?
                """,
                (group_chat_id, cutoff.isoformat()),
            )
        else:
            row = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(total_cost), 0) as total
                FROM medicine_costs
                WHERE group_chat_id = ?
                """,
                (group_chat_id,),
            )
        return float(row["total"]) if row else 0.0

    async def get_cost_summary(self, group_chat_id: int, days: int = 30) -> dict[str, Any]:
        """Get cost summary grouped by medicine."""
        cutoff = datetime.now() - timedelta(days=days)

        rows = await self.db.fetch_all(
            """
            SELECT m.name, SUM(mc.total_cost) as total, mc.currency,
                   COUNT(mc.id) as purchases
            FROM medicine_costs mc
            JOIN medicines m ON mc.medicine_id = m.id
            WHERE mc.group_chat_id = ? AND mc.created_at >= ?
            GROUP BY m.name, mc.currency
            ORDER BY total DESC
            """,
            (group_chat_id, cutoff.isoformat()),
        )

        total_spent = sum(row["total"] for row in rows)

        return {
            "by_medicine": [
                {
                    "name": row["name"],
                    "total_cost": row["total"],
                    "currency": row["currency"],
                    "purchases": row["purchases"],
                }
                for row in rows
            ],
            "total_spent": total_spent,
            "period_days": days,
        }
