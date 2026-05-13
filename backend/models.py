"""
CoachAI Cycle 2 data model.

Two tables: User (authentication) and SavedPlan (per-user plan snapshots).
Anonymous use is preserved — these models are only consulted when a user is
signed in, so the rule-based generator continues to work without any DB at all.
"""

from datetime import datetime
import json

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """A registered CoachAI user."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    saved_plans = db.relationship(
        "SavedPlan", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class SavedPlan(db.Model):
    """An immutable snapshot of a generated weekly plan, saved by a user.

    The full plan JSON is stored verbatim in `plan_json` so that a saved plan
    survives subsequent changes to the recommender or exercise database.
    Read-only by design (no edit endpoints in Cycle 2).
    """

    __tablename__ = "saved_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(120), nullable=False)
    sport = db.Column(db.String(40), nullable=False)
    position = db.Column(db.String(40), nullable=False)
    goal = db.Column(db.String(40), nullable=False)
    equipment = db.Column(db.String(40), nullable=False)

    plan_json = db.Column(db.Text, nullable=False)
    # JSON array of session indices the user has marked complete.
    # The plan content remains a read-only snapshot; only completion state is mutable.
    completed_sessions = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_summary(self) -> dict:
        """Lightweight view for the 'My plans' list."""
        try:
            completed_count = len(json.loads(self.completed_sessions or "[]"))
        except Exception:
            completed_count = 0
        return {
            "id": self.id,
            "name": self.name,
            "sport": self.sport,
            "position": self.position,
            "goal": self.goal,
            "equipment": self.equipment,
            "completed_count": completed_count,
            "created_at": self.created_at.isoformat(),
        }

    def to_full(self) -> dict:
        """Full view including the cached plan JSON and per-user progress."""
        summary = self.to_summary()
        summary["plan"] = json.loads(self.plan_json)
        try:
            summary["completed_sessions"] = json.loads(self.completed_sessions or "[]")
        except Exception:
            summary["completed_sessions"] = []
        return summary

    def __repr__(self) -> str:
        return f"<SavedPlan #{self.id} {self.sport}/{self.position} for user {self.user_id}>"
