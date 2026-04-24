"""
CoachAI Flask API.

Single endpoint /api/generate-plan returns a structured weekly S&C plan
based on the user's sport, position, goal and available equipment.

Static frontend (HTML/CSS/JS) is served from ../frontend.
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from recommender import generate_plan

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_file(filename):
    #Serve any file in the frontend folder (CSS, JS, images).
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    data = request.get_json(silent=True) or {}
    required = ["sport", "position", "goal", "equipment"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        plan = generate_plan(
            sport=data["sport"],
            position=data["position"],
            goal=data["goal"],
            equipment=data["equipment"],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(plan)


if __name__ == "__main__":
    #Use 0.0.0.0 so the app is reachable from a phone on the same network.
    app.run(host="0.0.0.0", port=5001, debug=True)
