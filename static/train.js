(function () {
  const card = document.getElementById("card");
  const grade = document.getElementById("grade");
  if (!card || !grade) return;

  const front = card.querySelector(".card-front");
  const back = card.querySelector(".card-back");

  function flip() {
    const open = card.classList.toggle("is-flipped");
    card.setAttribute("aria-pressed", open ? "true" : "false");
    if (front) front.setAttribute("aria-hidden", open ? "true" : "false");
    if (back) back.setAttribute("aria-hidden", open ? "false" : "true");
    grade.hidden = false;
  }

  card.addEventListener("click", flip);

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target;
    if (target instanceof Element && target.closest("button, a, input, select, textarea")) return;

    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      flip();
      return;
    }

    if (!grade.hidden && /^[1-9]$/.test(event.key)) {
      const button = grade.querySelectorAll("button")[Number(event.key) - 1];
      if (button) {
        event.preventDefault();
        button.click();
      }
    }
  });
})();
