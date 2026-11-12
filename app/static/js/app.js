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
  initPasswordToggles();
  initDeviceDetailTabs();
  initIpSegmentedInputs();
  initLiveNetworkValidators();
  initCategoryQuickAddModal();
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
 * Validaciones reactivas en Front-End para Direcciones IP RFC 1918 y Direcciones MAC.
 */
function initLiveNetworkValidators() {
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

    input.addEventListener("input", () => {
      const val = input.value.trim();
      if (!val) {
        visualElement.classList.remove("border-emerald-500", "border-rose-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 theme-text-muted";
          feedbackBox.textContent = "Ingrese la dirección IP privada del dispositivo (ej. 192.168.1.50).";
        }
        return;
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
        return;
      }

      const lastOctet = Number(parts[3]);
      if (lastOctet === 1) {
        visualElement.classList.add("border-amber-500");
        visualElement.classList.remove("border-emerald-500", "border-rose-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-amber-400 font-semibold";
          feedbackBox.textContent = "Atención: La dirección terminada en .1 suele ser el Router doméstico y no debe asignarse a un dispositivo.";
        }
      } else if (lastOctet === 0 || lastOctet === 255) {
        visualElement.classList.add("border-rose-500");
        visualElement.classList.remove("border-emerald-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-rose-400 font-semibold";
          feedbackBox.textContent = "Dirección no asignable: .0 es la dirección de red y .255 es la dirección de broadcast.";
        }
      } else {
        visualElement.classList.add("border-emerald-500");
        visualElement.classList.remove("border-rose-500", "border-amber-500");
        if (feedbackBox) {
          feedbackBox.className = "text-[11px] mt-1 text-emerald-400 font-medium";
          feedbackBox.textContent = "Dirección IP válida y conforme a los rangos privados RFC 1918.";
        }
      }
    });
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
      const targetSelectIds =
        catType === "device_type"
          ? ["device_type", "editor_device_type"]
          : ["profile", "editor_profile"];

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
