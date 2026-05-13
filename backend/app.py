"""
CoachAI Flask application (Cycle 2).

Cycle 1 (rule-based prototype) endpoint:
  POST /api/generate-plan          — generates a weekly S&C plan, no auth required.

Cycle 2 (extended system) endpoints:
  POST   /api/auth/signup
  POST   /api/auth/login
  POST   /api/auth/logout
  GET    /api/auth/me
  POST   /api/save-plan            — save the just-generated plan (auth required)
  GET    /api/my-plans             — list the signed-in user's saved plans
  GET    /api/plans/<plan_id>      — fetch one saved plan in full

Anonymous use is preserved throughout: all /api/auth/me responses are valid for
anonymous users, /api/generate-plan never requires auth, and the save/load
endpoints return 401 cleanly if invoked without a session.
"""

import json
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_login import LoginManager, current_user, login_required

from recommender import generate_plan
from models import db, User, SavedPlan
from auth import auth_bp


HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(HERE, "..", "frontend")
DB_PATH = os.path.join(HERE, "coachai.db")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # SECRET_KEY for session cookies. In production this would come from an env var;
    # for the prototype + Cycle 2 dev/demo we fall back to a stable default so that
    # signing in once and refreshing keeps you signed in.
    app.config["SECRET_KEY"] = os.environ.get("COACHAI_SECRET_KEY", "coachai-cycle2-dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = None  # We handle auth state on the frontend

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Authentication required."}), 401

    app.register_blueprint(auth_bp)

    # ---- Static frontend ---------------------------------------------------

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def static_file(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    # ---- Cycle 1: plan generation (anonymous OK) ---------------------------

    @app.post("/api/generate-plan")
    def api_generate_plan():
        data = request.get_json(silent=True) or {}
        required = ["sport", "position", "goal", "equipment"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        # Cycle 2: optional 'beginner_friendly' flag swaps coaching notes for the
        # tiered version (see build_tiered_notes.py). Defaults to False so the
        # baseline behaviour for anonymous users is unchanged.
        beginner_friendly = bool(data.get("beginner_friendly", False))

        try:
            plan = generate_plan(
                sport=data["sport"],
                position=data["position"],
                goal=data["goal"],
                equipment=data["equipment"],
                beginner_friendly=beginner_friendly,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        return jsonify(plan)

    # ---- Cycle 2: per-user plan persistence (auth required) ---------------

    @app.post("/api/save-plan")
    @login_required
    def api_save_plan():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        plan = data.get("plan") or {}

        if not name:
            return jsonify({"error": "Please give this plan a name."}), 400
        if not all(k in plan for k in ("sport", "position", "goal", "equipment", "sessions")):
            return jsonify({"error": "Plan payload is missing required fields."}), 400

        sp = SavedPlan(
            user_id=current_user.id,
            name=name[:120],
            sport=plan["sport"],
            position=plan["position"],
            goal=plan["goal"],
            equipment=plan["equipment"],
            plan_json=json.dumps(plan),
        )
        db.session.add(sp)
        db.session.commit()
        return jsonify(sp.to_summary()), 201

    @app.get("/api/my-plans")
    @login_required
    def api_my_plans():
        plans = (
            SavedPlan.query.filter_by(user_id=current_user.id)
            .order_by(SavedPlan.created_at.desc())
            .all()
        )
        return jsonify({"plans": [p.to_summary() for p in plans]})

    @app.get("/api/plans/<int:plan_id>")
    @login_required
    def api_get_plan(plan_id: int):
        sp = db.session.get(SavedPlan, plan_id)
        if not sp or sp.user_id != current_user.id:
            return jsonify({"error": "Plan not found."}), 404
        return jsonify(sp.to_full())

    @app.post("/api/plans/<int:plan_id>/progress")
    @login_required
    def api_update_progress(plan_id: int):
        """Persist which sessions of a saved plan the user has marked complete."""
        sp = db.session.get(SavedPlan, plan_id)
        if not sp or sp.user_id != current_user.id:
            return jsonify({"error": "Plan not found."}), 404
        data = request.get_json(silent=True) or {}
        completed = data.get("completed_sessions", [])
        if not isinstance(completed, list) or not all(
            isinstance(i, int) and 0 <= i < 10 for i in completed
        ):
            return jsonify({"error": "Invalid completion data."}), 400
        sp.completed_sessions = json.dumps(sorted(set(completed)))
        db.session.commit()
        return jsonify({"completed_sessions": json.loads(sp.completed_sessions)})

    # ---- DB bootstrap ------------------------------------------------------

    def _ensure_schema():
        """Add the completed_sessions column to existing saved_plans tables.

        SQLite doesn't natively support ALTER COLUMN, but ADD COLUMN is fine and
        idempotent enough — we just check for the column first. This lets users
        who set up the database before the progress feature was added keep their
        existing data instead of having to drop the DB.
        """
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        if "saved_plans" in inspector.get_table_names():
            cols = [c["name"] for c in inspector.get_columns("saved_plans")]
            if "completed_sessions" not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text(
                        "ALTER TABLE saved_plans "
                        "ADD COLUMN completed_sessions TEXT NOT NULL DEFAULT '[]'"
                    ))

    with app.app_context():
        db.create_all()
        _ensure_schema()

    return app


app = create_app()


if __name__ == "__main__":
    # 0.0.0.0 so the app is reachable from a phone on the same Wi-Fi.
    app.run(host="0.0.0.0", port=5001, debug=True)
