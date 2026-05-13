//CoachAI — frontend logic
//Screens: landing → multi-step form → plan view

//Position data
const POSITIONS = {
    volleyball: [
        ["middle_blocker", "Middle blocker"],
        ["outside_hitter", "Outside hitter"],
        ["setter", "Setter"],
        ["libero", "Libero"],
    ],
    basketball: [
        ["point_guard", "Point guard"],
        ["shooting_guard", "Shooting guard"],
        ["forward", "Forward"],
        ["center", "Center"],
    ],
};

const GOAL_LABELS = {
    vertical_jump: "Increase vertical jump",
    explosive_power: "Build explosive power",
    general_strength: "General strength",
    injury_prevention: "Injury prevention",
    agility: "Improve agility",
};

const EQUIPMENT_LABELS = {
    full_gym: "Full gym",
    dumbbells: "Dumbbells only",
    bodyweight: "Bodyweight only",
};

const STAR_HINTS = ["Poor", "Fair", "Good", "Very good", "Excellent"];

//Element refs
const screens = {
    landing: document.getElementById("screen-landing"),
    form:    document.getElementById("screen-form"),
    plan:    document.getElementById("screen-plan"),
    login:   document.getElementById("screen-login"),
    signup:  document.getElementById("screen-signup"),
    myplans: document.getElementById("screen-myplans"),
};

const sportEl     = document.getElementById("sport");
const positionEl  = document.getElementById("position");
const goalEl      = document.getElementById("goal");
const equipmentEl = document.getElementById("equipment");
const generateBtn = document.getElementById("generate-btn");
const errorEl     = document.getElementById("error-banner");
const backBtn     = document.getElementById("back-btn");

//Screen transitions
function showScreen(name) {
    Object.values(screens).forEach(s => s && s.classList.add("hidden"));
    if (screens[name]) screens[name].classList.remove("hidden");
    // Hide the auth strip on the login/signup screens themselves to avoid clutter
    const strip = document.getElementById("auth-strip");
    if (strip) strip.classList.toggle("hidden", name === "login" || name === "signup");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

document.getElementById("get-started-btn").addEventListener("click", () => showScreen("form"));
backBtn.addEventListener("click", () => showScreen("form"));

//Multi-step form
const TOTAL_STEPS = 3;
let currentStep = 1;

function showStep(n) {
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        document.getElementById(`step-${i}`).classList.toggle("hidden", i !== n);
    }
    document.getElementById("progress-fill").style.width = `${(n / TOTAL_STEPS) * 100}%`;
    document.getElementById("progress-label").textContent = `Step ${n} of ${TOTAL_STEPS}`;
    currentStep = n;

    //Populate summary on step 3
    if (n === 3) populateSummary();
}

document.querySelectorAll(".step-next").forEach(btn => {
    btn.addEventListener("click", () => showStep(parseInt(btn.dataset.next)));
});
document.querySelectorAll(".step-back").forEach(btn => {
    btn.addEventListener("click", () => showStep(parseInt(btn.dataset.back)));
});

//Position dropdown
function populatePositions() {
    const sport = sportEl.value;
    positionEl.innerHTML = "";
    POSITIONS[sport].forEach(([value, label]) => {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        positionEl.appendChild(opt);
    });
}
sportEl.addEventListener("change", populatePositions);
populatePositions();

//Summary (step 3)
function titleCase(s) {
    return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function populateSummary() {
    document.getElementById("sum-sport").textContent = titleCase(sportEl.value);
    document.getElementById("sum-position").textContent =
        POSITIONS[sportEl.value].find(p => p[0] === positionEl.value)?.[1] || positionEl.value;
    document.getElementById("sum-goal").textContent = GOAL_LABELS[goalEl.value] || titleCase(goalEl.value);
    document.getElementById("sum-equipment").textContent = EQUIPMENT_LABELS[equipmentEl.value] || titleCase(equipmentEl.value);
}

// Currently-rendered plan (kept around so the Save flow can submit it).
let currentPlan = null;

// If the currently-rendered plan is a saved plan, this holds its server id.
// null means the plan is brand-new and not yet saved (or the user is anonymous).
// When non-null, toggling a session complete persists progress to the server.
let currentSavedPlanId = null;

async function fetchPlan(beginnerFriendly) {
    const payload = {
        sport:     sportEl.value,
        position:  positionEl.value,
        goal:      goalEl.value,
        equipment: equipmentEl.value,
        beginner_friendly: !!beginnerFriendly,
    };
    const res = await fetch("/api/generate-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Request failed (${res.status})`);
    }
    return await res.json();
}

//Generate plan
generateBtn.addEventListener("click", async () => {
    errorEl.classList.add("hidden");
    generateBtn.disabled = true;
    generateBtn.textContent = "Generating…";

    try {
        const plan = await fetchPlan(false);
        currentPlan = plan;
        currentSavedPlanId = null;  // freshly generated, not yet saved
        renderPlan(plan);
        showScreen("plan");
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("hidden");
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "⚡ Generate plan";
    }
});

//Render plan 
function renderPlan(plan) {
    document.getElementById("plan-title").textContent =
        `Weekly plan — ${titleCase(plan.sport)} (${titleCase(plan.position)})`;
    document.getElementById("plan-summary").textContent = plan.focus_summary;

    const posNote = document.getElementById("plan-position");
    if (plan.position_note) {
        posNote.textContent = plan.position_note;
        posNote.classList.remove("hidden");
    } else {
        posNote.classList.add("hidden");
    }

    //Tracker dots
    const dotsEl = document.getElementById("tracker-dots");
    dotsEl.innerHTML = "";
    plan.sessions.forEach((_, i) => {
        const dot = document.createElement("div");
        dot.className = "tracker-dot";
        dot.textContent = `D${i + 1}`;
        dot.dataset.index = i;
        dotsEl.appendChild(dot);
    });

    //Sessions
    const sessionsEl = document.getElementById("sessions");
    sessionsEl.innerHTML = "";
    plan.sessions.forEach((session, i) => {
        const wrap = document.createElement("div");
        wrap.className = "session";
        wrap.dataset.index = i;

        // Header
        const header = document.createElement("div");
        header.className = "session-header";

        const titleWrap = document.createElement("div");
        titleWrap.innerHTML = `
            <div class="session-title">${session.name}</div>
            <div class="session-focus">Focus: ${titleCase(session.focus)}</div>
        `;

        const completeBtn = document.createElement("button");
        completeBtn.className = "complete-btn";
        completeBtn.textContent = "Mark done";
        completeBtn.addEventListener("click", () => toggleComplete(i, wrap, completeBtn));

        header.appendChild(titleWrap);
        header.appendChild(completeBtn);
        wrap.appendChild(header);

        //Exercises
        session.exercises.forEach(ex => {
            const exDiv = document.createElement("div");
            exDiv.className = "exercise";
            exDiv.innerHTML = `
                <div class="ex-name">${ex.name}</div>
                <div class="ex-meta">
                    <span>${ex.sets} sets</span>
                    <span>${ex.reps} reps</span>
                    <span>Rest: ${ex.rest}</span>
                </div>
                ${ex.notes ? `<div class="ex-notes">${ex.notes}</div>` : ""}
            `;
            wrap.appendChild(exDiv);
        });

        sessionsEl.appendChild(wrap);
    });

    //Reset feedback
    resetFeedback();
}

// Mark session complete 
const completedSessions = new Set();

function toggleComplete(index, card, btn) {
    if (completedSessions.has(index)) {
        completedSessions.delete(index);
        card.classList.remove("completed");
        btn.classList.remove("done");
        btn.textContent = "Mark done";
    } else {
        completedSessions.add(index);
        card.classList.add("completed");
        btn.classList.add("done");
        btn.textContent = "✓ Done";
    }
    // Update tracker dots
    document.querySelectorAll(".tracker-dot").forEach(dot => {
        const i = parseInt(dot.dataset.index);
        dot.classList.toggle("done", completedSessions.has(i));
        dot.textContent = completedSessions.has(i) ? "✓" : `D${i + 1}`;
    });
    // Cycle 2: if this is a saved plan owned by a signed-in user, persist
    // the completion state. Soft-fail on network errors — UI state is already
    // correct, and we'd rather not block tapping a button on a flaky network.
    if (currentSavedPlanId && authState.user) {
        persistProgress();
    }
}

async function persistProgress() {
    try {
        await fetch(`/api/plans/${currentSavedPlanId}/progress`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({
                completed_sessions: Array.from(completedSessions),
            }),
        });
    } catch (e) {
        console.warn("Could not persist progress:", e);
    }
}

// Restore the marked-done state of a saved plan after renderPlan() has rebuilt
// the session cards. Walks the freshly-rendered DOM and reproduces the toggle
// click for each completed index, so the UI matches saved state exactly.
function restoreCompletion(indices) {
    if (!Array.isArray(indices) || indices.length === 0) return;
    indices.forEach((i) => {
        const card = document.querySelector(`.session[data-index="${i}"]`);
        if (!card) return;
        const btn = card.querySelector(".complete-btn");
        if (!btn || completedSessions.has(i)) return;
        // Toggle without re-persisting — we're restoring server state, not changing it.
        completedSessions.add(i);
        card.classList.add("completed");
        btn.classList.add("done");
        btn.textContent = "✓ Done";
        const dot = document.querySelector(`.tracker-dot[data-index="${i}"]`);
        if (dot) {
            dot.classList.add("done");
            dot.textContent = "✓";
        }
    });
}

//Feedback / star ratings
const ratings = { clarity: 0, sport: 0 };

function buildStars(containerId, key) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    for (let v = 1; v <= 5; v++) {
        const star = document.createElement("span");
        star.className = "star";
        star.textContent = "★";
        star.dataset.value = v;
        star.addEventListener("click", () => setRating(key, v, containerId));
        star.addEventListener("mouseenter", () => highlightStars(containerId, v));
        star.addEventListener("mouseleave", () => highlightStars(containerId, ratings[key]));
        container.appendChild(star);
    }
}

function highlightStars(containerId, n) {
    document.querySelectorAll(`#${containerId} .star`).forEach(s => {
        s.classList.toggle("on", parseInt(s.dataset.value) <= n);
    });
}

function setRating(key, value, containerId) {
    ratings[key] = value;
    highlightStars(containerId, value);
    const hint = document.getElementById(`hint-${key}`);
    hint.textContent = `${value}/5 — ${STAR_HINTS[value - 1]}`;
    hint.classList.remove("hidden");
}

function resetFeedback() {
    ratings.clarity = 0;
    ratings.sport = 0;
    buildStars("stars-clarity", "clarity");
    buildStars("stars-sport", "sport");
    document.getElementById("feedback-comment").value = "";
    document.getElementById("feedback-thanks").classList.add("hidden");
    document.getElementById("submit-feedback-btn").classList.remove("hidden");
    document.getElementById("hint-clarity").classList.add("hidden");
    document.getElementById("hint-sport").classList.add("hidden");
    completedSessions.clear();
}

document.getElementById("submit-feedback-btn").addEventListener("click", () => {
    const comment = document.getElementById("feedback-comment").value.trim();
    //Log to console (can be wired to a backend endpoint later)
    console.log("CoachAI feedback:", {
        clarity: ratings.clarity,
        sport_specificity: ratings.sport,
        comment,
        sport: sportEl.value,
        position: positionEl.value,
        goal: goalEl.value,
        equipment: equipmentEl.value,
        sessions_completed: completedSessions.size,
        timestamp: new Date().toISOString(),
    });
    document.getElementById("submit-feedback-btn").classList.add("hidden");
    document.getElementById("feedback-thanks").classList.remove("hidden");
});

// =====================================================================
//  CYCLE 2 — auth, beginner-friendly toggle, save plan, my plans
// =====================================================================

const authState = { user: null };

async function refreshAuthState() {
    try {
        const res = await fetch("/api/auth/me", { credentials: "same-origin" });
        if (!res.ok) throw new Error();
        const data = await res.json();
        authState.user = data.user;
    } catch (_) {
        authState.user = null;
    }
    renderAuthStrip();
}

function renderAuthStrip() {
    const anon = document.getElementById("auth-strip-anon");
    const user = document.getElementById("auth-strip-user");
    if (authState.user) {
        anon.classList.add("hidden");
        user.classList.remove("hidden");
        document.getElementById("auth-username").textContent =
            authState.user.display_name || authState.user.email;
    } else {
        anon.classList.remove("hidden");
        user.classList.add("hidden");
    }
}

// --- Auth strip + screen navigation ---
document.getElementById("auth-login-link").addEventListener("click", () => showScreen("login"));
document.getElementById("auth-signup-link").addEventListener("click", () => showScreen("signup"));
document.getElementById("auth-myplans-link").addEventListener("click", () => loadMyPlans());
document.getElementById("login-to-signup").addEventListener("click", () => showScreen("signup"));
document.getElementById("login-to-landing").addEventListener("click", () => showScreen("landing"));
document.getElementById("signup-to-login").addEventListener("click", () => showScreen("login"));
document.getElementById("signup-to-landing").addEventListener("click", () => showScreen("landing"));
document.getElementById("myplans-back").addEventListener("click", () => showScreen("landing"));

// --- Login ---
document.getElementById("login-submit").addEventListener("click", async () => {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const err = document.getElementById("login-error");
    err.classList.add("hidden");
    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Sign-in failed.");
        authState.user = data.user;
        renderAuthStrip();
        showScreen("landing");
    } catch (e) {
        err.textContent = e.message;
        err.classList.remove("hidden");
    }
});

// --- Signup ---
document.getElementById("signup-submit").addEventListener("click", async () => {
    const email = document.getElementById("signup-email").value.trim();
    const display_name = document.getElementById("signup-name").value.trim();
    const password = document.getElementById("signup-password").value;
    const err = document.getElementById("signup-error");
    err.classList.add("hidden");
    try {
        const res = await fetch("/api/auth/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ email, password, display_name }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Signup failed.");
        authState.user = data.user;
        renderAuthStrip();
        showScreen("landing");
    } catch (e) {
        err.textContent = e.message;
        err.classList.remove("hidden");
    }
});

// --- Logout ---
document.getElementById("auth-logout-btn").addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    authState.user = null;
    renderAuthStrip();
    showScreen("landing");
});

// --- Beginner-friendly toggle on plan view ---
document.getElementById("beginner-toggle").addEventListener("change", async (e) => {
    if (!currentPlan) return;
    try {
        const plan = await fetchPlan(e.target.checked);
        currentPlan = plan;
        renderPlan(plan);
    } catch (err) {
        // Re-render existing plan; the toggle visually persists but data didn't update.
        renderPlan(currentPlan);
    }
});

// --- Save-plan flow ---
const saveBtn      = document.getElementById("save-plan-btn");
const saveModal    = document.getElementById("save-modal");
const saveNameEl   = document.getElementById("save-plan-name");
const saveCancelEl = document.getElementById("save-cancel-btn");
const saveConfirmEl= document.getElementById("save-confirm-btn");
const saveErrorEl  = document.getElementById("save-error");

saveBtn.addEventListener("click", () => {
    if (!currentPlan) return;
    // If the user isn't signed in, route them to the login screen first.
    // After signing in, they land back on the home screen with the same plan
    // still in memory, and a second click will open the save modal.
    if (!authState.user) {
        showScreen("login");
        return;
    }
    const defaultName = `${titleCase(currentPlan.sport)} — ${
        GOAL_LABELS[currentPlan.goal] || titleCase(currentPlan.goal)
    } (${new Date().toLocaleDateString()})`;
    saveNameEl.value = defaultName;
    saveErrorEl.classList.add("hidden");
    saveModal.classList.remove("hidden");
    saveNameEl.focus();
    saveNameEl.select();
});

saveCancelEl.addEventListener("click", () => saveModal.classList.add("hidden"));

saveConfirmEl.addEventListener("click", async () => {
    const name = saveNameEl.value.trim();
    if (!name) {
        saveErrorEl.textContent = "Please give your plan a name.";
        saveErrorEl.classList.remove("hidden");
        return;
    }
    saveConfirmEl.disabled = true;
    saveConfirmEl.textContent = "Saving…";
    try {
        const res = await fetch("/api/save-plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ name, plan: currentPlan }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not save the plan.");
        // The plan is now saved — remember its id so subsequent Mark-done taps
        // persist progress against this record. If the user has already ticked
        // some sessions before saving, push those up immediately.
        currentSavedPlanId = data.id;
        if (completedSessions.size > 0) {
            persistProgress();
        }
        saveModal.classList.add("hidden");
    } catch (e) {
        saveErrorEl.textContent = e.message;
        saveErrorEl.classList.remove("hidden");
    } finally {
        saveConfirmEl.disabled = false;
        saveConfirmEl.textContent = "Save plan";
    }
});

// --- My plans list ---
async function loadMyPlans() {
    showScreen("myplans");
    const listEl = document.getElementById("myplans-list");
    const emptyEl = document.getElementById("myplans-empty");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    try {
        const res = await fetch("/api/my-plans", { credentials: "same-origin" });
        if (!res.ok) throw new Error("Could not load your plans.");
        const data = await res.json();
        if (!data.plans.length) {
            emptyEl.classList.remove("hidden");
            return;
        }
        data.plans.forEach((p) => {
            const card = document.createElement("div");
            card.className = "myplan-card";
            const progress = (typeof p.completed_count === "number")
                ? `${p.completed_count} / 5 sessions done`
                : "";
            card.innerHTML = `
                <div class="myplan-name">${escapeHtml(p.name)}</div>
                <div class="myplan-meta">
                    ${titleCase(p.sport)} · ${titleCase(p.position)} · ${
                        GOAL_LABELS[p.goal] || titleCase(p.goal)
                    } · ${EQUIPMENT_LABELS[p.equipment] || titleCase(p.equipment)}
                </div>
                <div class="myplan-meta">
                    Saved ${new Date(p.created_at).toLocaleString()}${progress ? " · " + progress : ""}
                </div>
            `;
            card.addEventListener("click", () => openSavedPlan(p.id));
            listEl.appendChild(card);
        });
    } catch (e) {
        listEl.innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`;
    }
}

async function openSavedPlan(planId) {
    try {
        const res = await fetch(`/api/plans/${planId}`, { credentials: "same-origin" });
        if (!res.ok) throw new Error("Could not load that plan.");
        const data = await res.json();
        currentPlan = data.plan;
        currentSavedPlanId = data.id;
        // Reflect the saved plan's profile inputs so the form summary stays correct
        if (currentPlan.sport) sportEl.value = currentPlan.sport;
        if (currentPlan.position) {
            populatePositions();
            positionEl.value = currentPlan.position;
        }
        if (currentPlan.goal) goalEl.value = currentPlan.goal;
        if (currentPlan.equipment) equipmentEl.value = currentPlan.equipment;
        document.getElementById("beginner-toggle").checked = !!currentPlan.beginner_friendly;
        renderPlan(currentPlan);
        // Restore which sessions were marked done last time the user opened
        // this plan. renderPlan() resets feedback (which clears
        // completedSessions), so this must run AFTER it.
        restoreCompletion(data.completed_sessions || []);
        renderAuthStrip();
        showScreen("plan");
    } catch (e) {
        alert(e.message);
    }
}

// Tiny HTML-escape for user-controlled text
function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

//Init
buildStars("stars-clarity", "clarity");
buildStars("stars-sport", "sport");
showStep(1);
refreshAuthState();
