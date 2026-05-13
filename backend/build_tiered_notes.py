"""
Cycle 2 — dev-time LLM rephrasing builder.

Reads exercises.json. For each exercise, asks Google Gemini (free tier) to
rephrase the existing coaching note into a beginner-friendly version. Writes
the result to coaching_notes_tiered.json, which the recommender consults at
runtime when beginner_friendly=True.

Run this script ONCE during development:

    export GEMINI_API_KEY="your-key-here"
    python3 build_tiered_notes.py

The runtime application never calls Gemini directly — it only reads the static
JSON cache. This preserves NFR3 (determinism), NFR5 (offline demoability), and
keeps the system free to operate.

Safety note: the LLM is constrained to rephrasing the EXISTING coaching note in
plainer language. It must NOT introduce new exercises, change volumes (sets,
reps, rest), or invent technique cues. The system prompt enforces this.
"""

from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXERCISES_PATH = os.path.join(HERE, "exercises.json")
OUTPUT_PATH = os.path.join(HERE, "coaching_notes_tiered.json")

SYSTEM_PROMPT = (
    "You are an assistant rephrasing strength-and-conditioning coaching notes "
    "for amateur athletes who are new to the gym. Your job is to take an "
    "existing one-line coaching cue and rewrite it so a beginner can follow it "
    "confidently. STRICT RULES:\n"
    "  1. DO NOT introduce new exercises or replace the exercise being described.\n"
    "  2. DO NOT change or add sets, reps, weights, rest intervals or any "
    "numbers. Sets and reps are NOT in your scope.\n"
    "  3. DO NOT invent technique cues that are not present in or directly "
    "implied by the original note. If the original is vague, keep your "
    "version equally vague rather than guessing.\n"
    "  4. KEEP the rephrasing under 40 words.\n"
    "  5. Use plain everyday language — assume the reader has never lifted "
    "weights before. Spell out gym jargon (e.g. \"hinge\" → \"bend at the hips\").\n"
    "  6. Output ONLY the rephrased coaching note — no preamble, no quotation "
    "marks, no explanations.\n"
)


def pick_model(genai) -> "genai.GenerativeModel":
    """Find a working Flash-tier Gemini model for this account.

    Google rotates model names periodically, so we ask the API which models the
    current key has access to and pick a small, fast one. Preferring 'flash'
    variants because they're cheap and more than capable enough for the
    rephrasing task; falling through to anything that supports generateContent
    if no flash model is offered.
    """
    candidates = []
    for m in genai.list_models():
        methods = getattr(m, "supported_generation_methods", []) or []
        if "generateContent" not in methods:
            continue
        # Strip the "models/" prefix the API returns
        name = m.name.split("/")[-1]
        candidates.append(name)

    if not candidates:
        raise RuntimeError(
            "No models on this API key support generateContent. "
            "Check your Gemini key is valid and the API is enabled."
        )

    # Preference order prioritises models with generous DAILY quotas on the
    # free tier, since the rephrasing batch is small (~45 calls) and we want
    # to finish in one run rather than wait 24h for a quota reset.
    #   - gemini-2.5-flash-lite: 1000 RPD on free tier (best for batch jobs)
    #   - gemini-2.0-flash:       200 RPD
    #   - gemini-2.5-flash:        20 RPD (will exhaust before this batch finishes)
    #   - gemini-1.5-flash-*:    1500 RPD historically (often deprecated)
    preferences = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-lite-latest",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-002",
        "gemini-2.5-flash",  # last resort — only 20 RPD free
    ]
    for pref in preferences:
        if pref in candidates:
            print(f"Using model: {pref}")
            return genai.GenerativeModel(pref)

    # No preferred flash model — fall back to any flash variant we found
    for c in candidates:
        if "flash" in c:
            print(f"Using model: {c} (fallback)")
            return genai.GenerativeModel(c)

    # Last resort — any model at all
    print(f"Using model: {candidates[0]} (final fallback)")
    return genai.GenerativeModel(candidates[0])


def _extract_retry_delay(err: Exception) -> float:
    """Pull the retry_delay seconds out of a 429 ResourceExhausted error.

    The google-generativeai client surfaces the proto's retry_delay, but the
    field name and the ways to access it vary by version, so we just grep the
    string representation. Returns a sensible fallback if no delay is found.
    """
    text = str(err)
    import re
    # Look for: retry_delay { seconds: <N> } OR "retry in <N>s"
    m = re.search(r"retry_delay\s*\{[^}]*?seconds:\s*(\d+)", text)
    if m:
        return float(m.group(1)) + 1.0  # +1s margin
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", text)
    if m:
        return float(m.group(1)) + 1.0
    return 15.0  # safe default for free-tier 5-RPM quota


# A rephrasing shorter than this many words is treated as a truncated/failed
# generation. These show up when a content filter cuts the response off, when
# response.text returns only the first part of a multi-part candidate, or when
# the model decides to stop early. We re-generate any that fall below.
MIN_WORDS = 8


def _extract_full_text(response) -> str:
    """Pull the full response text, joining multi-part candidates.

    response.text in google-generativeai sometimes returns only the first part
    when the model produced multiple. Walking candidates[0].content.parts is
    more reliable.
    """
    # Fast path
    try:
        t = response.text
        if t:
            joined_via_parts = ""
            try:
                parts = response.candidates[0].content.parts
                joined_via_parts = "".join(
                    getattr(p, "text", "") or "" for p in parts
                ).strip()
            except Exception:
                pass
            # Prefer the longer of the two — the parts join is more reliable
            # for multi-part responses.
            return joined_via_parts if len(joined_via_parts) > len(t) else t
    except Exception:
        pass
    # Slow path: parts only
    try:
        parts = response.candidates[0].content.parts
        return "".join(getattr(p, "text", "") or "" for p in parts).strip()
    except Exception:
        return ""


def call_gemini(model, exercise_name: str, original_note: str, max_retries: int = 4) -> str:
    """Call Gemini once and return the rephrased note.

    Automatically retries on (a) 429 quota errors, sleeping for the delay the
    API recommends, and (b) suspiciously short outputs that look truncated.
    Raises on persistent failure or any non-recoverable error.
    """
    # Slightly assertive prompt to make truncation less likely. The bracketed
    # "Output the rephrased note as ONE complete sentence" steers the model
    # away from stopping mid-clause.
    user = (
        f"Exercise: {exercise_name}\n"
        f"Original coaching note: {original_note}\n\n"
        f"Rewrite the original coaching note as ONE complete beginner-friendly "
        f"sentence (or two short sentences). Under 40 words. Plain language. "
        f"Output the rephrased coaching note now:"
    )
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                SYSTEM_PROMPT + "\n\n" + user,
                generation_config={
                    "temperature": 0.4,        # slight bump to discourage early stops
                    "max_output_tokens": 200,  # generous; rephrasings are short
                },
            )
            text = _extract_full_text(response).strip()
            # Strip surrounding quotes if the model added them despite instructions.
            if text and (
                (text.startswith('"') and text.endswith('"')) or
                (text.startswith("'") and text.endswith("'"))
            ):
                text = text[1:-1].strip()

            # Quality check: too short to be a real rephrasing → retry once more
            # with a slightly different shape, up to max_retries.
            if text and len(text.split()) < MIN_WORDS and attempt < max_retries:
                print(f"    short response ({len(text.split())} words: {text!r}); "
                      f"retrying (attempt {attempt + 1}/{max_retries})")
                time.sleep(2)
                continue

            return text
        except Exception as e:
            last_err = e
            # Retry on quota / rate-limit errors; others bubble up.
            if "ResourceExhausted" in type(e).__name__ or "429" in str(e):
                if attempt < max_retries:
                    delay = _extract_retry_delay(e)
                    print(f"    rate-limited; sleeping {delay:.0f}s before retry "
                          f"(attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
            raise
    raise last_err  # type: ignore[misc]


def _purge_truncated_cache_entries(cache: dict) -> int:
    """Remove cache entries that look truncated so they get regenerated.

    Returns the number purged. We treat anything under MIN_WORDS as suspect.
    """
    purged = 0
    for eid in list(cache.keys()):
        beginner = (cache.get(eid) or {}).get("beginner", "")
        if beginner and len(beginner.split()) < MIN_WORDS:
            del cache[eid]
            purged += 1
    return purged


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "ERROR: GEMINI_API_KEY environment variable is not set.\n"
            "Set it with:  export GEMINI_API_KEY=\"your-key\"  and re-run.",
            file=sys.stderr,
        )
        return 1

    try:
        import google.generativeai as genai
    except ImportError:
        print(
            "ERROR: google-generativeai is not installed.\n"
            "Install with:  pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    genai.configure(api_key=api_key)
    try:
        model = pick_model(genai)
    except Exception as e:
        print(f"ERROR: Could not select a Gemini model: {e}", file=sys.stderr)
        return 1

    with open(EXERCISES_PATH, "r") as f:
        exercises = json.load(f)["exercises"]

    # Resume if a partial cache exists, so we can re-run after a transient failure.
    cache: dict[str, dict[str, str]] = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r") as f:
            cache = json.load(f)
        print(f"Loaded existing cache with {len(cache)} entries.")
        # Purge previously-truncated entries (e.g. "Take a", "Step one foot")
        # so they get regenerated this run.
        purged = _purge_truncated_cache_entries(cache)
        if purged:
            print(f"Purged {purged} truncated entries; they will be regenerated.")
            with open(OUTPUT_PATH, "w") as f:
                json.dump(cache, f, indent=2)

    todo = [ex for ex in exercises if ex["id"] not in cache]
    print(f"Total exercises: {len(exercises)}")
    print(f"Already cached:  {len(exercises) - len(todo)}")
    print(f"To author:       {len(todo)}\n")

    successes = 0
    failures: list[tuple[str, str]] = []  # (exercise_id, error_message)

    for i, ex in enumerate(todo, start=1):
        eid = ex["id"]
        name = ex["name"]
        original = ex.get("notes", "")
        if not original:
            print(f"[{i}/{len(todo)}] {eid}: skipping (no original note)")
            cache[eid] = {"beginner": ""}
            continue

        try:
            rephrased = call_gemini(model, name, original)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print(f"[{i}/{len(todo)}] {eid}: ERROR — {msg}")
            failures.append((eid, msg))
            continue

        cache[eid] = {"beginner": rephrased}
        successes += 1
        print(f"[{i}/{len(todo)}] {eid}:")
        print(f"    original : {original}")
        print(f"    beginner : {rephrased}\n")

        # Write cache after every entry so a crash doesn't lose work.
        with open(OUTPUT_PATH, "w") as f:
            json.dump(cache, f, indent=2)

        # Pace at ~5 RPM for safety across all free-tier models. flash-lite
        # actually allows 15 RPM, but a slower pace costs us nothing on this
        # 45-exercise batch and avoids any per-minute hiccup.
        time.sleep(5)

    print(f"\nDone. Cache written to {OUTPUT_PATH}")
    print(f"Successes this run:  {successes}")
    print(f"Failures this run:   {len(failures)}")
    print(f"Total cache entries: {len(cache)}")
    if failures:
        print("\nFAILURES:")
        for eid, msg in failures[:5]:
            print(f"  {eid}: {msg}")
        if len(failures) > 5:
            print(f"  ... and {len(failures) - 5} more")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
