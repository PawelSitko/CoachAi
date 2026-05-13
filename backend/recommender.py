"""
CoachAI rule-based recommender.

Generates a structured weekly S&C plan from a user profile
(sport, position, goal, equipment) using curated exercise mappings
grounded in published S&C literature (Ramirez-Campillo et al. 2020;
Markovic 2007; Sheppard & Gabbett 2009).
"""

import json
import os
from typing import List, Dict

EXERCISE_PATH = os.path.join(os.path.dirname(__file__), "exercises.json")
TIERED_NOTES_PATH = os.path.join(os.path.dirname(__file__), "coaching_notes_tiered.json")

with open(EXERCISE_PATH, "r") as f:
    EXERCISES = {ex["id"]: ex for ex in json.load(f)["exercises"]}


# Cycle 2: optional tiered coaching notes authored at dev-time by Gemini and
# cached as a static JSON file (see build_tiered_notes.py). Loaded if present;
# absence is fine and means beginner_friendly mode silently falls back to the
# default coaching note.
try:
    with open(TIERED_NOTES_PATH, "r") as f:
        TIERED_NOTES = json.load(f)
except FileNotFoundError:
    TIERED_NOTES = {}


#Equipment is hierarchical: full_gym > dumbbells > bodyweight.
#A user with "dumbbells" can do bodyweight movements but not barbell lifts.
EQUIPMENT_RANK = {"bodyweight": 0, "dumbbells": 1, "full_gym": 2}


def _allowed(ex: dict, equipment: str) -> bool:
    """Return True if the user's equipment level can perform this exercise."""
    return EQUIPMENT_RANK[ex["equipment"]] <= EQUIPMENT_RANK[equipment]


def _filter(category: str, sport: str, equipment: str, exclude: set = None) -> List[dict]: # type: ignore
    """Return exercises in a category that match the sport, kit, and haven't been used yet."""
    exclude = exclude or set()
    return [
        ex for ex in EXERCISES.values()
        if ex["category"] == category
        and sport in ex["sport_tags"]
        and _allowed(ex, equipment)
        and ex["id"] not in exclude
    ]


def _pick(category: str, sport: str, equipment: str, n: int = 1, used: set = None) -> List[dict]: # type: ignore
    """Pick n unique exercises from a category, skipping any already in `used`."""
    pool = _filter(category, sport, equipment, exclude=used)
    if not pool:
        return []
    #Stable sort so picks are deterministic for the same inputs.
    pool.sort(key=lambda e: e["id"])
    picked = pool[:n]
    if used is not None:
        for ex in picked:
            used.add(ex["id"])
    return picked



# Session templates: each session is a list of (category, sets, reps, rest)
# tuples. Volumes follow standard S&C prescriptions:
#   strength: 3-5 sets x 4-8 reps, 2-3 min rest
#   power/plyo: 3-5 sets x 3-6 reps, full rest
#   accessory/core: 2-3 sets x 8-15 reps, 60-90s rest


def _session(name: str, focus: str, blocks: List[Dict]) -> Dict:
    return {"name": name, "focus": focus, "exercises": blocks}


# Module-level flag set inside generate_plan() (single-threaded Flask dev server,
# so a simple global is sufficient — keeps the 20+ call sites of _block unchanged).
_BEGINNER_FRIENDLY = False


def _block(ex: dict, sets: int, reps: str, rest: str) -> Dict:
    notes = ex.get("notes", "")
    if _BEGINNER_FRIENDLY:
        # Cycle 2: swap in the LLM-authored beginner rephrasing if available.
        # Falls back silently to the default note if the cache is missing.
        notes = TIERED_NOTES.get(ex["id"], {}).get("beginner", notes)
    return {
        "name": ex["name"],
        "category": ex["category"],
        "sets": sets,
        "reps": reps,
        "rest": rest,
        "notes": notes,
    }


def _lower_power_day(sport, equipment, goal, used):
    blocks = []
    #Plyometric primer (2 different moves)
    for ex in _pick("plyometric", sport, equipment, 2, used):
        blocks.append(_block(ex, 4, "5", "2 min"))
    #Main lower-body lift
    main = _pick("lower_power", sport, equipment, 1, used) or _pick("lower_strength", sport, equipment, 1, used)
    for ex in main:
        blocks.append(_block(ex, 4, "5", "3 min"))
    #Unilateral — guaranteed different from main lift
    for ex in _pick("lower_strength", sport, equipment, 1, used):
        blocks.append(_block(ex, 3, "8 each side", "90 s"))
    #Posterior chain accessory — only add if user's equipment supports it
    if "nordic_curl" not in used and _allowed(EXERCISES["nordic_curl"], equipment):
        blocks.append(_block(EXERCISES["nordic_curl"], 3, "6", "90 s"))
        used.add("nordic_curl")
    return _session("Day 1 \u2014 Lower-Body Power", goal, blocks)


def _upper_day(sport, equipment, goal, used):
    blocks = []
    #Fresh used set per session — upper exercises don't clash with lower days
    u = set()
    for ex in _pick("upper_push", sport, equipment, 1, u):
        blocks.append(_block(ex, 4, "6", "2 min"))
    for ex in _pick("upper_pull", sport, equipment, 1, u):
        blocks.append(_block(ex, 4, "6", "2 min"))
    for ex in _pick("upper_push", sport, equipment, 2, u)[:1]:
        blocks.append(_block(ex, 3, "10", "90 s"))
    for ex in _pick("upper_pull", sport, equipment, 2, u)[:1]:
        blocks.append(_block(ex, 3, "10", "90 s"))
    if EXERCISES["face_pull"]["equipment"] != "full_gym" or equipment == "full_gym":
        blocks.append(_block(EXERCISES["face_pull"], 3, "15", "60 s"))
    return _session("Day 2 \u2014 Upper-Body Strength", goal, blocks)


def _lower_strength_day(sport, equipment, goal, used):
    blocks = []
    for ex in _pick("lower_strength", sport, equipment, 1, used):
        blocks.append(_block(ex, 4, "6", "3 min"))
    for ex in _pick("lower_strength", sport, equipment, 1, used):
        blocks.append(_block(ex, 3, "10 each side", "90 s"))
    if "calf_raise" not in used:
        blocks.append(_block(EXERCISES["calf_raise"], 4, "12", "60 s"))
        used.add("calf_raise")
    if "copenhagen" not in used:
        blocks.append(_block(EXERCISES["copenhagen"], 3, "20 s each side", "60 s"))
        used.add("copenhagen")
    return _session("Day 3 \u2014 Lower-Body Strength & Resilience", goal, blocks)


def _power_agility_day(sport, equipment, goal, used):
    blocks = []
    #Fresh set — plyometrics can safely repeat across sessions
    u = set()
    if sport == "basketball":
        for ex in _pick("agility", sport, equipment, 2, u):
            blocks.append(_block(ex, 4, "20 s", "60 s"))
        for ex in _pick("plyometric", sport, equipment, 2, u):
            blocks.append(_block(ex, 3, "5 each side", "90 s"))
    else:  # volleyball
        for ex in _pick("plyometric", sport, equipment, 3, u):
            blocks.append(_block(ex, 4, "5", "90 s"))
    if equipment == "full_gym":
        blocks.append(_block(EXERCISES["med_ball_slam"], 3, "8", "60 s"))
        blocks.append(_block(EXERCISES["rotational_throw"], 3, "6 each side", "60 s"))
    return _session("Day 4 \u2014 Power & Agility", goal, blocks)


def _core_day(sport, equipment, goal, used):
    blocks = []
    u = set()
    for ex in _pick("core", sport, equipment, 3, u):
        blocks.append(_block(ex, 3, "30 s" if "plank" in ex["id"] else "10", "60 s"))
    blocks.append(_block(EXERCISES["ankle_hops"], 3, "20", "60 s"))
    return _session("Day 5 \u2014 Core & Recovery", goal, blocks)



# Goal-driven adjustments. The position parameter influences accent (e.g.
# middle blockers get extra jump volume) without changing the overall shape.

GOAL_FOCUS = {
    "vertical_jump": "Maximise vertical jump height through plyometric and lower-body power work.",
    "explosive_power": "Build whole-body explosive power for jumps, sprints and changes of direction.",
    "general_strength": "Develop a balanced strength base across the whole body.",
    "injury_prevention": "Reinforce joints and tissues most at risk in your sport.",
    "agility": "Improve change-of-direction and reactive footwork.",
}


POSITION_NOTES = {
    "middle_blocker": "Middle blockers accumulate the most jumps in a match \u2014 prioritise jump quality and posterior-chain recovery work.",
    "outside_hitter": "Outside hitters need both jump power and shoulder durability for repeated swings.",
    "setter": "Setters benefit from lateral movement, hand/wrist conditioning, and balanced lower-body work.",
    "libero": "Liberos need lateral agility, low-stance endurance and core anti-rotation.",
    "point_guard": "Point guards rely on first-step speed, deceleration and lateral agility.",
    "shooting_guard": "Shooting guards need sustained explosiveness and shoulder stability.",
    "forward": "Forwards need full-body power and contact strength under the basket.",
    "center": "Centers benefit from raw lower-body strength and shoulder stability for contested rebounds.",
}


def generate_plan(
    sport: str,
    position: str,
    goal: str,
    equipment: str,
    beginner_friendly: bool = False,
) -> Dict:
    """
    Generate a structured weekly S&C plan.

    Args:
        sport: "volleyball" or "basketball"
        position: position string (see POSITION_NOTES)
        goal: one of GOAL_FOCUS keys
        equipment: "bodyweight" | "dumbbells" | "full_gym"
        beginner_friendly: Cycle 2 toggle. When True, swaps each exercise's
            coaching note for the LLM-authored beginner rephrasing if one is
            available in coaching_notes_tiered.json.

    Returns:
        A dict with metadata and a list of session dicts.
    """
    sport = sport.lower()
    equipment = equipment.lower()
    goal = goal.lower()

    if sport not in ("volleyball", "basketball"):
        raise ValueError(f"Unsupported sport: {sport}")
    if equipment not in EQUIPMENT_RANK:
        raise ValueError(f"Unsupported equipment: {equipment}")

    global _BEGINNER_FRIENDLY
    _BEGINNER_FRIENDLY = bool(beginner_friendly)
    try:
        # shared `used` set prevents duplicate exercises within lower-body days
        lower_used: set = set()

        sessions = [
            _lower_power_day(sport, equipment, goal, lower_used),
            _upper_day(sport, equipment, goal, set()),
            _lower_strength_day(sport, equipment, goal, lower_used),
            _power_agility_day(sport, equipment, goal, set()),
            _core_day(sport, equipment, goal, set()),
        ]

        # If the goal is vertical jump, add an extra plyometric block to day 1.
        if goal == "vertical_jump":
            u: set = set()
            extra = _pick("plyometric", sport, equipment, 4, u)
            if extra:
                sessions[0]["exercises"].append(
                    _block(extra[-1], 3, "5", "2 min")
                )

        return {
            "sport": sport,
            "position": position,
            "goal": goal,
            "equipment": equipment,
            "beginner_friendly": _BEGINNER_FRIENDLY,
            "focus_summary": GOAL_FOCUS.get(goal, "Balanced sport-specific S&C programme."),
            "position_note": POSITION_NOTES.get(position, ""),
            "sessions": sessions,
        }
    finally:
        _BEGINNER_FRIENDLY = False


if __name__ == "__main__":
    #Manual smoke test
    plan = generate_plan("volleyball", "middle_blocker", "vertical_jump", "full_gym")
    print(json.dumps(plan, indent=2))
