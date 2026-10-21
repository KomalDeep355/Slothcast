"use strict";

const API_BASE = "http://127.0.0.1:8000";
const STORAGE_KEY = "slothcast-prototype-v2";
const FOCUS_DURATION = 5 * 60;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body?.detail
      ? JSON.stringify(body.detail)
      : `API request failed: ${response.status}`;
    throw new Error(message);
  }

  return body;
}

const barrierInfo = {
  overwhelmed: {
    title: "Make the task smaller",
    tag: "TINY-STEP STRATEGY",
    explanation:
      "A task can feel impossible when it exists as one giant thing in your head. We're shrinking the scope so you only have to deal with the next visible action.",
    evidence:
      "Research connection: breaking goals into concrete actions is a practical planning technique. This recommendation is a starting hypothesis, not a guaranteed result.",
    strategy: "tiny_step"
  },

  uncertain: {
    title: "Find the first visible action",
    tag: "CLARITY STRATEGY",
    explanation:
      "You don't have to know how to finish the entire task. Let's identify one thing you can open, read, list, or inspect.",
    evidence:
      "Research connection: specific action plans can help bridge the gap between intentions and behavior.",
    strategy: "if_then"
  },

  perfectionism: {
    title: "Give yourself permission to be rough",
    tag: "IMPERFECT-START STRATEGY",
    explanation:
      "The first attempt is allowed to be incomplete. Your only job is to create something you can improve later, not something perfect right now.",
    evidence:
      "Practical self-help approach: reduce the pressure attached to the first attempt. This is not a diagnostic assessment.",
    strategy: "imperfect_start"
  },

  boring: {
    title: "Make the task easier to enter",
    tag: "LOW-FRICTION STRATEGY",
    explanation:
      "You don't need to manufacture enthusiasm. Give the task a tiny beginning, a clear stopping point, and a short time limit.",
    evidence:
      "Research connection: concrete plans can make an intended action easier to initiate. We'll keep the first attempt deliberately small.",
    strategy: "tiny_step"
  },

  distracted: {
    title: "Make distractions harder to reach",
    tag: "DISTRACTION-RESET STRATEGY",
    explanation:
      "Instead of relying entirely on willpower, change one thing around you. Close one tab, silence one notification, or put your phone out of reach.",
    evidence:
      "Practical strategy: change the immediate environment and define a short action window. Its usefulness will vary by person and situation.",
    strategy: "distraction_reset"
  },

  low_energy: {
    title: "Match the task to your energy",
    tag: "GENTLE-START STRATEGY",
    explanation:
      "Low energy doesn't mean you have to force a full work session. Choose a smaller version of the task, or allow yourself to rest if you need it.",
    evidence:
      "Practical self-management: adjust the size of the action to the resources you have today. Rest is a valid choice.",
    strategy: "energy_match"
  }
};

const strategyLabels = {
  tiny_step: "Breaking it into a tiny step",
  if_then: "An if–then plan",
  imperfect_start: "An imperfect first draft",
  distraction_reset: "Removing distractions",
  energy_match: "Matching the task to my energy",
  other: "Something else"
};

const outcomeLabels = {
  yes: "I started",
  partial: "A little",
  no: "Not this time"
};

const energyDescriptions = {
  1: "Running on fumes",
  2: "Taking it gently",
  3: "A little low-key",
  4: "Feeling pretty good",
  5: "Full battery"
};

let state = loadState();
let currentPlan = null;
let lastTimerDuration = FOCUS_DURATION;
let remainingSeconds = FOCUS_DURATION;
let timerRunning = false;
let timerInterval = null;
let toastTimeout = null;
let voiceEnabled = false;
let recognition = null;
let recognitionActive = false;

function emptyState() {
  return {
    wins: [],
    tasks: [],
    sessions: [],
    selectedBarrier: null
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return emptyState();
    }

    const parsed = JSON.parse(raw);

    return {
      wins: Array.isArray(parsed.wins) ? parsed.wins : [],
      tasks: Array.isArray(parsed.tasks) ? parsed.tasks : [],
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : [],
      selectedBarrier: parsed.selectedBarrier || null
    };
  } catch (error) {
    console.warn("Could not read Slothcast browser data.", error);
    return emptyState();
  }
}

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch (error) {
    console.warn("Could not save Slothcast browser data.", error);
    showToast("Your browser couldn't save this change. Check storage settings.");
    return false;
  }
}

function makeId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function parseLocalDate(dateString) {
  if (!dateString || !/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
    return null;
  }

  const [year, month, day] = dateString.split("-").map(Number);
  const date = new Date(year, month - 1, day);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }

  date.setHours(0, 0, 0, 0);
  return date;
}

function daysUntil(dateString) {
  const deadline = parseLocalDate(dateString);

  if (!deadline) {
    return null;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return Math.round((deadline.getTime() - today.getTime()) / 86400000);
}

function formatDate(dateString) {
  const date = parseLocalDate(dateString);

  if (!date) {
    return "No date set";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function showToast(message) {
  const toast = $("#toast");

  if (!toast) return;

  toast.textContent = message;
  toast.classList.add("visible");

  clearTimeout(toastTimeout);

  toastTimeout = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2800);
}

function scrollToElement(selector) {
  const element = $(selector);

  if (element) {
    element.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start"
    });
  }
}

function setText(selector, text) {
  const element = $(selector);

  if (element) {
    element.textContent = text;
  }
}

function updateDate() {
  const today = new Date();

  setText(
    "#today",
    today.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric"
    }).toUpperCase()
  );

  setText("#year", String(today.getFullYear()));
}

function updateEnergyLabel() {
  const slider = $("#energy");
  const label = $("#energyText");

  if (!slider || !label) return;

  label.textContent = energyDescriptions[slider.value] || "A little low-key";
}

function selectBarrier(barrier, shouldSave = true) {
  if (!barrierInfo[barrier]) return;

  state.selectedBarrier = barrier;

  $$(".barrier-card").forEach((button) => {
    const selected = button.dataset.barrier === barrier;
    button.setAttribute("aria-pressed", String(selected));
  });

  if (shouldSave) {
    saveState();
  }

  const info = barrierInfo[barrier];

  showToast(`Your check-in: ${info.title.toLowerCase()}.`);
}

function setupBarrierCheckin() {
  $$(".barrier-card").forEach((button) => {
    button.addEventListener("click", () => {
      selectBarrier(button.dataset.barrier);
    });
  });

  if (state.selectedBarrier && barrierInfo[state.selectedBarrier]) {
    $$(".barrier-card").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.barrier === state.selectedBarrier)
      );
    });
  }
}

function makeFirstStep(task, barrier, energy, minutes) {
  const normalized = task.trim();
  const shortTask = normalized.length > 150
    ? `${normalized.slice(0, 147)}...`
    : normalized;

  const steps = {
    overwhelmed:
      `Write down the three smallest pieces of "${shortTask}". Circle just one. You only need to begin with that piece.`,

    uncertain:
      `Open the document, website, or materials for "${shortTask}". Write down what you already know and one question you need to answer next.`,

    perfectionism:
      `Create a deliberately rough first attempt at "${shortTask}". Write three imperfect bullet points or a placeholder. Editing comes later.`,

    boring:
      `Set up everything needed for "${shortTask}". Do one small, visible part, then decide whether you want another short round.`,

    distracted:
      `Prepare to work on "${shortTask}": close one distracting tab, silence one notification, and spend your first few minutes on a single action.`,

    low_energy:
      `Choose the easiest useful part of "${shortTask}". Gather the materials or complete one tiny piece, then check whether you need a break.`
  };

  let step = steps[barrier] || steps.overwhelmed;

  if (energy <= 2 && barrier !== "low_energy") {
    step += " Keep the scope especially small today.";
  }

  if (minutes <= 2) {
    step += " If that feels too much, just open the relevant file or materials.";
  }

  return step;
}

function makePlan({ task, barrier, energy, minutes, cue }) {
  const info = barrierInfo[barrier] || barrierInfo.overwhelmed;
  const taskText = task.trim();

  if (!taskText) {
    showToast("Add a task first. It can be messy and incomplete.");
    return null;
  }

  const startCue = cue.trim() || "I finish this check-in";
  const firstStep = makeFirstStep(taskText, barrier, energy, minutes);

  return {
    id: makeId(),
    task: taskText,
    barrier,
    energy,
    minutes,
    cue: startCue,
    firstStep,
    strategy: info.strategy,
    createdAt: new Date().toISOString(),
    started: false
  };
}

function renderPlan(plan) {
  currentPlan = plan;

  $("#emptyResult").classList.add("hidden");
  $("#planOutput").classList.remove("hidden");

  setText("#strategyTag", barrierInfo[plan.barrier].tag);
  setText("#resultTask", plan.task);
  setText("#resultReason", barrierInfo[plan.barrier].explanation);
  setText("#resultStep", plan.firstStep);
  setText("#resultTime", `TRY FOR ${plan.minutes} MINUTE${plan.minutes === 1 ? "" : "S"} · STOPPING IS ALLOWED`);

  setText(
    "#ifThenPlan",
    `If ${plan.cue.toLowerCase()}, then I'll work on the first tiny step for ${plan.minutes} minute${plan.minutes === 1 ? "" : "s"}.`
  );

  setText("#evidenceNote", barrierInfo[plan.barrier].evidence);

  const startedButton = $("#markStarted");
  startedButton.textContent = "I already started this step ✓";
  startedButton.disabled = false;

  $("#planResult").scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth",
    block: "nearest"
  });
}

function handleTaskForm(event) {
  event.preventDefault();

  const task = $("#taskInput").value.trim();

  if (!task) {
    showToast("Tell me the task you're thinking about.");
    $("#taskInput").focus();
    return;
  }

  const barrier = state.selectedBarrier || "overwhelmed";
  const energy = Number($("#energy").value);
  const minutes = Number($("#taskMinutes").value);
  const cue = $("#ifCue").value.trim();

  const plan = makePlan({
    task,
    barrier,
    energy,
    minutes,
    cue
  });

  if (!plan) return;

  const deadline = $("#taskDeadline").value;

  if (deadline) {
    plan.deadline = deadline;
  }

  state.sessions.push({
    id: makeId(),
    planId: plan.id,
    barrier: plan.barrier,
    strategy: plan.strategy,
    createdAt: plan.createdAt,
    started: false,
    completed: false
  });

  state.sessions = state.sessions.slice(-200);

  saveState();
  renderPlan(plan);
  renderPatternSummary();

  showToast("Your tiny move is ready. No need to do the whole thing.");
}

function getApiTaskDetails() {
  const task = $("#taskInput").value.trim();
  const plannedMinutes = Number($("#forecastMinutes").value);
  const deadline = $("#taskDeadline").value;
  const deadlineDays = deadline ? daysUntil(deadline) : 3;

  if (!task) {
    throw new Error("Tell me the task you're thinking about.");
  }
  if (deadlineDays === null || deadlineDays < 0 || deadlineDays > 60) {
    throw new Error("Choose a deadline from today through the next 60 days.");
  }

  return {
    task,
    planned_minutes: plannedMinutes,
    days_to_deadline: deadlineDays,
    energy: Number($("#energy").value),
    date: localDateString()
  };
}

async function handleForecastRequest() {
  const resultElement = $("#forecastResult");
  resultElement.textContent = "Generating your forecast...";

  try {
    const details = getApiTaskDetails();
    const result = await apiRequest("/api/forecast", {
      method: "POST",
      body: JSON.stringify({
        ...details,
        model: "auto",
        use_tabpfn: false,
        use_llm: false,
        use_demo: false
      })
    });
    const risk = typeof result.risk === "number"
      ? `${(result.risk * 100).toFixed(1)}%`
      : "Not available yet";

    resultElement.textContent =
      `Risk: ${risk}\n` +
      `Status: ${result.label || "Unknown"}\n` +
      `First step: ${result.plan?.first_step || "No plan available"}\n` +
      `Data: ${result.data_mode || "personal_history"}`;
  } catch (error) {
    resultElement.textContent = `Could not generate forecast: ${error.message}`;
  }
}

async function handleSaveCheckin() {
  const resultElement = $("#checkinApiResult");
  resultElement.textContent = "Saving your check-in...";

  try {
    const details = getApiTaskDetails();
    const result = await apiRequest("/api/checkins", {
      method: "POST",
      body: JSON.stringify(details)
    });

    if (!result?.ok) {
      throw new Error("The API did not confirm that the check-in was saved.");
    }
    resultElement.textContent = result.message || "Check-in saved.";
  } catch (error) {
    resultElement.textContent = `Could not save check-in: ${error.message}`;
  }
}

async function handleOutcomeForm(event) {
  event.preventDefault();
  const resultElement = $("#outcomeApiResult");
  const date = $("#outcomeDate").value;

  if (!parseLocalDate(date)) {
    resultElement.textContent = "Choose a valid check-in date.";
    return;
  }

  resultElement.textContent = "Saving your outcome...";
  try {
    const result = await apiRequest("/api/outcome", {
      method: "POST",
      body: JSON.stringify({
        date,
        completed: Number($("#outcomeCompleted").value)
      })
    });

    if (!result?.ok) {
      throw new Error("The API did not confirm that the outcome was saved.");
    }
    resultElement.textContent = result.message || "Outcome saved.";
  } catch (error) {
    resultElement.textContent = `Could not save outcome: ${error.message}`;
  }
}

async function handleHistoryRequest() {
  const resultElement = $("#historyResult");
  resultElement.replaceChildren();
  const status = document.createElement("p");
  status.className = "api-message";
  status.textContent = "Loading your history...";
  resultElement.append(status);

  try {
    const history = await apiRequest("/api/history");
    resultElement.replaceChildren();

    const summary = document.createElement("p");
    summary.className = "api-message";
    summary.textContent = `${history.count ?? 0} labelled check-in(s).`;
    resultElement.append(summary);

    const items = Array.isArray(history.items) ? history.items : [];
    if (items.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No labelled history is available yet.";
      resultElement.append(empty);
      return;
    }

    const list = document.createElement("ul");
    list.className = "history-list";
    items.forEach((item) => {
      const entry = document.createElement("li");
      const outcome = item.y_slip === 0
        ? "completed"
        : item.y_slip === 1
          ? "not completed"
          : "outcome unknown";
      entry.textContent = `${item.date || "Undated"} — ${item.planned_task || "Task"} — ${outcome}`;
      list.append(entry);
    });
    resultElement.append(list);
  } catch (error) {
    resultElement.replaceChildren();
    const message = document.createElement("p");
    message.className = "api-message";
    message.textContent = `Could not load history: ${error.message}`;
    resultElement.append(message);
  }
}

function handleSampleTask() {
  $("#taskInput").value = "Start my machine learning project report";
  $("#taskMinutes").value = "5";
  $("#energy").value = "3";
  $("#ifCue").value = "I sit down with my notebook";

  updateEnergyLabel();
  selectBarrier("overwhelmed");
  scrollToElement("#planner");
  showToast("Example loaded. Change anything to make it yours.");
}

function tryAnotherStrategy() {
  if (!currentPlan) {
    showToast("Add a task first and we'll make a plan.");
    return;
  }

  const order = [
    "overwhelmed",
    "uncertain",
    "perfectionism",
    "boring",
    "distracted",
    "low_energy"
  ];

  const currentIndex = order.indexOf(currentPlan.barrier);
  const nextBarrier = order[(currentIndex + 1) % order.length];

  selectBarrier(nextBarrier);

  const updated = makePlan({
    task: currentPlan.task,
    barrier: nextBarrier,
    energy: currentPlan.energy,
    minutes: currentPlan.minutes,
    cue: currentPlan.cue
  });

  if (!updated) return;

  updated.deadline = currentPlan.deadline;
  renderPlan(updated);
  showToast("Here's another approach. Keep the one that feels useful.");
}

function markCurrentStepStarted() {
  if (!currentPlan) {
    showToast("Create a tiny-step plan first.");
    return;
  }

  currentPlan.started = true;

  const session = [...state.sessions]
    .reverse()
    .find((item) => item.planId === currentPlan.id);

  if (session) {
    session.started = true;
    session.startedAt = new Date().toISOString();
  }

  saveState();

  $("#markStarted").textContent = "Start recorded ✓";
  $("#markStarted").disabled = true;

  showToast("That counts. You made a start.");
  speakIfEnabled("You made a start. Nice work.");
}

function updateTimerDisplay() {
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;

  setText(
    "#timer",
    `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  );

  const progress = lastTimerDuration > 0
    ? (lastTimerDuration - remainingSeconds) / lastTimerDuration
    : 0;

  const degrees = Math.min(1, Math.max(0, progress)) * 360;
  $("#timerRing").style.background =
    `conic-gradient(var(--green) ${degrees}deg, #e3d5c4 ${degrees}deg)`;

  if (timerRunning) {
    setText("#timerStatus", "One little step at a time");
  } else if (remainingSeconds === 0) {
    setText("#timerStatus", "You showed up ♡");
  } else if (remainingSeconds === lastTimerDuration) {
    setText("#timerStatus", "Ready when you are");
  } else {
    setText("#timerStatus", "Paused. Take your time.");
  }

  setText("#timerToggle", timerRunning ? "Pause timer" : remainingSeconds === 0 ? "Start again" : remainingSeconds < lastTimerDuration ? "Resume focus" : "Start focus");
}

function stopTimer() {
  timerRunning = false;

  if (timerInterval !== null) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  updateTimerDisplay();
}

function finishTimer() {
  stopTimer();
  remainingSeconds = 0;
  updateTimerDisplay();

  showToast("Five minutes done. You showed up for yourself.");
  speakIfEnabled("Your five minutes are done. You showed up for yourself.");

  if (currentPlan) {
    const session = [...state.sessions]
      .reverse()
      .find((item) => item.planId === currentPlan.id);

    if (session) {
      session.focusCompleted = true;
      session.focusCompletedAt = new Date().toISOString();
      saveState();
    }
  }

  const winNote = currentPlan
    ? `Spent five minutes starting: ${currentPlan.task}`
    : "Spent five minutes showing up for a task";

  addWin({
    note: winNote,
    strategy: currentPlan ? currentPlan.strategy : "tiny_step",
    outcome: "yes",
    source: "timer"
  });
}

function startTimer() {
  if (timerRunning) return;

  if (remainingSeconds <= 0) {
    remainingSeconds = lastTimerDuration;
  }

  timerRunning = true;
  updateTimerDisplay();

  timerInterval = setInterval(() => {
    if (remainingSeconds > 0) {
      remainingSeconds -= 1;
      updateTimerDisplay();
    }

    if (remainingSeconds <= 0) {
      finishTimer();
    }
  }, 1000);
}

function toggleTimer() {
  if (timerRunning) {
    stopTimer();
  } else {
    startTimer();
  }
}

function resetTimer() {
  stopTimer();
  remainingSeconds = lastTimerDuration;
  updateTimerDisplay();
  showToast("Timer reset. A fresh start is always allowed.");
}

function setupTimer() {
  updateTimerDisplay();

  $("#timerToggle").addEventListener("click", toggleTimer);
  $("#timerReset").addEventListener("click", resetTimer);

  $("#startFocus").addEventListener("click", () => {
    stopTimer();

    lastTimerDuration = FOCUS_DURATION;
    remainingSeconds = FOCUS_DURATION;

    updateTimerDisplay();
    scrollToElement("#focus");
    startTimer();
  });
}

function classifyDeadline(task) {
  const days = daysUntil(task.deadline);

  if (days === null) {
    return {
      label: "DATE NEEDED",
      className: "status-plan",
      message: "Add a valid deadline to plan this task."
    };
  }

  if (days < 0) {
    return {
      label: "PAST DUE",
      className: "status-late",
      message: `The deadline passed ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago. Consider revising the plan.`
    };
  }

  const availableMinutes = days * 24 * 60;

  if (days === 0 || (days <= 1 && task.effortMinutes >= availableMinutes)) {
    return {
      label: "NEEDS ATTENTION",
      className: "status-soon",
      message: "The deadline is close relative to the estimated work remaining."
    };
  }

  if (days <= 2 || (days <= 3 && task.effortMinutes >= 180)) {
    return {
      label: "PLAN SOON",
      className: "status-soon",
      message: "Consider reserving a short work session soon."
    };
  }

  return {
    label: "ON THE RADAR",
    className: "status-plan",
    message: "There may be time to break this into smaller sessions."
  };
}

function renderDeadlineRadar() {
  const container = $("#radarList");
  container.replaceChildren();

  const tasks = [...state.tasks].sort((a, b) => {
    return (daysUntil(a.deadline) ?? Infinity) - (daysUntil(b.deadline) ?? Infinity);
  });

  setText("#radarCount", `${tasks.length} task${tasks.length === 1 ? "" : "s"}`);

  if (tasks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "radar-empty";

    const icon = document.createElement("span");
    icon.textContent = "☁";
    icon.setAttribute("aria-hidden", "true");

    const title = document.createElement("p");
    title.textContent = "No tasks on the radar yet.";

    const description = document.createElement("span");
    description.textContent = "Adding a deadline can make the next move clearer.";

    empty.append(icon, title, description);
    container.append(empty);
    return;
  }

  tasks.forEach((task) => {
    const status = classifyDeadline(task);

    const card = document.createElement("article");
    card.className = "radar-task";

    const top = document.createElement("div");
    top.className = "radar-task-top";

    const info = document.createElement("div");

    const title = document.createElement("h4");
    title.textContent = task.title;

    const meta = document.createElement("div");
    meta.className = "radar-task-meta";
    meta.textContent = `${formatDate(task.deadline)} · ${formatEffort(task.effortMinutes)} remaining`;

    info.append(title, meta);

    const badge = document.createElement("span");
    badge.className = `radar-status ${status.className}`;
    badge.textContent = status.label;

    top.append(info, badge);

    const explanation = document.createElement("p");
    explanation.className = "radar-task-meta";
    explanation.textContent = status.message;

    const bottom = document.createElement("div");
    bottom.className = "radar-task-bottom";

    const days = daysUntil(task.deadline);
    const remaining = document.createElement("span");
    remaining.textContent = days === null
      ? "Deadline unknown"
      : days < 0
        ? `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} overdue`
        : days === 0
          ? "Due today"
          : `${days} day${days === 1 ? "" : "s"} to go`;

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Remove";
    deleteButton.setAttribute("aria-label", `Remove ${task.title} from deadline radar`);

    deleteButton.addEventListener("click", () => {
      state.tasks = state.tasks.filter((item) => item.id !== task.id);
      saveState();
      renderDeadlineRadar();
      showToast("Task removed from your radar.");
    });

    bottom.append(remaining, deleteButton);
    card.append(top, explanation, bottom);
    container.append(card);
  });
}

function formatEffort(minutes) {
  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = minutes / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hr`;
}

function handleDeadlineForm(event) {
  event.preventDefault();

  const title = $("#radarTask").value.trim();
  const deadline = $("#radarDate").value;
  const effortMinutes = Number($("#radarEffort").value);

  if (!title || !parseLocalDate(deadline)) {
    showToast("Add a task and a valid deadline.");
    return;
  }

  state.tasks.push({
    id: makeId(),
    title,
    deadline,
    effortMinutes,
    createdAt: new Date().toISOString()
  });

  state.tasks = state.tasks.slice(-100);

  saveState();
  renderDeadlineRadar();

  $("#radarTask").value = "";
  $("#radarDate").value = "";

  showToast("Task added. Now you can decide on one small next move.");
}

function addWin({ note, strategy, outcome, source = "manual" }) {
  const win = {
    id: makeId(),
    note: note.trim(),
    strategy: strategyLabels[strategy] ? strategy : "other",
    outcome: outcomeLabels[outcome] ? outcome : "partial",
    source,
    createdAt: new Date().toISOString()
  };

  state.wins.unshift(win);
  state.wins = state.wins.slice(0, 100);

  saveState();
  renderWins();
  renderPatternSummary();

  return win;
}

function handleWinForm(event) {
  event.preventDefault();

  const note = $("#winNote").value.trim();

  if (!note) {
    showToast("Add a tiny win or observation first.");
    return;
  }

  addWin({
    note,
    strategy: $("#winStrategy").value,
    outcome: $("#winOutcome").value
  });

  $("#winNote").value = "";
  showToast("Added to your journal. Small progress still counts.");
}

function renderWins() {
  const container = $("#winsGrid");
  container.replaceChildren();

  setText("#winCount", String(state.wins.length));

  if (state.wins.length === 0) {
    const empty = document.createElement("div");
    empty.className = "wins-empty";
    empty.textContent = "Your first little win can go here. It doesn't have to be impressive.";
    container.append(empty);
    return;
  }

  state.wins.slice(0, 6).forEach((win) => {
    const card = document.createElement("article");
    card.className = "win-card";

    const top = document.createElement("div");
    top.className = "win-card-top";

    const icon = document.createElement("span");
    icon.textContent = win.outcome === "yes" ? "✳" : win.outcome === "partial" ? "♡" : "☁";
    icon.setAttribute("aria-hidden", "true");

    const date = document.createElement("small");
    const created = new Date(win.createdAt);
    date.textContent = Number.isNaN(created.getTime())
      ? ""
      : created.toLocaleDateString(undefined, { month: "short", day: "numeric" });

    top.append(icon, date);

    const note = document.createElement("p");
    note.textContent = win.note;

    const strategy = document.createElement("small");
    strategy.textContent = strategyLabels[win.strategy] || strategyLabels.other;

    const outcome = document.createElement("span");
    outcome.className = `win-outcome ${win.outcome}`;
    outcome.textContent = outcomeLabels[win.outcome] || "Logged";

    card.append(top, note, strategy, document.createElement("br"), outcome);
    container.append(card);
  });
}

function renderPatternSummary() {
  const wins = state.wins;
  const observations = wins.length;

  if (observations < 3) {
    setText("#patternTitle", "We're still getting to know your habits.");
    setText(
      "#patternDescription",
      `You've logged ${observations} of 3 initial observations. Log a few attempts and their outcomes before looking for patterns. These early entries are not enough to conclude which strategy works best for you.`
    );
    return;
  }

  const groups = {};

  wins.forEach((win) => {
    if (!groups[win.strategy]) {
      groups[win.strategy] = {
        total: 0,
        yes: 0,
        partial: 0,
        no: 0
      };
    }

    groups[win.strategy].total += 1;
    groups[win.strategy][win.outcome] += 1;
  });

  const eligible = Object.entries(groups)
    .filter(([, group]) => group.total >= 3)
    .map(([strategy, group]) => ({
      strategy,
      ...group,
      positiveRate: (group.yes + group.partial * 0.5) / group.total
    }))
    .sort((a, b) => b.positiveRate - a.positiveRate);

  if (eligible.length === 0) {
    setText("#patternTitle", "You're building a useful record.");
    setText(
      "#patternDescription",
      `You have ${observations} logged observations, but no single strategy has at least three attempts yet. Keep recording what you try and how it feels; avoid drawing conclusions from too little data.`
    );
    return;
  }

  const best = eligible[0];
  const label = strategyLabels[best.strategy] || strategyLabels.other;
  const percent = Math.round(best.positiveRate * 100);

  setText("#patternTitle", `An early pattern: ${label.toLowerCase()}`);
  setText(
    "#patternDescription",
    `In your ${best.total} logged attempts with this strategy, ${percent}% were marked "I started" or "A little". This is a small, self-reported observation—not proof that the strategy caused the outcome or will work next time.`
  );
}

function openHelp() {
  $("#helpPanel").classList.remove("hidden");
  $("#openHelp").setAttribute("aria-expanded", "true");
  $("#topHelp").setAttribute("aria-expanded", "true");
  $("#chatInput").focus();
}

function closeHelp() {
  $("#helpPanel").classList.add("hidden");
  $("#openHelp").setAttribute("aria-expanded", "false");
  $("#topHelp").setAttribute("aria-expanded", "false");
}

function appendChatMessage(text, role) {
  const container = $("#chatMessages");
  const bubble = document.createElement("div");

  bubble.className = `chat-bubble ${role === "user" ? "user-message" : "bot-message"}`;
  bubble.textContent = text;

  container.append(bubble);
  container.scrollTop = container.scrollHeight;

  return bubble;
}

function chooseChatResponse(message) {
  const text = message.toLowerCase();

  if (/suicid|self.harm|hurt myself|kill myself/.test(text)) {
    return "I'm sorry things feel this heavy. I'm a task-planning helper, not a crisis service. If you're in immediate danger, contact your local emergency service or someone you trust who can stay with you. You deserve real support.";
  }

  if (/overwhelm|too much|stressed|panic|anxious/.test(text)) {
    return "Let's lower the pressure. You don't have to solve the whole task right now. Pick one: open the file, gather the materials, or write down the very next question. Which feels easiest?";
  }

  if (/don't know|dont know|where.*start|confus|unclear/.test(text)) {
    return "Try a clarity step: write down what the finished task needs to contain, then list one thing you can do first. If you're still unsure, your first action can simply be finding the instructions or an example.";
  }

  if (/perfect|mistake|wrong|failure|fail/.test(text)) {
    return "The first version can be a draft, not a verdict on you. Give yourself permission to make something incomplete for five minutes. You can improve it after it exists.";
  }

  if (/boring|bored|can't be bothered|cant be bothered|motivation/.test(text)) {
    return "You don't have to wait for motivation. Try making the task shorter and easier to enter: set up what you need, do one small piece, then choose whether to continue.";
  }

  if (/distract|phone|scroll|social media|focus/.test(text)) {
    return "Let's change one thing around you instead of fighting everything at once. Put your phone out of reach, close one tab, and choose one task window. A five-minute timer is enough for a first experiment.";
  }

  if (/tired|exhaust|sleep|energy|burnt out|burnout/.test(text)) {
    return "Low energy deserves some kindness. If you need rest, take it. If a little progress feels manageable, choose a smaller version of the task—like opening the file or writing one line.";
  }

  if (/if.then|if then|plan/.test(text)) {
    return "Try this template: 'If [a specific moment or situation happens], then I will [one small action] for [a short amount of time].' For example: 'After I make tea, I'll open my assignment and write three rough bullet points.'";
  }

  if (/break.*down|big task|huge task|large task/.test(text)) {
    return "Write down three small pieces of the task. Circle the easiest one. Turn that into an action that starts with a verb, like 'open', 'read', 'list', 'write', or 'send'. You only need to do the first piece.";
  }

  if (/hello|hi\b|hey\b/.test(text)) {
    return "Hey, welcome in. What is one task that's been sitting on your mind? We can make the next move smaller together.";
  }

  return "Let's start with the task itself. What are you trying to do, and what feels hardest about beginning? If you aren't sure, choose one small action: open the file, gather the materials, or write down the first question.";
}

function sendChatMessage(message) {
  const trimmed = message.trim();

  if (!trimmed) return;

  appendChatMessage(trimmed, "user");

  const response = chooseChatResponse(trimmed);

  appendChatMessage(response, "bot");
  speakIfEnabled(response);
}

function setupChat() {
  $("#openHelp").addEventListener("click", () => {
    if ($("#helpPanel").classList.contains("hidden")) {
      openHelp();
    } else {
      closeHelp();
    }
  });

  $("#topHelp").addEventListener("click", openHelp);
  $("#closeHelp").addEventListener("click", closeHelp);

  $("#chatForm").addEventListener("submit", (event) => {
    event.preventDefault();

    const input = $("#chatInput");
    const message = input.value.trim();

    if (!message) return;

    input.value = "";
    sendChatMessage(message);
  });

  $$("[data-chat-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      sendChatMessage(button.dataset.chatPrompt);
    });
  });
}

/* -------------------------------------------------------
   Optional browser voice
------------------------------------------------------- */

function speakIfEnabled(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.96;
  utterance.pitch = 1.0;

  window.speechSynthesis.speak(utterance);
}

function toggleVoiceOutput() {
  voiceEnabled = !voiceEnabled;

  const button = $("#voiceOutput");
  button.setAttribute("aria-pressed", String(voiceEnabled));
  button.textContent = voiceEnabled ? "🔈 Voice replies on" : "🔈 Voice replies off";

  if (!voiceEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  if (voiceEnabled && !("speechSynthesis" in window)) {
    voiceEnabled = false;
    button.setAttribute("aria-pressed", "false");
    button.textContent = "🔈 Voice replies unavailable";
    showToast("Voice replies aren't supported by this browser.");
    return;
  }

  showToast(voiceEnabled ? "Voice replies turned on." : "Voice replies turned off.");
}

function setupVoiceInput() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const button = $("#voiceInput");
  const note = $("#voiceNote");

  if (!SpeechRecognition) {
    button.textContent = "🎙 Voice input unavailable";
    button.disabled = true;
    note.textContent = "This browser does not support speech recognition. You can still type your message.";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = navigator.language || "en-US";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onstart = () => {
    recognitionActive = true;
    button.textContent = "🎙 Listening…";
    note.textContent = "Listening. Speak naturally, then wait for the transcript.";
  };

  recognition.onresult = (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript?.trim();

    if (transcript) {
      $("#chatInput").value = transcript;
      $("#chatInput").focus();
      showToast("Voice captured. Review your message and send it.");
    }
  };

  recognition.onerror = (event) => {
    note.textContent = event.error === "not-allowed"
      ? "Microphone permission was denied. You can type instead."
      : "Voice input stopped. You can try again or type instead.";
  };

  recognition.onend = () => {
    recognitionActive = false;
    button.textContent = "🎙 Voice input";
  };

  button.addEventListener("click", () => {
    if (recognitionActive) {
      recognition.stop();
      return;
    }

    try {
      recognition.start();
    } catch (error) {
      console.warn("Could not start speech recognition.", error);
      showToast("Voice input couldn't start. Please try again.");
    }
  });
}

function setupVoice() {
  $("#voiceOutput").addEventListener("click", toggleVoiceOutput);
  setupVoiceInput();
}

function setupMobileNavigation() {
  const sidebar = $("#sidebar");
  const menu = $("#mobileMenu");

  menu.addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("mobile-open");
    menu.setAttribute("aria-expanded", String(isOpen));
    menu.textContent = isOpen ? "×" : "☰";
  });

  $$(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      sidebar.classList.remove("mobile-open");
      menu.setAttribute("aria-expanded", "false");
      menu.textContent = "☰";

      $$(".nav-link").forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });

  const sections = $$(".main-content section[id]");

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (!visible) return;

      const matchingLink = $(`.nav-link[href="#${visible.target.id}"]`);

      if (matchingLink) {
        $$(".nav-link").forEach((item) => item.classList.remove("active"));
        matchingLink.classList.add("active");
      }
    }, {
      rootMargin: "-20% 0px -65% 0px",
      threshold: [0, 0.1, 0.3]
    });

    sections.forEach((section) => observer.observe(section));
  }
}

function setupForms() {
  $("#taskForm").addEventListener("submit", handleTaskForm);
  $("#forecastButton").addEventListener("click", handleForecastRequest);
  $("#saveCheckinButton").addEventListener("click", handleSaveCheckin);
  $("#sampleButton").addEventListener("click", handleSampleTask);
  $("#newStrategy").addEventListener("click", tryAnotherStrategy);
  $("#markStarted").addEventListener("click", markCurrentStepStarted);
  $("#deadlineForm").addEventListener("submit", handleDeadlineForm);
  $("#winForm").addEventListener("submit", handleWinForm);
  $("#outcomeForm").addEventListener("submit", handleOutcomeForm);
  $("#historyButton").addEventListener("click", handleHistoryRequest);
  $("#energy").addEventListener("input", updateEnergyLabel);
}

function renderInitialState() {
  renderWins();
  renderDeadlineRadar();
  renderPatternSummary();
  updateEnergyLabel();
  updateDate();
}

function init() {
  setupBarrierCheckin();
  setupForms();
  setupTimer();
  setupChat();
  setupVoice();
  setupMobileNavigation();
  renderInitialState();

  $("#radarDate").min = localDateString();

  $("#outcomeDate").value = localDateString();
  console.info("Slothcast frontend initialized with local API integration.");
}

document.addEventListener("DOMContentLoaded", init);