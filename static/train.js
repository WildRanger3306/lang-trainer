(function () {
  const card = document.getElementById("card");
  const grade = document.getElementById("grade");
  if (!card || !grade) return;

  function flip() {
    const open = card.classList.toggle("is-flipped");
    card.setAttribute("aria-pressed", open ? "true" : "false");
    grade.hidden = false;
  }

  card.addEventListener("click", flip);
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      flip();
    }
  });
})();
