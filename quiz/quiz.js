const state = { questions: [], category: "all" };

function visibleQuestions() {
  return state.questions.filter((question) => state.category === "all" || question.category === state.category);
}

function render() {
  const questions = visibleQuestions();
  document.querySelector("#count").textContent = `${questions.length} question${questions.length === 1 ? "" : "s"}`;
  document.querySelector("#quiz-form").innerHTML = questions.map((question, index) => `
    <fieldset class="question" data-id="${question.id}">
      <legend class="meta">${question.category}</legend>
      <h2>${index + 1}. ${question.prompt}</h2>
      ${question.options.map((option, optionIndex) => `<label class="option"><input type="radio" name="${question.id}" value="${optionIndex}" /> ${option}</label>`).join("")}
      <div class="explanation"><strong>Explanation:</strong> ${question.explanation}</div>
    </fieldset>`).join("");
  document.querySelector("#result").textContent = "";
}

function score() {
  const questions = visibleQuestions();
  let correct = 0;
  questions.forEach((question) => {
    const card = document.querySelector(`[data-id="${question.id}"]`);
    const chosen = card.querySelector("input:checked");
    const isCorrect = chosen && Number(chosen.value) === question.answer;
    correct += Number(Boolean(isCorrect));
    card.classList.add("scored", isCorrect ? "correct" : "incorrect");
  });
  const percent = questions.length ? Math.round((correct / questions.length) * 100) : 0;
  document.querySelector("#result").innerHTML = `<strong>${correct}/${questions.length} (${percent}%)</strong> — ${percent >= 80 ? "Checkpoint passed. Defend your choices using the explanations." : "Revisit the relevant course sections and try again."}`;
}

fetch("questions.json")
  .then((response) => response.json())
  .then((data) => {
    state.questions = data.questions;
    const categories = [...new Set(state.questions.map((question) => question.category))].sort();
    document.querySelector("#category").insertAdjacentHTML("beforeend", categories.map((category) => `<option value="${category}">${category}</option>`).join(""));
    render();
  });

document.querySelector("#category").addEventListener("change", (event) => {
  state.category = event.target.value;
  render();
});
document.querySelector("#submit").addEventListener("click", score);
