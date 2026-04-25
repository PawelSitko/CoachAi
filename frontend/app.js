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
};

const sportEl     = document.getElementById("sport");
const positionEl  = document.getElementById("position");
const goalEl      = document.getElementById("goal");
const equipmentEl = document.getElementById("equipment");
const generateBtn = document.getElementById("generate-btn");
const errorEl     = document.getElementById("error-banner");
const backBtn     = document.getElementById("back-btn");
const printBtn    = document.getElementById("print-btn");

//Screen transitions
function showScreen(name) {
    Object.values(screens).forEach(s => s.classList.add("hidden"));
    screens[name].classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

document.getElementById("get-started-btn").addEventListener("click", () => showScreen("form"));
backBtn.addEventListener("click", () => showScreen("form"));
printBtn.addEventListener("click", () => window.print());

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

//Generate plan
generateBtn.addEventListener("click", async () => {
    errorEl.classList.add("hidden");
    generateBtn.disabled = true;
    generateBtn.textContent = "Generating…";

    const payload = {
        sport:     sportEl.value,
        position:  positionEl.value,
        goal:      goalEl.value,
        equipment: equipmentEl.value,
    };

    try {
        const res = await fetch("/api/generate-plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `Request failed (${res.status})`);
        }
        const plan = await res.json();
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

//Init
buildStars("stars-clarity", "clarity");
buildStars("stars-sport", "sport");
showStep(1);
