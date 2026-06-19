/* ═══════════════════════════════════════════════════════════════
   Lumin — Landing Page JavaScript
   Handles: domain card rendering, selection, GSAP animations,
   and subscription API calls.
   ═══════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────
  let selectedDomains = [];
  let categories = [];

  // ── Fetch interest categories from API ────────────────────────
  async function loadCategories() {
    try {
      const res = await fetch("/api/interests");
      const data = await res.json();
      categories = data.categories;
      renderDomainCards();
    } catch (err) {
      console.error("Failed to load categories:", err);
      // Fallback categories
      categories = [
        "Large Language Models (LLMs)",
        "Computer Vision",
        "Robotics & Embodied AI",
        "AI Safety & Alignment",
        "AI Engineering & MLOps",
        "Reinforcement Learning",
        "Generative AI & Diffusion",
        "Natural Language Processing",
        "AI Research Papers",
        "AI Products & Launches",
        "Developer Tools & SDKs",
        "AI Business & Industry",
      ];
      renderDomainCards();
    }
  }

  // ── Render domain cards ───────────────────────────────────────
  function renderDomainCards() {
    const grid = document.getElementById("domains-grid");
    if (!grid) return;

    grid.innerHTML = categories
      .map(
        (cat) => `
      <button
        type="button"
        class="domain-card"
        aria-pressed="false"
        data-domain="${cat}"
      >
        <div class="domain-card-glass"></div>
        <div class="domain-card-stroke"></div>
        <div class="domain-card-check">✓</div>
        <div class="domain-card-content">
          <p class="domain-card-title">${cat}</p>
        </div>
      </button>
    `
      )
      .join("");

    // Attach click handlers
    grid.querySelectorAll(".domain-card").forEach((card) => {
      card.addEventListener("click", () => toggleDomain(card));
    });
  }

  // ── Toggle domain selection ───────────────────────────────────
  function toggleDomain(card) {
    const domain = card.dataset.domain;
    const isSelected = card.getAttribute("aria-pressed") === "true";

    if (isSelected) {
      selectedDomains = selectedDomains.filter((d) => d !== domain);
      card.setAttribute("aria-pressed", "false");
    } else {
      selectedDomains.push(domain);
      card.setAttribute("aria-pressed", "true");
    }
  }

  // ── Subscribe ─────────────────────────────────────────────────
  async function handleSubscribe() {
    const nameInput = document.getElementById("name-input");
    const emailInput = document.getElementById("email-input");
    const customNote = document.getElementById("custom-note");
    const btn = document.getElementById("subscribe-btn");

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const note = customNote.value.trim();

    // Validation
    if (!name) {
      showMessage("Please enter your name.", "error");
      nameInput.focus();
      return;
    }

    if (!email || !email.includes("@")) {
      showMessage("Please enter a valid email address.", "error");
      emailInput.focus();
      return;
    }

    if (selectedDomains.length === 0) {
      showMessage("Please select at least one domain.", "error");
      return;
    }

    // Disable button
    btn.disabled = true;
    btn.textContent = "Subscribing...";

    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          email: email,
          interests: selectedDomains,
          custom_note: note || null,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        showMessage(
          `${data.message}<br><br>
           <a href="${data.manage_url}" target="_blank">Manage your preferences →</a>`,
          "success"
        );
        // Clear form
        nameInput.value = "";
        emailInput.value = "";
        customNote.value = "";
        selectedDomains = [];
        document.querySelectorAll(".domain-card").forEach((c) => {
          c.setAttribute("aria-pressed", "false");
        });
      } else {
        showMessage(data.detail || "Something went wrong.", "error");
      }
    } catch (err) {
      showMessage("Network error. Please try again.", "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Subscribe";
    }
  }

  // ── Show message ──────────────────────────────────────────────
  function showMessage(html, type) {
    const container = document.getElementById("message-container");
    const box = document.getElementById("message-box");

    box.className = "message-box " + type;
    box.innerHTML = html;
    container.style.display = "block";

    // Animate in
    gsap.fromTo(
      container,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }
    );

    // Auto-hide errors after 6s
    if (type === "error") {
      setTimeout(() => {
        gsap.to(container, {
          opacity: 0,
          duration: 0.3,
          onComplete: () => (container.style.display = "none"),
        });
      }, 6000);
    }
  }

  // ── GSAP Animations ───────────────────────────────────────────
  function initAnimations() {
    // Slow drift on the hero background
    gsap.to(".hero-bg", {
      scale: 1.06,
      duration: 18,
      ease: "sine.inOut",
      yoyo: true,
      repeat: -1,
    });

    // Reveal elements on load
    gsap.from(".reveal", {
      y: 28,
      opacity: 0,
      duration: 1,
      ease: "power3.out",
      stagger: 0.15,
      delay: 0.15,
      onComplete: function () {
        // Ensure elements are visible after animation
        document.querySelectorAll(".reveal").forEach((el) => {
          el.style.opacity = "1";
        });
      },
    });
  }

  // ── Init ──────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    loadCategories();
    initAnimations();

    // Subscribe button
    document
      .getElementById("subscribe-btn")
      .addEventListener("click", handleSubscribe);

    // Enter key on email input
    document
      .getElementById("email-input")
      .addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSubscribe();
      });
  });
})();
