const state = { lessons: [], selected: null, filter: "all", view: "learn" };
const progressKey = "cross-functional-ai-specialist-progress-v1";

function progress() {
  try { return JSON.parse(localStorage.getItem(progressKey)) || {}; }
  catch { return {}; }
}

function saveProgress(next) {
  localStorage.setItem(progressKey, JSON.stringify(next));
  renderProgress();
}

function renderProgress() {
  const ready = state.lessons.filter((lesson) => lesson.status === "ready");
  const done = progress();
  const completed = ready.filter((lesson) => done[lesson.id]).length;
  const percent = ready.length ? Math.round((completed / ready.length) * 100) : 0;
  document.querySelector("#progress-copy").textContent = `${completed} of ${ready.length} complete`;
  const track = document.querySelector(".progress-track");
  track.setAttribute("aria-valuenow", String(percent));
  document.querySelector("#progress-bar").style.width = `${percent}%`;
}

function renderList() {
  const list = document.querySelector("#lesson-list");
  const shown = state.lessons.filter((lesson) => state.filter === "all" || lesson.status === state.filter);
  list.innerHTML = shown.map((lesson) => `
    <li>
      <button class="lesson-button ${state.selected?.id === lesson.id ? "selected" : ""}" data-id="${lesson.id}">
        <span class="step">${String(lesson.step).padStart(2, "0")}</span>
        <span><span class="lesson-title">${lesson.title}</span><span class="phase">${lesson.phase}</span></span>
        <span class="status ${lesson.status}">${lesson.status}</span>
      </button>
    </li>`).join("");
  list.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    state.selected = state.lessons.find((lesson) => lesson.id === button.dataset.id);
    state.view = "learn";
    renderList();
    renderDetail();
  }));
}

function viewCopy(lesson) {
  if (lesson.status === "planned") {
    return `<div class="notice"><strong>Planned, not ready.</strong> The scope is defined in the sequential plan. Notebook, lab, and checkpoint will appear only after the complete course passes quality gates.</div>`;
  }
  const views = {
    learn: `<p>Use the chapter as the technical narrative: motivation, mechanics, architecture alternatives, tooling, state of the art, failure analysis, production upgrades, exercises, and sources.</p><a class="action" href="${lesson.readme}">Open course chapter</a>`,
    lab: `<p>The notebook is the primary guided experience. It imports the same deterministic implementation tested by the repository, compares a baseline, injects failures, and interprets evaluation evidence.</p><div class="actions"><a class="action" href="${lesson.notebook}">Open notebook</a><a class="action secondary" href="${lesson.lab}">Inspect reusable lab</a></div>`,
    checkpoint: `<p>The focused checkpoint tests architecture judgment, trust boundaries, failure policy, and metric interpretation—not memorized vocabulary.</p><div class="actions"><a class="action" href="${lesson.checkpoint}">Open checkpoint data</a><a class="action secondary" href="../quiz/index.html">Take full quiz</a></div>`
  };
  return views[state.view];
}

function renderDetail() {
  const lesson = state.selected;
  if (!lesson) return;
  const done = Boolean(progress()[lesson.id]);
  document.querySelector("#lesson-detail").innerHTML = `
    <p class="eyebrow">Step ${lesson.step} · ${lesson.phase}</p>
    <h2>${lesson.title}</h2>
    <span class="status ${lesson.status}">${lesson.status}</span>
    <p class="summary">${lesson.summary}</p>
    <h3>Outcomes</h3>
    <ul class="outcomes">${lesson.outcomes.map((outcome) => `<li>${outcome}</li>`).join("")}</ul>
    <div class="tabbar" role="tablist" aria-label="Lesson views">
      ${["learn", "lab", "checkpoint"].map((view) => `<button class="tab ${state.view === view ? "active" : ""}" data-view="${view}" ${lesson.status === "planned" && view !== "learn" ? "disabled" : ""}>${view[0].toUpperCase() + view.slice(1)}</button>`).join("")}
    </div>
    <div class="view">${viewCopy(lesson)}</div>
    <div class="actions">
      ${lesson.status === "ready" ? `<button class="complete ${done ? "done" : ""}">${done ? "Completed ✓" : "Mark complete"}</button>` : ""}
      <a class="action secondary" href="${lesson.readme}">${lesson.status === "ready" ? "Course source" : "Read planned scope"}</a>
    </div>`;
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
    if (tab.disabled) return;
    state.view = tab.dataset.view;
    renderDetail();
  }));
  const complete = document.querySelector(".complete");
  if (complete) complete.addEventListener("click", () => {
    const next = progress();
    next[lesson.id] = !next[lesson.id];
    saveProgress(next);
    renderDetail();
  });
}

document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
  renderList();
}));

fetch("lessons.json")
  .then((response) => {
    if (!response.ok) throw new Error(`Curriculum registry returned ${response.status}`);
    return response.json();
  })
  .then((lessons) => {
    state.lessons = lessons;
    state.selected = lessons.find((lesson) => lesson.status === "ready") || lessons[0];
    renderList();
    renderDetail();
    renderProgress();
  })
  .catch((error) => {
    document.querySelector("#lesson-detail").innerHTML = `<h2>Unable to load curriculum</h2><p>${error.message}. Serve the repository with a local web server rather than opening the HTML file directly.</p>`;
  });
