(() => {
  const buttons = [...document.querySelectorAll("[data-screen]")];
  const screens = [...document.querySelectorAll(".screen")];

  function showScreen(id) {
    const target = screens.find((screen) => screen.id === id) || screens[0];
    screens.forEach((screen) => {
      const active = screen === target;
      screen.hidden = !active;
    });
    buttons.forEach((button) => {
      const active = button.dataset.screen === target.id;
      button.classList.toggle("is-selected", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    history.replaceState(null, "", `#${target.id}`);
  }

  buttons.forEach((button) => button.addEventListener("click", () => showScreen(button.dataset.screen)));
  document.querySelectorAll("[data-screen-link]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showScreen(link.dataset.screenLink);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const shortcut = /^Digit([1-5])$/.exec(event.code);
    if (!shortcut) return;
    event.preventDefault();
    const button = buttons[Number(shortcut[1]) - 1];
    showScreen(button.dataset.screen);
    button.focus();
  });
  showScreen(location.hash.slice(1) || "resumo");
})();
