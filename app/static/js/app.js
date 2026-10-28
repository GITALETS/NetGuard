/**
 * Módulo principal de interfaz amigable para el hogar.
 * Incluye selector de Tema Claro/Oscuro sin fatiga visual,
 * diálogos de confirmación, asistencia en formularios y selectores rápidos.
 */

document.addEventListener("DOMContentLoaded", () => {
  initThemeToggle();
  initMobileSidebar();
  initConfirmationModal();
  initPolicyFormHelper();
  initScheduleFormHelper();
  initSubmitLoadingIndicator();
});

/**
 * Permite alternar entre Tema Claro Suave (sin fatiga visual) y Tema Oscuro Descansado.
 */
function initThemeToggle() {
  const toggleBtn = document.getElementById("theme-toggle-btn");
  const labelEl = document.getElementById("theme-toggle-label");
  const iconSun = document.getElementById("theme-icon-sun");
  const iconMoon = document.getElementById("theme-icon-moon");
  const htmlEl = document.documentElement;

  const applyTheme = (theme) => {
    htmlEl.setAttribute("data-theme", theme);
    if (theme === "dark") {
      htmlEl.classList.add("dark");
      if (labelEl) labelEl.textContent = "Modo Claro";
      if (iconSun) iconSun.classList.remove("hidden");
      if (iconMoon) iconMoon.classList.add("hidden");
    } else {
      htmlEl.classList.remove("dark");
      if (labelEl) labelEl.textContent = "Modo Oscuro";
      if (iconSun) iconSun.classList.add("hidden");
      if (iconMoon) iconMoon.classList.remove("hidden");
    }
  };

  const savedTheme = localStorage.getItem("netguard_ui_theme") || "light";
  applyTheme(savedTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const current = htmlEl.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";
      localStorage.setItem("netguard_ui_theme", next);
      applyTheme(next);
    });
  }
}

/**
 * Controla el menú lateral en pantallas móviles y tabletas.
 */
function initMobileSidebar() {
  const toggleBtn = document.getElementById("mobile-menu-btn");
  const closeBtn = document.getElementById("mobile-menu-close");
  const sidebar = document.getElementById("app-sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");

  if (!toggleBtn || !sidebar) return;

  const openMenu = () => {
    sidebar.classList.remove("-translate-x-full");
    if (backdrop) backdrop.classList.remove("hidden");
  };

  const closeMenu = () => {
    sidebar.classList.add("-translate-x-full");
    if (backdrop) backdrop.classList.add("hidden");
  };

  toggleBtn.addEventListener("click", openMenu);
  if (closeBtn) closeBtn.addEventListener("click", closeMenu);
  if (backdrop) backdrop.addEventListener("click", closeMenu);
}

/**
 * Intercepta formularios marcados con `data-confirm-message` y muestra un
 * diálogo modal de confirmación accesible antes de ejecutar la acción destructiva.
 */
function initConfirmationModal() {
  const modal = document.getElementById("confirm-modal");
  const titleEl = document.getElementById("confirm-modal-title");
  const messageEl = document.getElementById("confirm-modal-message");
  const confirmBtn = document.getElementById("confirm-modal-accept");
  const cancelBtn = document.getElementById("confirm-modal-cancel");

  if (!modal || !confirmBtn || !cancelBtn) return;

  let pendingForm = null;

  document.querySelectorAll("form[data-confirm-message]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.confirmed === "true") {
        return;
      }
      event.preventDefault();
      pendingForm = form;
      if (titleEl) {
        titleEl.textContent = form.dataset.confirmTitle || "Confirmar acción";
      }
      if (messageEl) {
        messageEl.textContent =
          form.dataset.confirmMessage ||
          "¿Está seguro de que desea realizar esta acción?";
      }
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      confirmBtn.focus();
    });
  });

  const closeModal = () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    pendingForm = null;
  };

  cancelBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });

  confirmBtn.addEventListener("click", () => {
    if (pendingForm) {
      pendingForm.dataset.confirmed = "true";
      pendingForm.submit();
    }
  });
}

/**
 * Adapta los campos del formulario de políticas según la categoría seleccionada.
 */
function initPolicyFormHelper() {
  const typeSelect = document.getElementById("policy_type_select");
  const validUntilInput = document.getElementById("valid_until_input");
  const validUntilHint = document.getElementById("valid_until_hint");
  const navProfileGroup = document.getElementById("nav_profile_group");
  const actionSelect = document.getElementById("policy_action_select");

  if (!typeSelect) return;

  const updateFields = () => {
    const typeVal = typeSelect.value;

    if (validUntilInput && validUntilHint) {
      if (typeVal === "permanent_access") {
        validUntilInput.value = "";
        validUntilInput.disabled = true;
        validUntilHint.textContent =
          "No aplica: un permiso permanente no tiene fecha de vencimiento.";
      } else if (typeVal === "temporary_access") {
        validUntilInput.disabled = false;
        validUntilHint.textContent =
          "Obligatorio para Permiso Temporal: elija hasta qué día y hora tendrá acceso.";
      } else {
        validUntilInput.disabled = false;
        validUntilHint.textContent =
          "Opcional: déjelo en blanco si no desea que venza en una fecha fija.";
      }
    }

    if (navProfileGroup) {
      if (typeVal === "navigation_restriction") {
        navProfileGroup.classList.remove("hidden");
        if (actionSelect && actionSelect.value === "allow") {
          actionSelect.value = "restrict";
        }
      } else {
        navProfileGroup.classList.add("hidden");
      }
    }
  };

  typeSelect.addEventListener("change", updateFields);
  updateFields();
}

/**
 * Analiza en tiempo real la hora inicial y final de un horario y ofrece botones rápidos de días.
 */
function initScheduleFormHelper() {
  const startInput = document.getElementById("schedule_start_time");
  const endInput = document.getElementById("schedule_end_time");
  const previewBox = document.getElementById("schedule_window_preview");

  // Botones rápidos de selección de días
  document.querySelectorAll("[data-select-days]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetDays = btn.dataset.selectDays.split(",");
      document.querySelectorAll('input[name="days_of_week"]').forEach((cb) => {
        cb.checked = targetDays.includes(cb.value);
      });
    });
  });

  if (!startInput || !endInput || !previewBox) return;

  const updatePreview = () => {
    const s = startInput.value;
    const e = endInput.value;
    if (!s || !e || !s.includes(":") || !e.includes(":")) {
      previewBox.textContent = "Elija la hora de inicio y la hora de fin.";
      return;
    }

    const [sh, sm] = s.split(":").map(Number);
    const [eh, em] = e.split(":").map(Number);
    const startMins = sh * 60 + sm;
    const endMins = eh * 60 + em;

    if (startMins === endMins) {
      previewBox.innerHTML =
        '<strong>Atención:</strong> La hora de inicio y de fin no pueden ser exactamente la misma.';
      return;
    }

    let diffMins = 0;
    let crosses = false;
    if (endMins > startMins) {
      diffMins = endMins - startMins;
    } else {
      crosses = true;
      diffMins = 24 * 60 - startMins + endMins;
    }

    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    const durText = `${hours} horas ${mins > 0 ? "y " + mins + " min" : ""}`.trim();

    if (crosses) {
      previewBox.innerHTML =
        `<strong>Horario nocturno (cruza la medianoche):</strong> ` +
        `Comienza a las <strong>${s}</strong> de la noche y termina a las <strong>${e}</strong> de la mañana siguiente (${durText}).`;
    } else {
      previewBox.innerHTML =
        `<strong>Horario en el mismo día:</strong> ` +
        `Desde las <strong>${s}</strong> hasta las <strong>${e}</strong> (${durText}).`;
    }
  };

  startInput.addEventListener("input", updatePreview);
  endInput.addEventListener("input", updatePreview);
  updatePreview();
}

/**
 * Añade indicador visual de procesamiento al enviar formularios.
 */
function initSubmitLoadingIndicator() {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      if (form.dataset.confirmMessage && form.dataset.confirmed !== "true") {
        return;
      }
      const btn = form.querySelector('button[type="submit"][data-loading-text]');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>${btn.dataset.loadingText}</span>`;
      }
    });
  });
}
