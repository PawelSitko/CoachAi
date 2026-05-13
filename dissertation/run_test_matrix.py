"""
CoachAI functional test matrix.

Runs every combination of (sport, position, goal, equipment) through generate_plan
and writes the results to appendix_a_test_matrix.md and appendix_a_test_matrix.csv.

Run from this folder:
    python3 run_test_matrix.py

What it checks (criteria 1, 2, 3 from the project brief success-criteria table):
  - Criterion 1: every input combination produces a valid plan (no exception, response
    object has the expected shape).
  - Criterion 2: plans are produced for both volleyball AND basketball.
  - Criterion 3: every plan is well-structured — five sessions, each with a name,
    a focus, and at least one exercise block; every block has name, sets, reps, rest.

Output goes into the dissertation Appendix A.
"""

import csv
import os
import sys
import traceback

# Make the backend importable
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
sys.path.insert(0, BACKEND)

from recommender import generate_plan  # noqa: E402


# Input space.  We intentionally cover every combination — total = 2 sports * 4 pos * 5
# goals * 3 equipment = 120 cases.  This is exhaustive for criterion 1 and over-samples
# what's strictly needed; the dissertation cites the headline pass rate.
SPORTS = ["volleyball", "basketball"]
POSITIONS = {
    "volleyball": ["middle_blocker", "outside_hitter", "setter", "libero"],
    "basketball": ["point_guard", "shooting_guard", "forward", "center"],
}
GOALS = ["vertical_jump", "explosive_power", "general_strength", "injury_prevention", "agility"]
EQUIPMENT = ["bodyweight", "dumbbells", "full_gym"]


REQUIRED_PLAN_KEYS = {"sport", "position", "goal", "equipment", "focus_summary",
                      "position_note", "sessions"}
REQUIRED_BLOCK_KEYS = {"name", "category", "sets", "reps", "rest", "notes"}


def validate_plan(plan: dict) -> tuple[bool, list[str]]:
    """Return (passed, reasons) describing whether the plan is well-structured."""
    reasons = []
    missing = REQUIRED_PLAN_KEYS - set(plan.keys())
    if missing:
        reasons.append(f"plan missing keys: {sorted(missing)}")
    sessions = plan.get("sessions", [])
    if len(sessions) != 5:
        reasons.append(f"expected 5 sessions, got {len(sessions)}")
    for i, s in enumerate(sessions):
        if "name" not in s or "focus" not in s:
            reasons.append(f"session {i} missing name/focus")
        blocks = s.get("exercises", [])
        if not blocks:
            reasons.append(f"session {i} '{s.get('name','?')}' has no exercise blocks")
        for j, b in enumerate(blocks):
            missing_b = REQUIRED_BLOCK_KEYS - set(b.keys())
            if missing_b:
                reasons.append(f"session {i} block {j} missing: {sorted(missing_b)}")
    return (len(reasons) == 0), reasons


def main():
    rows = []   # for CSV
    md_lines = []  # for markdown appendix

    md_lines.append("# Appendix A: Functional Test Matrix\n")
    md_lines.append(
        "This appendix reports the result of running every supported input "
        "combination through `generate_plan`. The script in `run_test_matrix.py` "
        "produced this output.\n"
    )

    total = 0
    passed = 0
    by_sport: dict[str, int] = {}
    fail_examples = []

    for sport in SPORTS:
        for pos in POSITIONS[sport]:
            for goal in GOALS:
                for equip in EQUIPMENT:
                    total += 1
                    case = (sport, pos, goal, equip)
                    try:
                        plan = generate_plan(*case)
                        ok, reasons = validate_plan(plan)
                        n_blocks = sum(len(s.get("exercises", []))
                                       for s in plan.get("sessions", []))
                        result = "PASS" if ok else "FAIL"
                        notes = "" if ok else "; ".join(reasons)
                    except Exception as e:
                        ok = False
                        result = "ERROR"
                        n_blocks = 0
                        notes = f"{type(e).__name__}: {e}"
                        traceback.print_exc()
                    if ok:
                        passed += 1
                        by_sport[sport] = by_sport.get(sport, 0) + 1
                    else:
                        fail_examples.append((case, notes))
                    rows.append({
                        "sport": sport, "position": pos, "goal": goal,
                        "equipment": equip, "result": result,
                        "exercise_count": n_blocks, "notes": notes,
                    })

    # --- write CSV ---
    csv_path = os.path.join(HERE, "appendix_a_test_matrix.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sport", "position", "goal", "equipment",
                                          "result", "exercise_count", "notes"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {csv_path}")

    # --- write markdown ---
    md_lines.append("## Headline results\n")
    md_lines.append(f"- Total cases tested: **{total}**")
    md_lines.append(f"- Cases passing structural validation: **{passed} / {total}** "
                    f"({100.0 * passed / total:.1f}%)")
    md_lines.append(f"- Volleyball cases passing: **{by_sport.get('volleyball', 0)}**")
    md_lines.append(f"- Basketball cases passing: **{by_sport.get('basketball', 0)}**")
    md_lines.append(f"- Failures: **{total - passed}**\n")

    if fail_examples:
        md_lines.append("## Failed cases\n")
        md_lines.append("| sport | position | goal | equipment | reason |")
        md_lines.append("|-------|----------|------|-----------|--------|")
        for case, notes in fail_examples:
            md_lines.append(f"| {case[0]} | {case[1]} | {case[2]} | {case[3]} | {notes} |")
        md_lines.append("")
    else:
        md_lines.append("All cases passed structural validation.\n")

    md_lines.append("## Per-case results\n")
    md_lines.append("| sport | position | goal | equipment | result | exercises | notes |")
    md_lines.append("|-------|----------|------|-----------|--------|-----------|-------|")
    for r in rows:
        md_lines.append(
            f"| {r['sport']} | {r['position']} | {r['goal']} | {r['equipment']} "
            f"| {r['result']} | {r['exercise_count']} | {r['notes']} |"
        )

    md_path = os.path.join(HERE, "appendix_a_test_matrix.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"Wrote {md_path}")
    print()
    print(f"Headline: {passed} of {total} input combinations produced a valid, "
          f"well-structured plan ({100.0 * passed / total:.1f}%).")


if __name__ == "__main__":
    main()
