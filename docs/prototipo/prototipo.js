(() => {
  const buttons = [...document.querySelectorAll("[data-screen]")];
  const screens = [...document.querySelectorAll(".screen")];

  function showScreen(id, focus = false) {
    const target = screens.find((screen) => screen.id === id);
    if (!target) return;
    screens.forEach((screen) => {
      const active = screen === target;
      screen.hidden = !active;
      screen.classList.toggle("is-active", active);
    });
    buttons.forEach((button) => {
      const active = button.dataset.screen === id;
      button.classList.toggle("is-selected", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    history.replaceState(null, "", `#${id}`);
    if (focus) document.querySelector("#conteudo").focus({ preventScroll: true });
  }

  buttons.forEach((button) => button.addEventListener("click", () => showScreen(button.dataset.screen)));
  document.querySelectorAll("[data-screen-link]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showScreen(link.dataset.screenLink);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.altKey && /^[1-5]$/.test(event.key)) {
      event.preventDefault();
      const button = buttons[Number(event.key) - 1];
      showScreen(button.dataset.screen, true);
      button.focus();
    }
  });
  showScreen(location.hash.slice(1) || "resumo");
})();
