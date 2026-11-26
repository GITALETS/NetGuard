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
  initPasswordToggles();
  initDeviceDetailTabs();
  initIpSegmentedInputs();
  initLiveNetworkValidators();
  initCategoryQuickAddModal();
  initTableActionMenus();
  initLiveNetworkMonitor();
  initClientLiveStatusPoller();
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
 * Muestra u oculta un aviso de validación en línea justo encima de los botones del formulario.
 */
function _showFormInlineError(form, message, focusEl) {
  if (!form) return;
  let box = form.querySelector(".js-inline-validation-alert");
  if (!box) {
    box = document.createElement("div");
    box.className = "js-inline-validation-alert p-3 rounded-xl bg-rose-950/70 border border-rose-700/70 text-xs font-medium text-rose-200";
    const submitRow = form.querySelector('button[type="submit"]')?.closest("div.pt-4") || form;
    if (submitRow && submitRow.parentElement === form) {
      form.insertBefore(box, submitRow);
    } else {
      form.prepend(box);
    }
  }
  box.textContent = message;
  box.classList.remove("hidden");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  if (focusEl && typeof focusEl.focus === "function") {
    focusEl.focus();
  }
}

function _clearFormInlineError(form) {
  const box = form?.querySelector(".js-inline-validation-alert");
  if (box) {
    box.textContent = "";
    box.classList.add("hidden");
  }
}

/**
 * Adapta los campos del formulario de políticas según la categoría seleccionada y valida coherencia.
 */
function initPolicyFormHelper() {
  const typeSelect = document.getElementById("policy_type_select");
  const validFromInput = document.getElementById("valid_from");
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

    // Intermediario e Intermitencia de Accesos
    const targetScopeSelect = document.getElementById("target_scope");
    const targetDomainGroup = document.getElementById("target_domain_group");
    const intermittentCheckbox = document.getElementById("is_intermittent");
    const intermittentSettings = document.getElementById("intermittent_settings");

    if (targetScopeSelect && targetDomainGroup) {
      if (targetScopeSelect.value === "specific_domain") {
        targetDomainGroup.classList.remove("hidden");
      } else {
        targetDomainGroup.classList.add("hidden");
      }
    }

    if (intermittentCheckbox && intermittentSettings) {
      if (typeVal === "intermittent_intermediary") {
        intermittentCheckbox.checked = true;
      }
      const isInter = intermittentCheckbox.checked || typeVal === "intermittent_intermediary";
      if (isInter) {
        intermittentSettings.classList.remove("hidden");
      } else {
        intermittentSettings.classList.add("hidden");
      }
    }
  };

  const targetScopeSelect = document.getElementById("target_scope");
  const intermittentCheckbox = document.getElementById("is_intermittent");
  if (targetScopeSelect) targetScopeSelect.addEventListener("change", updateFields);
  if (intermittentCheckbox) intermittentCheckbox.addEventListener("change", updateFields);

  typeSelect.addEventListener("change", updateFields);
  updateFields();

  // Validación previa en Front-End para evitar envíos incompletos o contradictorios
  const form = typeSelect.closest("form");
  if (form) {
    form.addEventListener("submit", (e) => {
      _clearFormInlineError(form);
      const nameInput = document.getElementById("name");
      const navProfileInput = document.getElementById("navigation_profile");
      const targetDomainInput = document.getElementById("target_domain");
      const activeMinsInput = document.getElementById("interval_active_minutes");
      const pauseMinsInput = document.getElementById("interval_pause_minutes");

      const nameVal = (nameInput?.value || "").trim();
      if (nameVal.length < 3) {
        e.preventDefault();
        _showFormInlineError(form, "Escribe un nombre de al menos 3 letras para identificar esta regla.", nameInput);
        return;
      }

      const typeVal = typeSelect.value;
      const actionVal = actionSelect?.value || "allow";
      const scopeVal = targetScopeSelect?.value || "all_traffic";
      const domainVal = (targetDomainInput?.value || "").trim();
      const navProfileVal = (navProfileInput?.value || "").trim();

      if (typeVal === "navigation_restriction") {
        if (actionVal === "allow") {
          e.preventDefault();
          _showFormInlineError(form, "Para restringir páginas debes elegir 'Limitar / Con filtro familiar' o 'Pausar / Bloquear acceso'.", actionSelect);
          return;
        }
        if (!navProfileVal && !domainVal) {
          e.preventDefault();
          _showFormInlineError(form, "Indica qué sitios o usos deseas limitar en este filtro familiar.", navProfileInput);
          return;
        }
      }

      if (scopeVal === "specific_domain" && !domainVal) {
        e.preventDefault();
        _showFormInlineError(form, "Escribe el dominio o página web que deseas controlar (ejemplo: youtube.com o tiktok.com).", targetDomainInput);
        return;
      }

      const vfVal = (validFromInput?.value || "").trim();
      const vuVal = (validUntilInput?.value || "").trim();
      if (!vfVal) {
        e.preventDefault();
        _showFormInlineError(form, "Elige la fecha y hora desde cuando empieza la regla.", validFromInput);
        return;
      }
      if (typeVal === "temporary_access" && !vuVal) {
        e.preventDefault();
        _showFormInlineError(form, "Para un Permiso Temporal es obligatorio indicar hasta cuándo estará activo.", validUntilInput);
        return;
      }
      if (vfVal && vuVal && vuVal <= vfVal) {
        e.preventDefault();
        _showFormInlineError(form, "La fecha de finalización debe ser posterior a la fecha de inicio.", validUntilInput);
        return;
      }

      if (intermittentCheckbox?.checked || typeVal === "intermittent_intermediary") {
        const am = Number(activeMinsInput?.value || 0);
        const pm = Number(pauseMinsInput?.value || 0);
        if (am < 1 || am > 720 || pm < 1 || pm > 720) {
          e.preventDefault();
          _showFormInlineError(form, "Los minutos de uso y de descanso deben estar entre 1 y 720.", activeMinsInput);
        }
      }
    });
  }
}

/**
 * Analiza en tiempo real la hora inicial y final de un horario, ofrece botones rápidos y valida antes de guardar.
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
        '<strong class="text-rose-400">Atención:</strong> La hora de inicio y de fin no pueden ser exactamente la misma.';
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

  // Validación previa en Front-End para horarios
  const form = startInput.closest("form");
  if (form) {
    form.addEventListener("submit", (e) => {
      _clearFormInlineError(form);
      const labelInput = document.getElementById("label");
      const labelVal = (labelInput?.value || "").trim();
      if (labelVal.length < 3) {
        e.preventDefault();
        _showFormInlineError(form, "Escribe un nombre de al menos 3 letras para reconocer este horario.", labelInput);
        return;
      }

      const checkedDays = form.querySelectorAll('input[name="days_of_week"]:checked');
      if (!checkedDays.length) {
        e.preventDefault();
        _showFormInlineError(form, "Selecciona al menos un día de la semana (o usa los botones rápidos como 'Todos los días').");
        return;
      }

      const s = (startInput.value || "").trim();
      const endV = (endInput.value || "").trim();
      if (!s || !endV || s === endV) {
        e.preventDefault();
        _showFormInlineError(form, "Elige horas válidas y diferentes para el inicio y el fin del horario.", endInput);
      }
    });
  }
}

/**
 * Añade indicador visual de procesamiento al enviar formularios.
 */
function initSubmitLoadingIndicator() {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented) {
        return;
      }
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

/**
 * Permite mostrar u ocultar contraseñas con botón de ojo interactivo.
 */
function initPasswordToggles() {
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-toggle-password");
      const input = document.getElementById(targetId);
      if (!input) return;

      const eyeOpen = btn.querySelector(".eye-open");
      const eyeClosed = btn.querySelector(".eye-closed");

      if (input.type === "password") {
        input.type = "text";
        btn.setAttribute("title", "Ocultar contraseña");
        if (eyeOpen) eyeOpen.classList.add("hidden");
        if (eyeClosed) eyeClosed.classList.remove("hidden");
      } else {
        input.type = "password";
        btn.setAttribute("title", "Mostrar contraseña");
        if (eyeOpen) eyeOpen.classList.remove("hidden");
        if (eyeClosed) eyeClosed.classList.add("hidden");
      }
    });
  });
}

/**
 * Controla las pestañas de la Ficha Técnica Unificada (Ficha, Editor y Control Familiar).
 */
function initDeviceDetailTabs() {
  const tabBtns = document.querySelectorAll("[data-tab-target]");
  if (!tabBtns.length) return;

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab-target");

      // Actualizar estado visual de los botones de pestañas
      tabBtns.forEach((b) => {
        b.classList.remove("border-blue-500", "text-blue-400");
        b.classList.add("border-transparent", "theme-text-secondary");
      });
      btn.classList.add("border-blue-500", "text-blue-400");
      btn.classList.remove("border-transparent", "theme-text-secondary");

      // Mostrar el contenedor correspondiente
      document.querySelectorAll(".tab-content").forEach((panel) => {
        panel.classList.add("hidden");
      });
      const activePanel = document.getElementById(targetId);
      if (activePanel) {
        activePanel.classList.remove("hidden");
      }

      // Actualizar URL amigable sin recargar la página
      const tabParam = targetId.replace("tab-", "");
      const newUrl = new URL(window.location);
      newUrl.searchParams.set("tab", tabParam);
      window.history.replaceState({}, "", newUrl);
    });
  });
}

/**
 * Inicializa el control de entrada de direccion IP segmentada con puntos fijos.
 * Garantiza que los tres puntos (.) permanezcan fijos e inmutables, permitiendo
 * al usuario ingresar unicamente los numeros correspondientes a cada octeto (0-255).
 * Soporta auto-avance por longitud, navegacion con flechas, retroceso inteligente y pegado.
 */
function initIpSegmentedInputs() {
  const containers = document.querySelectorAll("[data-ip-segmented='true']");
  if (!containers.length) return;

  containers.forEach((container) => {
    const targetHiddenId = container.getAttribute("data-target-input");
    const hiddenInput = document.getElementById(targetHiddenId);
    if (!hiddenInput) return;

    const octetInputs = container.querySelectorAll(".ip-octet-field");
    if (octetInputs.length !== 4) return;

    // Sincroniza desde el valor inicial del input oculto o prefijo predeterminado
    const populateFromHidden = () => {
      const currentVal = (hiddenInput.value || "").trim();
      if (currentVal) {
        const parts = currentVal.split(".");
        parts.forEach((part, idx) => {
          if (idx < 4 && octetInputs[idx]) {
            octetInputs[idx].value = part.replace(/\D/g, "").slice(0, 3);
          }
        });
      } else {
        const defaultPrefix = container.getAttribute("data-default-prefix");
        if (defaultPrefix) {
          const prefixParts = defaultPrefix.split(".").filter(Boolean);
          prefixParts.forEach((part, idx) => {
            if (idx < 3 && octetInputs[idx]) {
              octetInputs[idx].value = part;
            }
          });
        }
      }
    };

    // Actualiza el valor del input oculto y dispara eventos de validacion reactiva
    const updateHidden = () => {
      const values = Array.from(octetInputs).map((inp) => inp.value.trim());
      const hasAnyValue = values.some((v) => v !== "");
      if (!hasAnyValue) {
        hiddenInput.value = "";
      } else {
        hiddenInput.value = values.join(".");
      }
      hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
      hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    };

    populateFromHidden();
    // Actualizar hidden si se precargo prefijo
    if (!hiddenInput.value && Array.from(octetInputs).some((i) => i.value !== "")) {
      updateHidden();
    }

    octetInputs.forEach((input, index) => {
      // Filtrar estrictamente solo digitos
      input.addEventListener("input", () => {
        let val = input.value.replace(/\D/g, "");
        if (val.length > 3) val = val.slice(0, 3);
        if (val !== "" && Number(val) > 255) {
          val = "255";
        }
        input.value = val;
        updateHidden();

        // Auto-avance: si el usuario escribio 3 digitos, saltar inmediatamente al siguiente octeto
        if (val.length === 3 && index < 3) {
          octetInputs[index + 1].focus();
          octetInputs[index + 1].select();
        }
      });

      // Manejo ergonomico de teclado
      input.addEventListener("keydown", (e) => {
        // Al teclear punto (.) o espacio, avanzar al siguiente octeto
        if (e.key === "." || e.key === " " || e.key === "Decimal") {
          e.preventDefault();
          if (index < 3) {
            octetInputs[index + 1].focus();
            octetInputs[index + 1].select();
          }
          return;
        }

        // Al presionar retroceso (Backspace) en un octeto vacio, regresar al anterior
        if (e.key === "Backspace" && input.value === "" && index > 0) {
          e.preventDefault();
          const prev = octetInputs[index - 1];
          prev.focus();
          const len = prev.value.length;
          prev.setSelectionRange(len, len);
          return;
        }

        // Flecha izquierda al inicio del octeto
        if (e.key === "ArrowLeft" && input.selectionStart === 0 && index > 0) {
          e.preventDefault();
          const prev = octetInputs[index - 1];
          prev.focus();
          prev.setSelectionRange(prev.value.length, prev.value.length);
          return;
        }

        // Flecha derecha al final del octeto
        if (e.key === "ArrowRight" && input.selectionEnd === input.value.length && index < 3) {
          e.preventDefault();
          const next = octetInputs[index + 1];
          next.focus();
          next.setSelectionRange(0, 0);
          return;
        }
      });

      // Pegar direccion IP completa (ej. 192.168.1.50)
      input.addEventListener("paste", (e) => {
        e.preventDefault();
        const pastedText = (e.clipboardData || window.clipboardData).getData("text") || "";
        const parts = pastedText.trim().split(/[.\s]+/);
        if (parts.length >= 2) {
          parts.slice(0, 4).forEach((part, pIdx) => {
            const targetIdx = index + pIdx;
            if (targetIdx < 4) {
              let num = part.replace(/\D/g, "").slice(0, 3);
              if (num !== "" && Number(num) > 255) num = "255";
              octetInputs[targetIdx].value = num;
            }
          });
          updateHidden();
          const lastIdx = Math.min(3, index + parts.length - 1);
          octetInputs[lastIdx].focus();
        } else if (parts.length === 1) {
          let num = parts[0].replace(/\D/g, "").slice(0, 3);
          if (num !== "" && Number(num) > 255) num = "255";
          input.value = num;
          updateHidden();
          if (num.length === 3 && index < 3) {
            octetInputs[index + 1].focus();
            octetInputs[index + 1].select();
          }
        }
      });

      // Seleccionar texto completo al recibir foco para agilizar la edicion
      input.addEventListener("focus", () => {
        input.select();
      });
    });

    // Clic en el contenedor fuera de los inputs enfoca el primer octeto vacio o el ultimo
    container.addEventListener("click", (e) => {
      if (e.target === container || e.target.classList.contains("ip-dot-separator")) {
        const firstEmpty = Array.from(octetInputs).find((inp) => inp.value === "") || octetInputs[3];
        firstEmpty.focus();
      }
    });
  });
}

/**
 * Comprueba si una dirección IPv4 pertenece a una subred CIDR dada (operación bit a bit).
 */
function isIpInCidr(ipStr, cidrStr) {
  try {
    const [netIp, prefixRaw] = (cidrStr || "").split("/");
    const prefix = Number(prefixRaw);
    if (!netIp || isNaN(prefix) || prefix < 0 || prefix > 32) return false;
    const toInt = (s) => s.split(".").reduce((acc, oct) => (acc << 8) + Number(oct), 0) >>> 0;
    const mask = prefix === 0 ? 0 : (~0 << (32 - prefix)) >>> 0;
    return (toInt(ipStr) & mask) === (toInt(netIp) & mask);
  } catch {
    return false;
  }
}

/**
 * Comprueba si una IP pertenece a bloques privados RFC 1918 (10/8, 172.16/12, 192.168/16).
 */
function isPrivateRfc1918Ip(parts) {
  const a = Number(parts[0]);
  const b = Number(parts[1]);
  return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

/**
 * Validaciones reactivas en Front-End para Direcciones IP RFC 1918, Subred CIDR y Direcciones MAC.
 */
function initLiveNetworkValidators() {
  const scopeInput = document.getElementById("network_scope") || document.getElementById("editor_network_scope");

  const isValidCidr = (raw) => {
    const parts = (raw || "").trim().split("/");
    if (parts.length !== 2) return false;
    const octs = parts[0].split(".");
    const prefix = Number(parts[1]);
    return (
      octs.length === 4 &&
      octs.every((p) => p !== "" && !isNaN(p) && Number(p) >= 0 && Number(p) <= 255) &&
      !isNaN(prefix) &&
      Number.isInteger(prefix) &&
      prefix >= 0 &&
      prefix <= 32
    );
  };

  // Validación reactiva de IP
  const ipInputs = document.querySelectorAll('[data-validate-ip="true"], #ip_address, #editor_ip_address');
  ipInputs.forEach((input) => {
    // Detectar si el input esta asociado a un contenedor segmentado con puntos fijos
    const container = document.querySelector(`[data-target-input="${input.id}"]`);
    const visualElement = container || input;

    // Buscar caja de retroalimentacion contextual
    const feedbackBox = input.closest(".ip-segmented-wrapper")?.parentElement?.querySelector("#ip_feedback_box") ||
                        input.parentElement?.querySelector("#ip_feedback_box") ||
                        document.getElementById("ip_feedback_box");

    const validateCurrentIp = () => {
      const val = input.value.trim();
      if (!val) {
        visualElement.classList.remove("border-emerald-500", "border-rose-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 theme-text-muted";
          feedbackBox.textContent = "Ingrese la dirección IP privada del dispositivo.";
        }
        return false;
      }

      const parts = val.split(".");
      const isValidShape = parts.length === 4 && parts.every((p) => p !== "" && !isNaN(p) && Number(p) >= 0 && Number(p) <= 255);

      if (!isValidShape) {
        visualElement.classList.add("border-rose-500");
        visualElement.classList.remove("border-emerald-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-rose-400 font-medium";
          feedbackBox.textContent = "Formato IP incompleto. Deben completarse los 4 números (0-255).";
        }
        return false;
      }

      // Si el ámbito está en modo automático y se ingresa una IP privada de otro módem/hotspot, adaptar a /24
      if (
        scopeInput &&
        scopeInput.getAttribute("data-auto-scope") === "true" &&
        isPrivateRfc1918Ip(parts) &&
        !isIpInCidr(val, scopeInput.value.trim())
      ) {
        const adaptedScope = `${parts[0]}.${parts[1]}.${parts[2]}.0/24`;
        scopeInput.value = adaptedScope;
        const scopeLabel = document.getElementById("ip_expected_scope_label");
        if (scopeLabel) scopeLabel.textContent = adaptedScope;
      }

      const lastOctet = Number(parts[3]);
      const currentScope = scopeInput ? scopeInput.value.trim() : "";
      if (lastOctet === 1) {
        visualElement.classList.add("border-amber-500");
        visualElement.classList.remove("border-emerald-500", "border-rose-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-amber-400 font-semibold";
          feedbackBox.textContent = "Atención: La dirección terminada en .1 suele ser el Router o Mini-Módem y no debe asignarse a un equipo cliente.";
        }
      } else if (lastOctet === 0 || lastOctet === 255) {
        visualElement.classList.add("border-rose-500");
        visualElement.classList.remove("border-emerald-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-rose-400 font-semibold";
          feedbackBox.textContent = "Dirección no asignable: .0 es la dirección de red y .255 es la dirección de broadcast.";
        }
        return false;
      } else if (currentScope && isValidCidr(currentScope) && !isIpInCidr(val, currentScope)) {
        visualElement.classList.add("border-rose-500");
        visualElement.classList.remove("border-emerald-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-rose-400 font-semibold";
          feedbackBox.textContent = `La IP ${val} no pertenece a la subred ${currentScope}.`;
        }
        return false;
      } else {
        visualElement.classList.add("border-emerald-500");
        visualElement.classList.remove("border-rose-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-emerald-400 font-medium";
          feedbackBox.textContent = currentScope
            ? `Dirección IP válida para la subred ${currentScope}.`
            : "Dirección IP válida y conforme a rangos privados RFC 1918.";
        }
      }
      return true;
    };

    input.addEventListener("input", validateCurrentIp);

    if (scopeInput) {
      scopeInput.addEventListener("input", () => {
        scopeInput.setAttribute("data-auto-scope", "false");
        const scopeVal = scopeInput.value.trim();
        if (!scopeVal || isValidCidr(scopeVal)) {
          scopeInput.classList.remove("border-rose-500");
        } else {
          scopeInput.classList.add("border-rose-500");
        }
        if (input.value.trim()) {
          validateCurrentIp();
        }
      });
    }

    const form = input.closest("form");
    if (form && !form.dataset.confirmMessage) {
      form.addEventListener("submit", (e) => {
        _clearFormInlineError(form);
        const nameField = form.querySelector('[name="name"]');
        if (nameField && (nameField.value || "").trim().length < 2) {
          e.preventDefault();
          _showFormInlineError(form, "Escribe un nombre reconocible para este equipo.", nameField);
          return;
        }
        if (!validateCurrentIp()) {
          e.preventDefault();
          _showFormInlineError(form, "Revisa la dirección IP: debe tener 4 números válidos y pertenecer al ámbito de red configurado.", visualElement);
          return;
        }
        if (scopeInput && !isValidCidr(scopeInput.value)) {
          e.preventDefault();
          _showFormInlineError(form, "El ámbito de red (CIDR) debe tener formato válido (ejemplo: 192.168.1.0/24).", scopeInput);
          return;
        }
        const macField = form.querySelector('[name="mac_address"]');
        const macRaw = (macField?.value || "").replace(/[^0-9A-Fa-f]/g, "");
        if (macField && macRaw.length > 0 && macRaw.length !== 12) {
          e.preventDefault();
          _showFormInlineError(form, "La dirección MAC es opcional, pero si la escribes debe tener exactamente 12 caracteres hexadecimales.", macField);
        }
      });
    }
  });

  // Validación y auto-formateo reactivo de MAC
  const macInputs = document.querySelectorAll('[data-validate-mac="true"], #mac_address, #editor_mac_address');
  macInputs.forEach((input) => {
    const feedbackBox = document.getElementById("mac_feedback_box");
    input.addEventListener("input", (e) => {
      let raw = input.value.replace(/[^0-9A-Fa-f]/g, "").toUpperCase();
      if (raw.length > 12) raw = raw.slice(0, 12);

      // Auto-insertar dos puntos
      const formatted = raw.match(/.{1,2}/g)?.join(":") || "";
      input.value = formatted;

      if (!formatted) {
        input.classList.remove("border-emerald-500", "border-rose-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 theme-text-muted";
          feedbackBox.textContent = "Formato estándar de 6 pares hexadecimales separados por dos puntos (Opcional).";
        }
        return;
      }

      if (raw.length === 12) {
        input.classList.add("border-emerald-500");
        input.classList.remove("border-rose-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-emerald-400 font-medium";
          feedbackBox.textContent = "Dirección MAC física válida de 48 bits (Capa de Enlace).";
        }
      } else {
        input.classList.add("border-rose-500");
        input.classList.remove("border-emerald-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-rose-400 font-medium";
          feedbackBox.textContent = `Dirección MAC incompleta (${raw.length}/12 caracteres hexadecimales).`;
        }
      }
    });
  });
}

/**
 * Controla el modal de alta rápida de Categorías Dinámicas (Admin y Superadmin).
 */
function initCategoryQuickAddModal() {
  const modal = document.getElementById("category-modal");
  const closeBtn = document.getElementById("category-modal-close");
  const cancelBtn = document.getElementById("category-modal-cancel");
  const form = document.getElementById("category-quick-form");
  const typeInput = document.getElementById("modal-category-type");
  const nameInput = document.getElementById("modal-category-name");
  const descInput = document.getElementById("modal-category-desc");
  const errorBox = document.getElementById("modal-category-error");
  const titleEl = document.getElementById("category-modal-title");

  if (!modal || !form) return;

  const closeModal = () => {
    modal.classList.add("hidden");
    if (errorBox) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
    }
    if (nameInput) nameInput.value = "";
    if (descInput) descInput.value = "";
  };

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  // Abrir modal configurando el tipo
  document.querySelectorAll("[data-open-category-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const catType = btn.getAttribute("data-open-category-modal") || "device_type";
      if (typeInput) typeInput.value = catType;

      if (titleEl) {
        if (catType === "device_type") {
          titleEl.textContent = "Nueva Categoría de Dispositivo";
        } else if (catType === "device_profile") {
          titleEl.textContent = "Nuevo Perfil Familiar de Red";
        } else if (catType === "admin_status") {
          titleEl.textContent = "Nuevo Permiso / Estado de Acceso";
        } else {
          titleEl.textContent = "Nueva Categoría del Sistema";
        }
      }

      modal.classList.remove("hidden");
      if (nameInput) setTimeout(() => nameInput.focus(), 50);
    });
  });

  // Envío AJAX
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (errorBox) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
    }

    const catType = typeInput ? typeInput.value : "device_type";
    const nameVal = nameInput ? nameInput.value.trim() : "";
    const descVal = descInput ? descInput.value.trim() : "";
    const csrfToken = form.querySelector('input[name="csrf_token"]')?.value || "";

    if (!nameVal) {
      if (errorBox) {
        errorBox.textContent = "El nombre de la categoría es obligatorio.";
        errorBox.classList.remove("hidden");
      }
      return;
    }

    try {
      const response = await fetch("/categories/quick-add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          category_type: catType,
          name: nameVal,
          description: descVal,
          csrf_token: csrfToken,
        }),
      });

      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.error || "Fallo al registrar la categoría.");
      }

      const created = result.category;

      // Inyectar la nueva opción en los selectores correspondientes
      let targetSelectIds = [];
      if (catType === "device_type") {
        targetSelectIds = ["device_type", "editor_device_type"];
      } else if (catType === "device_profile") {
        targetSelectIds = ["profile", "editor_profile"];
      } else if (catType === "admin_status") {
        targetSelectIds = ["admin_status", "editor_admin_status"];
      }

      targetSelectIds.forEach((id) => {
        const selectEl = document.getElementById(id);
        if (selectEl) {
          const newOpt = document.createElement("option");
          newOpt.value = created.code;
          newOpt.textContent = created.name;
          newOpt.selected = true;
          selectEl.appendChild(newOpt);
        }
      });

      closeModal();
    } catch (err) {
      if (errorBox) {
        errorBox.textContent = err.message || "Error al procesar la solicitud.";
        errorBox.classList.remove("hidden");
      }
    }
  });
}

/**
 * Controla los menús contextuales desplegables de acciones (tipo hamburguesa)
 * en las tablas del sistema para evitar dispersión horizontal de botones.
 */
function initTableActionMenus() {
  let activeMenu = null;
  let activeBtn = null;

  const closeAllMenus = () => {
    document.querySelectorAll(".action-dropdown-menu").forEach((m) => {
      m.classList.add("hidden");
    });
    document.querySelectorAll(".action-dropdown-btn").forEach((btn) => {
      btn.setAttribute("aria-expanded", "false");
    });
    activeMenu = null;
    activeBtn = null;
  };

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".action-dropdown-btn");
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      const container = btn.closest(".action-dropdown-container");
      const menu = container ? container.querySelector(".action-dropdown-menu") : null;
      if (!menu) return;

      const isCurrentlyOpen = !menu.classList.contains("hidden");
      closeAllMenus();

      if (!isCurrentlyOpen) {
        menu.classList.remove("hidden");
        btn.setAttribute("aria-expanded", "true");
        activeMenu = menu;
        activeBtn = btn;

        // Posicionamiento flotante relativo al botón disparador
        const rect = btn.getBoundingClientRect();
        const menuWidth = 180;
        menu.style.position = "fixed";
        menu.style.top = `${rect.bottom + 6}px`;
        const calculatedLeft = rect.right - menuWidth;
        menu.style.left = `${Math.max(12, calculatedLeft)}px`;
      }
      return;
    }

    if (activeMenu && !e.target.closest(".action-dropdown-menu")) {
      closeAllMenus();
    }
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllMenus();
  });
  window.addEventListener("scroll", closeAllMenus, true);
  window.addEventListener("resize", closeAllMenus);
}

function _escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function _getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
}

/**
 * Gestiona las acciones en tiempo real del Monitor de Red y Pruebas ICMP Ping.
 */
function initLiveNetworkMonitor() {
  // Copiar URL móvil al portapapeles
  document.querySelectorAll("[data-copy-target]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetId = btn.getAttribute("data-copy-target");
      const targetEl = document.getElementById(targetId);
      if (!targetEl) return;
      const text = targetEl.textContent.trim();
      try {
        await navigator.clipboard.writeText(text);
        const orig = btn.textContent;
        btn.textContent = "Copiado";
        setTimeout(() => { btn.textContent = orig; }, 1600);
      } catch {
        // Fallback silencioso
      }
    });
  });

  // Botón de Ping individual en ficha técnica del dispositivo
  const detailPingBtn = document.getElementById("btn-detail-ping");
  const detailPingBox = document.getElementById("detail-ping-result");
  if (detailPingBtn && detailPingBox) {
    detailPingBtn.addEventListener("click", async () => {
      const ip = detailPingBtn.getAttribute("data-ip");
      const devId = detailPingBtn.getAttribute("data-device-id");
      const origText = detailPingBtn.textContent;
      detailPingBtn.disabled = true;
      detailPingBtn.textContent = "Comprobando...";
      detailPingBox.textContent = `Enviando paquete ICMP hacia ${ip}...`;

      try {
        const resp = await fetch("/network/ping", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": _getCsrfToken(),
          },
          body: JSON.stringify({ ip_address: ip, device_id: devId, record_audit: true }),
        });
        const data = await resp.json();
        if (resp.ok && data.success) {
          detailPingBox.className = data.online ? "text-xs font-semibold text-emerald-400" : "text-xs font-semibold text-rose-400";
          detailPingBox.textContent = `${data.detail} (Comprobado a las ${data.checked_at})`;
        } else {
          detailPingBox.className = "text-xs text-rose-400";
          detailPingBox.textContent = data.error || "No se pudo realizar la prueba.";
        }
      } catch {
        detailPingBox.className = "text-xs text-rose-400";
        detailPingBox.textContent = "Error de comunicación con el servidor.";
      } finally {
        detailPingBtn.disabled = false;
        detailPingBtn.textContent = origText;
      }
    });
  }

  // Botones de Ping en tarjetas del Monitor de Red
  const attachPingHandlers = () => {
    document.querySelectorAll(".btn-ping-host").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ip = btn.getAttribute("data-ip");
        const card = btn.closest("[data-host-ip]");
        const badge = card ? card.querySelector(".host-online-badge") : null;
        const orig = btn.textContent;
        btn.disabled = true;
        btn.textContent = "Verificando...";

        try {
          const resp = await fetch("/network/ping", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": _getCsrfToken(),
            },
            body: JSON.stringify({ ip_address: ip }),
          });
          const data = await resp.json();
          if (badge && data.success) {
            if (data.online) {
              badge.className = "host-online-badge px-2.5 py-0.5 rounded-full text-[11px] font-semibold shrink-0 bg-emerald-950 text-emerald-300 border border-emerald-700/60";
              badge.textContent = data.latency_ms !== null ? `En línea (${data.latency_ms} ms)` : "En línea";
              if (card) card.classList.add("border-emerald-700/50");
            } else {
              badge.className = "host-online-badge px-2.5 py-0.5 rounded-full text-[11px] font-semibold shrink-0 bg-rose-950 text-rose-300 border border-rose-700/60";
              badge.textContent = "Sin respuesta";
              if (card) card.classList.remove("border-emerald-700/50");
            }
          }
        } catch {
          // Ignorar error transitorio
        } finally {
          btn.disabled = false;
          btn.textContent = orig;
        }
      });
    });
  };
  attachPingHandlers();

  // Escaneo completo ARP + Ping Sweep
  const scanButtons = [
    document.getElementById("btn-live-scan"),
    document.getElementById("btn-live-scan-top"),
  ].filter(Boolean);
  const grid = document.getElementById("discovered-devices-grid");
  const subtitleEl = document.getElementById("scan-status-subtitle");

  if (scanButtons.length && grid) {
    const runScan = async () => {
      scanButtons.forEach((b) => {
        b.disabled = true;
        b.dataset.origText = b.textContent;
        b.textContent = "Buscando equipos...";
      });
      if (subtitleEl) {
        subtitleEl.textContent = "Buscando celulares, computadoras y pantallas conectadas a tu red Wi-Fi...";
      }

      try {
        const resp = await fetch("/network/scan", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": _getCsrfToken(),
          },
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) throw new Error("Error de escaneo");

        const netScope = data.network_info?.network_scope || "192.168.1.0/24";
        if (subtitleEl) {
          subtitleEl.textContent = `Actualizado a las ${data.scanned_at}: ${data.online_count} conectado(s) ahora, ${data.discovered.length} visible(s).`;
        }

        if (!data.discovered.length) {
          grid.innerHTML = `<div class="col-span-full py-8 text-center text-xs theme-text-muted border border-dashed border-slate-800 rounded-xl">No se detectaron otros equipos en este momento.</div>`;
        } else {
          grid.innerHTML = data.discovered
            .map((host) => {
              const title = host.registered_device ? host.registered_device.name : host.suggested_name;
              const badgeCls = host.is_online
                ? "bg-emerald-950 text-emerald-300 border border-emerald-700/60"
                : "bg-slate-800 theme-text-muted";
              const badgeTxt = host.is_online
                ? host.latency_ms !== null
                  ? `Conectado (${host.latency_ms} ms)`
                  : "Conectado"
                : "En reposo";

              const roleTag = host.is_this_server
                ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-950 text-blue-300 border border-blue-800/60">Esta PC</span>'
                : host.is_gateway
                ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800/60">Módem Wi-Fi</span>'
                : "";

              const dbTag = host.registered_device
                ? `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-700/60">En tu lista (${_escapeHtml(host.registered_device.admin_status_label)})</span>`
                : '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 theme-text-secondary">Nuevo en Wi-Fi</span>';

              const canModify = grid.getAttribute("data-can-modify") === "true";
              let actionLink = "";
              if (host.registered_device) {
                const devHref = canModify
                  ? `/devices/${encodeURIComponent(host.registered_device.id)}?tab=family`
                  : `/devices/${encodeURIComponent(host.registered_device.id)}`;
                const devBtnLabel = canModify ? "Controlar Internet" : "Ver Ficha";
                actionLink = `<a href="${devHref}" class="btn-primary text-xs py-1.5 px-2.5 flex-1 text-center">${devBtnLabel}</a>`;
              } else if (canModify && !host.is_gateway) {
                const params = new URLSearchParams({
                  ip: host.ip_address || "",
                  mac: host.mac_address || "",
                  hostname: host.hostname || "",
                  scope: netScope,
                  name: host.suggested_name || "",
                  device_type: host.suggested_type || "smartphone",
                });
                actionLink = `<a href="/devices/new?${params.toString()}" class="btn-primary text-xs py-1.5 px-2.5 flex-1 text-center">+ Registrar Equipo</a>`;
              }

              return `
                <div class="surface-subtle p-4 flex flex-col justify-between space-y-3 border ${host.is_online ? "border-emerald-700/50" : "border-slate-800"}" data-host-ip="${_escapeHtml(host.ip_address)}">
                  <div class="space-y-2">
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <div class="font-bold text-sm theme-text-primary truncate">${_escapeHtml(title)}</div>
                        <div class="font-mono-code text-xs theme-text-secondary mt-0.5">${_escapeHtml(host.ip_address)}</div>
                      </div>
                      <span class="host-online-badge px-2.5 py-0.5 rounded-full text-[11px] font-semibold shrink-0 ${badgeCls}">${_escapeHtml(badgeTxt)}</span>
                    </div>
                    <div class="text-xs theme-text-muted space-y-1">
                      ${host.mac_address ? `<div>MAC: <span class="font-mono-code theme-text-secondary">${_escapeHtml(host.mac_address)}</span></div>` : ""}
                      <div class="flex flex-wrap gap-1.5 pt-0.5">${roleTag}${dbTag}</div>
                    </div>
                  </div>
                  <div class="pt-2 border-t border-slate-800/80 flex flex-wrap items-center gap-2">
                    <button type="button" class="btn-secondary text-xs py-1.5 px-2.5 btn-ping-host" data-ip="${_escapeHtml(host.ip_address)}">Verificar Señal</button>
                    ${actionLink}
                  </div>
                </div>
              `;
            })
            .join("");
          attachPingHandlers();
        }
      } catch {
        if (subtitleEl) subtitleEl.textContent = "No se pudo completar la búsqueda de equipos.";
      } finally {
        scanButtons.forEach((b) => {
          b.disabled = false;
          b.textContent = b.dataset.origText || "Buscar Equipos";
        });
      }
    };

    scanButtons.forEach((btn) => btn.addEventListener("click", runScan));
  }

  // Auto-refresco de conexiones interceptadas por el Proxy Intermediario
  const proxyEventsBox = document.getElementById("proxy-live-events");
  if (proxyEventsBox) {
    const refreshProxyLogs = async () => {
      try {
        const resp = await fetch("/network/proxy-logs", { cache: "no-store" });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.success) return;
        const items = data.recent_events || [];
        if (!items.length) return;
        proxyEventsBox.innerHTML = items
          .slice(0, 10)
          .map((ev) => {
            const pillCls = ev.allowed
              ? "bg-emerald-950 text-emerald-300 border border-emerald-700/60"
              : "bg-rose-950 text-rose-300 border border-rose-700/60";
            const pillTxt = ev.allowed ? "PERMITIDO" : "BLOQUEADO";
            return `
              <div class="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded bg-slate-900/60 border border-slate-800">
                <div class="min-w-0 truncate">
                  <span class="font-mono-code text-[11px] theme-text-muted">${_escapeHtml(ev.time)}</span>
                  <strong class="theme-text-primary ml-1">${_escapeHtml(ev.device_name)}</strong>
                  <span class="theme-text-secondary">&rarr;</span>
                  <span class="font-mono-code theme-text-primary">${_escapeHtml(ev.host)}</span>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-bold shrink-0 ${pillCls}">${pillTxt}</span>
              </div>
            `;
          })
          .join("");
      } catch {
        // Silencioso en caso de microcorte
      }
    };
    setInterval(refreshProxyLogs, 2500);
  }

  // Generador de QR Wi-Fi sin guardar contrasena
  const wifiQrForm = document.getElementById("wifi-qr-form");
  const wifiQrPreview = document.getElementById("wifi-qr-preview-box");
  const wifiQrError = document.getElementById("wifi-qr-error");
  if (wifiQrForm && wifiQrPreview) {
    wifiQrForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (wifiQrError) {
        wifiQrError.classList.add("hidden");
        wifiQrError.textContent = "";
      }
      const ssid = document.getElementById("wifi_qr_ssid")?.value.trim() || "";
      const password = document.getElementById("wifi_qr_password")?.value || "";
      const security = document.getElementById("wifi_qr_security")?.value || "WPA";

      try {
        const resp = await fetch("/network/wifi-qr", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": _getCsrfToken(),
          },
          body: JSON.stringify({ ssid, password, security }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
          throw new Error(data.error || "No se pudo generar el QR.");
        }
        wifiQrPreview.innerHTML = data.qr_svg;
      } catch (err) {
        if (wifiQrError) {
          wifiQrError.textContent = err.message || "Error al generar el QR Wi-Fi.";
          wifiQrError.classList.remove("hidden");
        }
      }
    });
  }
}

/**
 * Refresca automáticamente cada 3 segundos la vista móvil /network/mi-acceso
 * para demostrar cambios en tiempo real desde otro teléfono conectado al mini-módem.
 */
function initClientLiveStatusPoller() {
  const root = document.getElementById("client-live-status-root");
  if (!root) return;

  const targetIp = root.getAttribute("data-target-ip") || "";
  const clockEl = document.getElementById("live-clock-badge");
  const bannerEl = document.getElementById("verdict-banner");
  const labelEl = document.getElementById("verdict-label");
  const reasonEl = document.getElementById("verdict-reason");
  const intBox = document.getElementById("intermittent-live-box");
  const intCountdown = document.getElementById("intermittent-countdown");
  const intPhaseLabel = document.getElementById("intermittent-phase-label");
  const intBar = document.getElementById("intermittent-progress-bar");
  const refreshBtn = document.getElementById("btn-refresh-client-status");

  const colorClasses = {
    emerald: "p-4 rounded-2xl border space-y-2 bg-emerald-950/70 border-emerald-700/70 text-emerald-200",
    amber: "p-4 rounded-2xl border space-y-2 bg-amber-950/70 border-amber-700/70 text-amber-200",
    rose: "p-4 rounded-2xl border space-y-2 bg-rose-950/70 border-rose-700/70 text-rose-200",
    cyan: "p-4 rounded-2xl border space-y-2 bg-cyan-950/70 border-cyan-700/70 text-cyan-200",
    slate: "p-4 rounded-2xl border space-y-2 bg-slate-800/80 border-slate-700 text-slate-200",
  };

  const fetchUpdate = async () => {
    try {
      const qs = targetIp ? `?ip=${encodeURIComponent(targetIp)}` : "";
      const resp = await fetch(`/network/api/evaluate${qs}`, { cache: "no-store" });
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.success) return;

      if (clockEl) clockEl.textContent = data.evaluated_at;
      if (bannerEl) bannerEl.className = colorClasses[data.verdict_color] || colorClasses.slate;
      if (labelEl) labelEl.textContent = data.verdict_label;
      if (reasonEl) reasonEl.textContent = data.reason;

      if (intBox) {
        if (data.intermittent_status) {
          intBox.classList.remove("hidden");
          if (intCountdown) intCountdown.textContent = data.intermittent_status.remaining_mmss;
          if (intPhaseLabel) {
            intPhaseLabel.textContent = `${data.intermittent_status.phase_label} — ${data.intermittent_status.target}`;
          }
          if (intBar) intBar.style.width = `${data.intermittent_status.progress_percent}%`;
        } else {
          intBox.classList.add("hidden");
        }
      }
    } catch {
      // Silencioso en caso de microcorte Wi-Fi
    }
  };

  if (refreshBtn) refreshBtn.addEventListener("click", fetchUpdate);
  setInterval(fetchUpdate, 3000);
}
