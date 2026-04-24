# CoachAI

A mobile-first, multi-sport strength &amp; conditioning recommender for amateur athletes.
Final Year Project &mdash; Pawel Sitko, Goldsmiths University.

## What the software does

CoachAI generates a structured **weekly gym plan** tailored to a user&rsquo;s
**sport, playing position, training goal and available equipment**.
The current prototype supports **volleyball** and **basketball** and uses a
rule-based recommender grounded in published S&amp;C literature.

## Core features implemented

- Single-page mobile-first web UI (HTML5, CSS3, vanilla JS)
- Profile form: sport, position (auto-updates per sport), goal, equipment
- Flask + Python REST API (`POST /api/generate-plan`)
- Rule-based recommender engine with a curated 40+ exercise database
- Equipment-aware filtering (full gym &gt; dumbbells &gt; bodyweight)
- Sport- and position-aware coaching notes
- 5-day weekly plan output: lower power, upper, lower strength, power/agility, core
- Goal-driven adjustments (e.g. extra plyometric block when the goal is vertical jump)

## Project structure

```
coachai/
  backend/
    app.py            # Flask app + API endpoint
    recommender.py    # Rule-based plan generator
    exercises.json    # Curated exercise database
    requirements.txt
  frontend/
    index.html
    styles.css
    app.js
  README.md
```

## Setup &amp; run instructions

Requires **Python 3.9+**.

```bash
#1. Clone the repo
git clone <repo-url>
cd coachai

# 2. (Recommended) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Run the server
cd backend
python app.py
```

Then open **http://localhost:5000** in your browser
(or on your phone if it&rsquo;s on the same Wi-Fi: `http://<your-laptop-ip>:5000`).

## How to use

1. Pick your **sport** &mdash; the position dropdown updates automatically.
2. Pick your **position**, **goal**, and **available equipment**.
3. Click **Generate plan**.
4. Scroll through your weekly sessions. Use **Edit profile** to regenerate.

## Sample inputs to try

| Sport      | Position        | Goal             | Equipment   |
|------------|-----------------|------------------|-------------|
| Volleyball | Middle blocker  | Vertical jump    | Full gym    |
| Basketball | Point guard     | Agility          | Bodyweight  |
| Volleyball | Setter          | Injury prevention| Dumbbells   |

## Dependencies

- `Flask==3.0.3` (only runtime dep)
- No frontend build step. No database. No API keys required.

## Known limitations / not implemented

- No user accounts, login, or persistent storage (out of scope per design doc)
- No nutrition advice, no wearable integrations
- LLM &ldquo;hybrid&rdquo; layer described in the design is not implemented in this prototype &mdash;
  the engine is purely rule-based for reliability and offline demoability
- Only volleyball and basketball are supported (extensible via `exercises.json` tags)
- The generated plan is the same on every call for the same inputs (deterministic by design,
  so users can trust the output rather than chasing variation)

## API reference

`POST /api/generate-plan`

Request body:
```json
{
  "sport": "volleyball",
  "position": "middle_blocker",
  "goal": "vertical_jump",
  "equipment": "full_gym"
}
```

Response: a JSON object with `sport`, `position`, `goal`, `equipment`,
`focus_summary`, `position_note`, and a `sessions` array. Each session
contains a list of exercises with `sets`, `reps`, `rest`, and coaching `notes`.
