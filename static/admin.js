(function () {
  document.querySelectorAll("[data-admin-field]").forEach((field) => {
    const boxes = field.querySelectorAll(".topic-chip-input");
    const status = field.querySelector("[data-status]");
    let fadeTimer = null;

    function show(text, isError) {
      status.textContent = text;
      status.classList.toggle("is-error", !!isError);
      clearTimeout(fadeTimer);
      if (!isError) {
        fadeTimer = setTimeout(() => {
          status.textContent = "";
        }, 2000);
      }
    }

    function checkedValues() {
      return [...boxes].filter((box) => box.checked).map((box) => box.value);
    }

    boxes.forEach((box) => {
      box.addEventListener("change", () => {
        const values = checkedValues();
        if (values.length === 0) {
          box.checked = true;
          show("Нужно оставить хотя бы один вариант", true);
          return;
        }
        const body = new URLSearchParams();
        values.forEach((value) => body.append(box.name, value));
        fetch(field.dataset.url, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        })
          .then((response) => {
            if (!response.ok) throw new Error("save failed");
            return response.json();
          })
          .then(() => show("Сохранено", false))
          .catch(() => show("Не сохранилось — обновите страницу", true));
      });
    });
  });
})();
