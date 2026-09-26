(function () {
  const form = document.getElementById("filters");
  const summary = document.getElementById("filters-summary");
  if (!form || !summary) return;

  const number = (n) => n.toLocaleString("ru-RU");
  const words = (n) => {
    const tail = n % 100;
    const last = n % 10;
    const word =
      tail >= 11 && tail <= 14 ? "слов" : last === 1 ? "слово" : last >= 2 && last <= 4 ? "слова" : "слов";
    return number(n) + " " + word;
  };
  const slot = (name) => summary.querySelector('[data-sum="' + name + '"]');

  function syncBank(bank) {
    const on = bank.querySelector(".bank-check").checked;
    const chips = bank.querySelectorAll(".topic-chip-input");
    bank.classList.toggle("is-on", on);
    chips.forEach((chip) => {
      chip.disabled = !on;
      if (!on) chip.checked = false;
    });
    const picked = bank.querySelectorAll(".topic-chip-input:checked").length;
    const state = bank.querySelector("[data-state]");
    if (state) state.textContent = on ? (picked ? "тем: " + picked : "весь учебник") : "";
  }

  let timer = null;
  let controller = null;

  function refresh() {
    const params = new URLSearchParams(new FormData(form));
    if (controller) controller.abort();
    controller = new AbortController();
    slot("title").textContent = params.has("textbook") ? "В фильтре" : "Выберите учебник";
    fetch(form.dataset.previewUrl + "?" + params.toString(), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((data) => {
        slot("words").textContent = words(data.words);
        slot("started").textContent = number(data.started);
        slot("due").textContent = number(data.due);
        slot("untouched").textContent = number(data.untouched);
        summary.classList.remove("is-stale");
      })
      .catch((error) => {
        if (error && error.name === "AbortError") return;
        summary.classList.add("is-stale");
      });
  }

  form.addEventListener("click", (event) => {
    const toggle = event.target.closest(".meta-toggle");
    if (!toggle) return;
    const detail = document.getElementById(toggle.getAttribute("aria-controls"));
    const open = detail.hidden;
    detail.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  form.addEventListener("change", (event) => {
    const bank = event.target.closest("[data-bank]");
    if (bank) syncBank(bank);
    summary.classList.add("is-stale");
    clearTimeout(timer);
    timer = setTimeout(refresh, 150);
  });
})();
