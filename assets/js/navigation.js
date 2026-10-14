const toggle = document.querySelector(".menu-toggle");
const nav = document.querySelector("#site-nav");
toggle?.addEventListener("click", () => { const open = toggle.getAttribute("aria-expanded") !== "true"; toggle.setAttribute("aria-expanded", String(open)); nav?.classList.toggle("open", open); });
nav?.addEventListener("click", () => { nav.classList.remove("open"); toggle?.setAttribute("aria-expanded", "false"); });
