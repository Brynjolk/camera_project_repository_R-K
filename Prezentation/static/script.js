"use strict";

/*
  script.js:
  — плавное появление секций;
  — индикатор прокрутки;
  — подсветка навигации;
  — спокойное движение звёздного фона за указателем.
*/

document.addEventListener("DOMContentLoaded", () => {
  const progressBar = document.querySelector("#page-progress");
  const header = document.querySelector(".site-header");
  const revealElements = document.querySelectorAll(".reveal");
  const navLinks = document.querySelectorAll('.main-nav a[href^="#"]');
  const sections = document.querySelectorAll("main section[id]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Появление элементов при прокрутке.
  if ("IntersectionObserver" in window && !reduceMotion) {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      {
        threshold: 0.12,
        rootMargin: "0px 0px -35px 0px"
      }
    );

    revealElements.forEach((element) => revealObserver.observe(element));
  } else {
    revealElements.forEach((element) => element.classList.add("is-visible"));
  }

  // Верхняя полоска показывает, сколько страницы уже просмотрено.
  function updateScrollProgress() {
    const documentHeight =
      document.documentElement.scrollHeight - window.innerHeight;

    const progress =
      documentHeight > 0 ? (window.scrollY / documentHeight) * 100 : 0;

    if (progressBar) {
      progressBar.style.width = `${Math.min(progress, 100)}%`;
    }

    if (header) {
      header.classList.toggle("is-scrolled", window.scrollY > 12);
    }
  }

  updateScrollProgress();
  window.addEventListener("scroll", updateScrollProgress, { passive: true });
  window.addEventListener("resize", updateScrollProgress);

  // Подсветка соответствующего пункта меню.
  if ("IntersectionObserver" in window && sections.length && navLinks.length) {
    const sectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          const currentId = `#${entry.target.id}`;

          navLinks.forEach((link) => {
            const isCurrent = link.getAttribute("href") === currentId;

            if (isCurrent) {
              link.setAttribute("aria-current", "location");
            } else {
              link.removeAttribute("aria-current");
            }
          });
        });
      },
      {
        rootMargin: "-30% 0px -55% 0px",
        threshold: 0
      }
    );

    sections.forEach((section) => sectionObserver.observe(section));
  }

  // Небольшой эффект глубины на больших экранах.
  // Не влияет на функциональность и отключается при настройке reduced motion.
  const hero = document.querySelector(".hero");

  if (hero && !reduceMotion && window.matchMedia("(pointer: fine)").matches) {
    let animationFrame = null;

    hero.addEventListener("pointermove", (event) => {
      if (animationFrame) cancelAnimationFrame(animationFrame);

      animationFrame = requestAnimationFrame(() => {
        const rect = hero.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;

        hero.style.setProperty("--pointer-x", `${x.toFixed(3)}`);
        hero.style.setProperty("--pointer-y", `${y.toFixed(3)}`);
      });
    });

    hero.addEventListener("pointerleave", () => {
      hero.style.setProperty("--pointer-x", "0");
      hero.style.setProperty("--pointer-y", "0");
    });
  }
});
