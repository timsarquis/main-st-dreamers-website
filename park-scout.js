const showcase = document.querySelector("#setup-showcase");

if (showcase) {
  const track = showcase.querySelector("#setup-track");
  const slides = [...track.querySelectorAll("a")];
  const firstClone = slides[0].cloneNode(true);
  const lastClone = slides[slides.length - 1].cloneNode(true);
  for (const clone of [firstClone, lastClone]) {
    clone.setAttribute("aria-hidden", "true");
    clone.tabIndex = -1;
  }
  [...slides, firstClone, lastClone].forEach((slide) => {
    slide.querySelector("img").loading = "eager";
  });
  track.prepend(lastClone);
  track.append(firstClone);
  const count = showcase.querySelector("#setup-count");
  const title = showcase.querySelector("#setup-title");
  const description = showcase.querySelector("#setup-description");
  const progress = showcase.querySelector("#setup-progress");
  const viewport = showcase.querySelector(".scout-setup-viewport");
  const pauseButton = showcase.querySelector("#setup-pause");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let current = 0;
  let position = 1;
  let moving = false;
  let visible = false;
  let hovered = false;
  let focused = false;
  let manuallyPaused = false;
  let timer;

  const progressButtons = slides.map((slide, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", `Show setup screen ${index + 1}: ${slide.dataset.title}`);
    button.addEventListener("click", () => show(index));
    progress.append(button);
    return button;
  });

  function canPlay() {
    return visible && !hovered && !focused && !manuallyPaused && !motionPreference.matches && !document.hidden;
  }

  function schedule() {
    window.clearTimeout(timer);
    const playing = canPlay();
    showcase.classList.toggle("is-paused", !playing);
    pauseButton.hidden = motionPreference.matches;
    pauseButton.textContent = manuallyPaused ? "Play" : "Pause";
    pauseButton.setAttribute("aria-label", manuallyPaused ? "Play setup slideshow" : "Pause setup slideshow");
    if (playing) timer = window.setTimeout(() => show(current + 1, false, "next"), 5000);
  }

  function show(index, userInitiated = true, direction = "direct") {
    if (moving) return;
    const next = (index + slides.length) % slides.length;
    if (next === current && userInitiated) return;
    const previous = current;
    current = next;
    const slide = slides[current];
    if (direction === "next" && previous === slides.length - 1 && current === 0) position = slides.length + 1;
    else if (direction === "prev" && previous === 0 && current === slides.length - 1) position = 0;
    else position = current + 1;
    track.style.transform = `translateX(-${position * 100}%)`;
    moving = !motionPreference.matches && !(!userInitiated && previous === current);
    count.textContent = `${String(current + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;
    title.textContent = slide.dataset.title;
    description.textContent = slide.dataset.description;
    slides.forEach((item, position) => {
      item.tabIndex = position === current ? 0 : -1;
      item.setAttribute("aria-hidden", String(position !== current));
    });
    progressButtons.forEach((button, position) => {
      button.classList.toggle("is-complete", position < current);
      button.classList.toggle("is-current", position === current);
      if (position === current) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    // Reflow restarts the small progress animation after a manual jump.
    void progress.offsetWidth;
    if (userInitiated) manuallyPaused = true;
    schedule();
  }

  track.addEventListener("transitionend", (event) => {
    if (event.target !== track || event.propertyName !== "transform") return;
    if (position === 0 || position === slides.length + 1) {
      position = current + 1;
      track.style.transition = "none";
      track.style.transform = `translateX(-${position * 100}%)`;
      void track.offsetWidth;
      track.style.transition = "";
    }
    moving = false;
  });

  showcase.querySelector("#setup-prev").addEventListener("click", () => show(current - 1, true, "prev"));
  showcase.querySelector("#setup-next").addEventListener("click", () => show(current + 1, true, "next"));
  pauseButton.addEventListener("click", () => {
    manuallyPaused = !manuallyPaused;
    schedule();
  });
  viewport.addEventListener("mouseenter", () => { hovered = true; schedule(); });
  viewport.addEventListener("mouseleave", () => { hovered = false; schedule(); });
  track.addEventListener("focusin", () => { focused = true; schedule(); });
  track.addEventListener("focusout", (event) => {
    if (!track.contains(event.relatedTarget)) { focused = false; schedule(); }
  });
  document.addEventListener("visibilitychange", schedule);
  motionPreference.addEventListener("change", schedule);

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      schedule();
    }, { threshold: 0.25 }).observe(showcase);
  } else {
    visible = true;
  }

  show(0, false);
}
