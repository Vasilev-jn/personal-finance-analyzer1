let trendChart;
const SYS_COLORS = ["#A55DE8", "#5BB4FF", "#FFB86B", "#FF8FA3", "#7C4DFF", "#4EC2FF", "#6FCF97", "#F2C94C"];

const BANK_ICONS = {
  alfa:    `<img class="bank-icon" src="/static/bank_icons/alfa.png" alt="Альфа">`,
  tinkoff: `<img class="bank-icon" src="/static/bank_icons/tinkoff.png" alt="Тинькофф">`,
  sber:    `<img class="bank-icon" src="/static/bank_icons/sber.png" alt="Сбер">`,
  vtb:     `<img class="bank-icon" src="/static/bank_icons/vtb.png" alt="ВТБ">`,
};

const BANK_IMPORT_FORMATS = {
  alfa: { label: "CSV", accept: ".csv", extensions: [".csv"] },
  tinkoff: { label: "CSV", accept: ".csv", extensions: [".csv"] },
  sber: { label: "Excel", accept: ".xls,.xlsx", extensions: [".xls", ".xlsx"] },
  vtb: { label: "PDF", accept: ".pdf", extensions: [".pdf"] },
};

const state = {
  expense: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  income: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  transfers: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  subscriptions: { selected: null, items: [], operations: [] },
  analytics: null,
  homeAnalytics: null,
  mainTransferChart: null,
  mainTransfersMode: "base",
  mainTransfersSelected: null,
  mainTransfersMerchants: [],
  expenseTopN: 5,
  expenseFilterCategory: null,
  expenseDynMode: "month",
  expenseCharts: { top: null, dynamics: null, cumulative: null },
  incomeCharts: { sources: null, timeline: null, net: null },
  transfersCharts: { methods: null, pairs: null, net: null },
  recentOps: [],
  baseCategories: [],
  unknownItems: [],
  corrections: [],
  profile: null,
  analyticsByTab: {
    expense: { period: { start: "", end: "" }, data: null },
    income: { period: { start: "", end: "" }, data: null },
    transfers: { period: { start: "", end: "" }, data: null },
    subscriptions: { period: { start: "", end: "" }, data: null },
  },
};
let activeAnalyticsTab = "expense";

let authToken = localStorage.getItem("auth_token") || "";
let appInitialized = false;
let reloadProfileFromBackend = async () => {};
const customSelectInstances = new Map();
let customSelectHandlersBound = false;

document.addEventListener("DOMContentLoaded", () => {
  setupTheme();
  setupFilePicker();
  setupCustomSelects();
  setupDetailPopup();
  setupInstructionLightbox();
  setupAuth();
});

function setupDetailPopup() {
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-detail-title]");
    if (!trigger || trigger.closest("#detail-popup")) return;
    e.preventDefault();
    showDetailPopup(trigger.dataset.detailTitle, trigger.dataset.detailBody || trigger.textContent.trim());
  });

  document.addEventListener("keydown", (e) => {
    const trigger = e.target.closest("[data-detail-title]");
    if ((e.key === "Enter" || e.key === " ") && trigger && !trigger.closest("#detail-popup")) {
      e.preventDefault();
      showDetailPopup(trigger.dataset.detailTitle, trigger.dataset.detailBody || trigger.textContent.trim());
    }
    if (e.key === "Escape") {
      closeDetailPopup();
      closeConfirmPopup();
      closeInstructionLightbox();
    }
  });
}

function setupInstructionLightbox() {
  document.querySelectorAll(".instruction-gallery figure").forEach((figure) => {
    const img = figure.querySelector("img");
    if (!img) return;
    const caption = figure.querySelector("figcaption")?.textContent?.trim() || img.alt || "Скриншот инструкции";
    figure.classList.add("instruction-zoom-trigger");
    figure.setAttribute("role", "button");
    figure.setAttribute("tabindex", "0");
    figure.setAttribute("aria-label", `Открыть скриншот: ${caption}`);
  });

  document.addEventListener("click", (e) => {
    const figure = e.target.closest(".instruction-zoom-trigger");
    if (!figure || figure.closest("#instruction-lightbox")) return;
    const img = figure.querySelector("img");
    if (!img) return;
    showInstructionLightbox(img.currentSrc || img.src, figure.querySelector("figcaption")?.textContent || img.alt);
  });

  document.addEventListener("keydown", (e) => {
    const figure = e.target.closest(".instruction-zoom-trigger");
    if ((e.key === "Enter" || e.key === " ") && figure && !figure.closest("#instruction-lightbox")) {
      e.preventDefault();
      const img = figure.querySelector("img");
      if (!img) return;
      showInstructionLightbox(img.currentSrc || img.src, figure.querySelector("figcaption")?.textContent || img.alt);
    }
    if (e.key === "Escape") {
      closeInstructionLightbox();
    }
  });
}

function ensureInstructionLightbox() {
  let popup = document.getElementById("instruction-lightbox");
  if (popup) return popup;
  popup = document.createElement("div");
  popup.id = "instruction-lightbox";
  popup.className = "detail-popup instruction-lightbox";
  popup.hidden = true;
  popup.innerHTML = `
    <div class="detail-backdrop" data-instruction-close></div>
    <div class="instruction-lightbox-card" role="dialog" aria-modal="true" aria-labelledby="instruction-lightbox-title">
      <div class="detail-header instruction-lightbox-header">
        <strong id="instruction-lightbox-title"></strong>
        <button class="btn ghost small" type="button" data-instruction-close>×</button>
      </div>
      <img id="instruction-lightbox-img" alt="">
    </div>
  `;
  popup.addEventListener("click", (e) => {
    if (e.target.closest("[data-instruction-close]")) {
      closeInstructionLightbox();
    }
  });
  document.body.appendChild(popup);
  return popup;
}

function showInstructionLightbox(src, title) {
  const popup = ensureInstructionLightbox();
  const img = popup.querySelector("#instruction-lightbox-img");
  const heading = popup.querySelector("#instruction-lightbox-title");
  const safeTitle = (title || "Скриншот инструкции").trim();
  heading.textContent = safeTitle;
  img.src = src;
  img.alt = safeTitle;
  popup.hidden = false;
  requestAnimationFrame(() => popup.classList.add("is-open"));
  popup.querySelector("[data-instruction-close]")?.focus();
}

function closeInstructionLightbox() {
  const popup = document.getElementById("instruction-lightbox");
  if (!popup || popup.hidden) return;
  popup.classList.remove("is-open");
  window.setTimeout(() => {
    if (!popup.classList.contains("is-open")) {
      popup.hidden = true;
      const img = popup.querySelector("#instruction-lightbox-img");
      if (img) img.removeAttribute("src");
    }
  }, 180);
}

function ensureDetailPopup() {
  let popup = document.getElementById("detail-popup");
  if (popup) return popup;
  popup = document.createElement("div");
  popup.id = "detail-popup";
  popup.className = "detail-popup";
  popup.hidden = true;
  popup.innerHTML = `
    <div class="detail-backdrop" data-detail-close></div>
    <div class="detail-card" role="dialog" aria-modal="true" aria-labelledby="detail-title">
      <div class="detail-header">
        <strong id="detail-title"></strong>
        <button class="btn ghost small" type="button" data-detail-close>×</button>
      </div>
      <div id="detail-body" class="detail-body"></div>
    </div>
  `;
  popup.addEventListener("click", (e) => {
    if (e.target.closest("[data-detail-close]")) {
      closeDetailPopup();
    }
  });
  document.body.appendChild(popup);
  return popup;
}

function showDetailPopup(title, body) {
  const popup = ensureDetailPopup();
  popup.querySelector("#detail-title").textContent = title || "Детали";
  popup.querySelector("#detail-body").textContent = body || "";
  popup.hidden = false;
  requestAnimationFrame(() => popup.classList.add("is-open"));
  popup.querySelector("[data-detail-close]")?.focus();
}

function closeDetailPopup() {
  const popup = document.getElementById("detail-popup");
  if (!popup || popup.hidden) return;
  popup.classList.remove("is-open");
  window.setTimeout(() => {
    if (!popup.classList.contains("is-open")) {
      popup.hidden = true;
    }
  }, 180);
}

function ensureConfirmPopup() {
  let popup = document.getElementById("confirm-popup");
  if (popup) return popup;
  popup = document.createElement("div");
  popup.id = "confirm-popup";
  popup.className = "detail-popup confirm-popup";
  popup.hidden = true;
  popup.innerHTML = `
    <div class="detail-backdrop" data-confirm-close></div>
    <div class="detail-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div class="detail-header">
        <strong id="confirm-title"></strong>
        <button class="btn ghost small" type="button" data-confirm-close>×</button>
      </div>
      <form id="confirm-form" class="confirm-body">
        <p id="confirm-message"></p>
        <div id="confirm-fields" class="confirm-form"></div>
        <p id="confirm-error" class="confirm-error" hidden></p>
        <div class="confirm-actions">
          <button id="confirm-cancel" class="btn ghost small" type="button" data-confirm-close>Отмена</button>
          <button id="confirm-submit" class="btn primary small" type="submit">Подтвердить</button>
        </div>
      </form>
    </div>
  `;
  popup.addEventListener("click", (e) => {
    if (e.target.closest("[data-confirm-close]")) {
      closeConfirmPopup();
    }
  });
  document.body.appendChild(popup);
  return popup;
}

function closeConfirmPopup() {
  const popup = document.getElementById("confirm-popup");
  if (!popup || popup.hidden) return;
  popup.classList.remove("is-open");
  window.setTimeout(() => {
    if (!popup.classList.contains("is-open")) {
      popup.hidden = true;
    }
  }, 180);
}

function showActionDialog({ title, message, confirmText, danger = false, fields = [], onConfirm }) {
  const popup = ensureConfirmPopup();
  const form = popup.querySelector("#confirm-form");
  const fieldsWrap = popup.querySelector("#confirm-fields");
  const errorEl = popup.querySelector("#confirm-error");
  const submit = popup.querySelector("#confirm-submit");

  popup.querySelector("#confirm-title").textContent = title;
  popup.querySelector("#confirm-message").textContent = message;
  fieldsWrap.innerHTML = "";
  errorEl.hidden = true;
  errorEl.textContent = "";
  submit.textContent = confirmText || "Подтвердить";
  submit.className = `btn ${danger ? "danger" : "primary"} small`;

  fields.forEach((field) => {
    const label = document.createElement("label");
    label.className = "profile-field";
    label.innerHTML = `
      <span>${escapeHtml(field.label)}</span>
      <input id="confirm-field-${field.id}" type="${field.type || "text"}" autocomplete="off">
    `;
    fieldsWrap.appendChild(label);
  });

  form.onsubmit = async (e) => {
    e.preventDefault();
    const values = {};
    fields.forEach((field) => {
      values[field.id] = popup.querySelector(`#confirm-field-${field.id}`)?.value || "";
    });
    errorEl.hidden = true;
    submit.disabled = true;
    try {
      await onConfirm(values);
      closeConfirmPopup();
    } catch (err) {
      errorEl.textContent = err?.message || "Не удалось выполнить действие";
      errorEl.hidden = false;
    } finally {
      submit.disabled = false;
    }
  };

  popup.hidden = false;
  requestAnimationFrame(() => popup.classList.add("is-open"));
  const firstInput = fieldsWrap.querySelector("input");
  (firstInput || submit).focus();
}

function setupCustomSelects() {
  const profileSelectIds = [
    "profile-currency",
    "profile-language",
    "profile-timezone",
    "profile-mode",
    "profile-priority",
    "profile-tone",
    "profile-file-select",
  ];

  document.querySelectorAll(".custom-select[data-select-for]").forEach((wrapper) => {
    const select = document.getElementById(wrapper.dataset.selectFor);
    if (select) enhanceCustomSelect(select, wrapper);
  });
  profileSelectIds.forEach((id) => {
    const select = document.getElementById(id);
    if (select) enhanceCustomSelect(select);
  });
  bindCustomSelectHandlers();
}

function enhanceCustomSelect(select, existingWrapper = null) {
  if (customSelectInstances.has(select)) {
    syncCustomSelect(select);
    return;
  }

  select.classList.add("native-select-hidden");
  select.setAttribute("tabindex", "-1");
  select.setAttribute("aria-hidden", "true");
  select.parentElement?.classList.add("has-custom-select");

  const wrapper = existingWrapper || document.createElement("span");
  wrapper.classList.add("custom-select");
  wrapper.dataset.selectFor = select.id;
  wrapper.innerHTML = "";

  const trigger = document.createElement("button");
  trigger.id = `${select.id}-select-trigger`;
  trigger.className = "custom-select-trigger";
  trigger.type = "button";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");

  const label = document.createElement("span");
  label.id = `${select.id}-select-label`;
  label.className = "custom-select-label";

  const caret = document.createElement("span");
  caret.className = "custom-select-caret";
  caret.setAttribute("aria-hidden", "true");

  const menu = document.createElement("span");
  menu.id = `${select.id}-select-menu`;
  menu.className = "custom-select-menu";
  menu.setAttribute("role", "listbox");
  menu.hidden = true;

  trigger.append(label, caret);
  wrapper.append(trigger, menu);

  if (!existingWrapper) {
    select.insertAdjacentElement("afterend", wrapper);
  }

  customSelectInstances.set(select, { wrapper, trigger, label, menu });

  trigger.addEventListener("click", () => {
    if (menu.hidden) openCustomSelect(select);
    else closeCustomSelect(select);
  });
  trigger.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openCustomSelect(select);
    }
  });
  select.addEventListener("change", () => syncCustomSelect(select));

  syncCustomSelect(select);
}

function bindCustomSelectHandlers() {
  if (customSelectHandlersBound) return;
  customSelectHandlersBound = true;
  document.addEventListener("click", (e) => {
    customSelectInstances.forEach((instance, select) => {
      if (!instance.wrapper.contains(e.target)) {
        closeCustomSelect(select);
      }
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      customSelectInstances.forEach((_, select) => closeCustomSelect(select));
    }
  });
}

function openCustomSelect(select) {
  const instance = customSelectInstances.get(select);
  if (!instance || select.disabled) return;
  customSelectInstances.forEach((_, item) => {
    if (item !== select) closeCustomSelect(item);
  });
  syncCustomSelect(select);
  instance.menu.hidden = false;
  instance.trigger.setAttribute("aria-expanded", "true");
  instance.menu.querySelector(".custom-select-option.active")?.focus();
}

function closeCustomSelect(select) {
  const instance = customSelectInstances.get(select);
  if (!instance) return;
  instance.menu.hidden = true;
  instance.trigger.setAttribute("aria-expanded", "false");
}

function setCustomSelectValue(select, value) {
  const previous = select.value;
  select.value = value;
  syncCustomSelect(select);
  closeCustomSelect(select);
  customSelectInstances.get(select)?.trigger.focus();
  if (select.value !== previous) {
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function syncCustomSelect(select) {
  const instance = customSelectInstances.get(select);
  if (!instance) return;

  const options = Array.from(select.options);
  const selectedOption = options.find((option) => option.value === select.value) || options.find((option) => option.selected) || options[0];
  const selectedText = selectedOption ? selectedOption.textContent.trim() : "";

  const isBankSelect = select.id === "bank";
  const bankIcon = isBankSelect ? (BANK_ICONS[selectedOption?.value] || "") : "";
  if (isBankSelect && bankIcon) {
    instance.label.innerHTML = `${bankIcon}<span>${escapeHtml(selectedText)}</span>`;
  } else {
    instance.label.textContent = selectedText;
  }
  instance.trigger.title = selectedText;
  instance.trigger.disabled = select.disabled || !options.length;
  instance.menu.innerHTML = "";

  options.forEach((option) => {
    const button = document.createElement("button");
    const active = option === selectedOption;
    button.className = `custom-select-option${active ? " active" : ""}`;
    button.type = "button";
    button.setAttribute("role", "option");
    button.dataset.value = option.value;
    button.disabled = option.disabled;
    button.setAttribute("aria-selected", active ? "true" : "false");
    const optIcon = isBankSelect ? (BANK_ICONS[option.value] || "") : "";
    if (optIcon) {
      button.innerHTML = `${optIcon}<span>${escapeHtml(option.textContent.trim())}</span>`;
    } else {
      button.textContent = option.textContent.trim();
    }
    button.addEventListener("click", () => setCustomSelectValue(select, option.value));
    button.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        button.nextElementSibling?.focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        button.previousElementSibling?.focus();
      }
    });
    instance.menu.appendChild(button);
  });
}

function setupFilePicker() {
  const input = document.getElementById("file");
  const name = document.getElementById("file-name");
  const picker = input?.closest(".file-picker");
  const bankSelect = document.getElementById("bank");
  if (!input || !name || !picker) return;

  const sync = () => {
    const fileName = input.files?.[0]?.name || "Файл не выбран";
    name.textContent = fileName;
    picker.classList.toggle("has-file", Boolean(input.files?.length));
    if (input.files?.length) clearUploadError();
  };

  const syncBankFormat = () => {
    const note = document.getElementById("bank-format-note");
    const format = BANK_IMPORT_FORMATS[bankSelect?.value] || BANK_IMPORT_FORMATS.alfa;
    input.accept = format.accept;
    if (note) note.textContent = `Поддерживаемый формат: ${format.label}`;
    if (input.files?.length) {
      input.value = "";
      sync();
    }
    clearUploadError();
  };

  input.addEventListener("change", sync);
  bankSelect?.addEventListener("change", syncBankFormat);
  syncBankFormat();
  sync();
}

function uploadFormatError(bank, fileName) {
  const format = BANK_IMPORT_FORMATS[bank] || BANK_IMPORT_FORMATS.alfa;
  const ext = fileExtension(fileName);
  if (!ext || !format.extensions.includes(ext)) {
    return `Неверный формат файла. Для выбранного банка нужен ${format.label}.`;
  }
  return "";
}

function fileExtension(fileName) {
  const name = String(fileName || "").toLowerCase();
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot) : "";
}

function showUploadError(message) {
  const error = document.getElementById("upload-error");
  if (!error) return;
  error.textContent = message;
  error.hidden = false;
}

function clearUploadError() {
  const error = document.getElementById("upload-error");
  if (!error) return;
  error.textContent = "";
  error.hidden = true;
}

function setupTheme() {
  const saved = localStorage.getItem("moneymap_theme") || "light";
  applyTheme(saved);
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    rerenderChartsForTheme();
  });
}

function applyTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = normalized;
  localStorage.setItem("moneymap_theme", normalized);
  const toggle = document.getElementById("theme-toggle");
  const icon = document.getElementById("theme-icon");
  const nextLabel = normalized === "dark" ? "\u0421\u0432\u0435\u0442\u043b\u0430\u044f \u0442\u0435\u043c\u0430" : "\u0422\u0451\u043c\u043d\u0430\u044f \u0442\u0435\u043c\u0430";
  if (toggle) {
    toggle.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
    toggle.setAttribute("aria-label", nextLabel);
    toggle.setAttribute("title", nextLabel);
  }
  if (icon) icon.textContent = normalized === "dark" ? "\u2600" : "\u263e";
  if (window.Chart) {
    Chart.defaults.color = chartTextColor();
    Chart.defaults.borderColor = chartGridColor();
  }
}

function chartTextColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--muted-strong").trim() || "#475467";
}

function chartGridColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--border").trim() || "#d8e0ea";
}

function rerenderChartsForTheme() {
  if (!appInitialized) return;
  renderAnalyticsForTab(activeAnalyticsTab);
  renderMainTransfersChart();
}

function apiFetch(url, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (authToken) {
    headers["X-Auth-Token"] = authToken;
  }
  return fetch(url, { ...options, headers });
}

async function apiJson(url, options = {}) {
  const res = await apiFetch(url, options);
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("unauthorized");
  }
  return res.json();
}

async function safeApiFetch(url, options = {}) {
  const res = await apiFetch(url, options);
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    let message = "Не удалось выполнить действие";
    try {
      const data = await res.clone().json();
      message = data.message || data.error || message;
    } catch (err) {
      try {
        message = (await res.clone().text()) || message;
      } catch (innerErr) {
        // keep the default message
      }
    }
    throw new Error(message);
  }
  return res;
}

async function ensureBaseCategoriesLoaded() {
  if (state.baseCategories.length) return state.baseCategories;
  const data = await apiJson("/api/categories");
  state.baseCategories = data.base || [];
  const mapSelect = document.getElementById("map-base-id");
  if (mapSelect) {
    mapSelect.innerHTML = '<option value="">Выберите категорию</option>';
    state.baseCategories.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = `${item.id} · ${item.name}`;
      mapSelect.appendChild(opt);
    });
  }
  return state.baseCategories;
}

function handleUnauthorized() {
  authToken = "";
  localStorage.removeItem("auth_token");
  showAuthLoginScreen("Сессия истекла. Введите пароль заново");
}

function showAuthLoginScreen(subtitleText = "Введите пароль, чтобы открыть данные") {
  const screen = document.getElementById("auth-screen");
  const loginForm = document.getElementById("auth-login-form");
  const createForm = document.getElementById("auth-create-form");
  const title = document.getElementById("auth-title");
  const subtitle = document.getElementById("auth-subtitle");
  if (screen) screen.style.display = "flex";
  if (loginForm) loginForm.classList.remove("hidden");
  if (createForm) createForm.classList.add("hidden");
  if (title) title.textContent = "Вход";
  if (subtitle) subtitle.textContent = subtitleText;
}

function showAuthCreateScreen() {
  const screen = document.getElementById("auth-screen");
  const loginForm = document.getElementById("auth-login-form");
  const createForm = document.getElementById("auth-create-form");
  const title = document.getElementById("auth-title");
  const subtitle = document.getElementById("auth-subtitle");
  if (screen) screen.style.display = "flex";
  if (loginForm) loginForm.classList.add("hidden");
  if (createForm) createForm.classList.remove("hidden");
  if (title) title.textContent = "Создание пароля";
  if (subtitle) subtitle.textContent = "Задайте пароль, чтобы защитить доступ";
}

function hideAuthScreen() {
  const screen = document.getElementById("auth-screen");
  if (screen) screen.style.display = "none";
}

function resumeAuthenticatedApp() {
  hideAuthScreen();
  if (appInitialized) {
    Promise.allSettled([reloadProfileFromBackend(), refresh()]);
    return;
  }
  startApp();
}

async function validateStoredSession() {
  if (!authToken) return false;
  const res = await apiFetch("/api/profile");
  if (res.status === 401) {
    authToken = "";
    localStorage.removeItem("auth_token");
    return false;
  }
  return res.ok;
}

function setupAuth() {
  const screen = document.getElementById("auth-screen");
  const loginForm = document.getElementById("auth-login-form");
  const createForm = document.getElementById("auth-create-form");
  const loginError = document.getElementById("auth-error");
  const createError = document.getElementById("auth-create-error");

  // показать форму сразу, чтобы не оставлять пустой экран даже если статус не загрузился
  showAuthLoginScreen();

  fetch("/api/auth/status")
    .then((r) => r.json())
    .then(async (data) => {
      if (data.password_set) {
        showAuthLoginScreen();
        if (authToken && (await validateStoredSession())) {
          resumeAuthenticatedApp();
        }
      } else {
        showAuthCreateScreen();
      }
    })
    .catch(() => {
      showAuthLoginScreen();
    });

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.hidden = true;
    const password = document.getElementById("auth-password").value;
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (!res.ok) {
      loginError.textContent = "Неверный пароль";
      loginError.hidden = false;
      return;
    }
    authToken = data.token;
    localStorage.setItem("auth_token", authToken);
    resumeAuthenticatedApp();
  });

  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    createError.hidden = true;
    const password = document.getElementById("auth-new-password").value;
    const res = await fetch("/api/auth/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (!res.ok) {
      createError.textContent = "Не удалось сохранить пароль";
      createError.hidden = false;
      return;
    }
    authToken = data.token;
    localStorage.setItem("auth_token", authToken);
    resumeAuthenticatedApp();
  });
}

function startApp() {
  if (appInitialized) return;
  appInitialized = true;

  const form = document.getElementById("upload-form");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearUploadError();
    const bank = document.getElementById("bank").value;
    const fileInput = document.getElementById("file");
    if (!fileInput.files.length) {
      const message = "Выберите файл с операциями";
      showUploadError(message);
      return showToast(message);
    }
    const formatError = uploadFormatError(bank, fileInput.files[0].name);
    if (formatError) {
      showUploadError(formatError);
      return showToast(formatError);
    }
    const data = new FormData();
    data.append("bank", bank);
    data.append("file", fileInput.files[0]);
    try {
      const response = await safeApiFetch("/api/import", { method: "POST", body: data });
      const result = await response.json();
      fileInput.value = "";
      fileInput.dispatchEvent(new Event("change"));
      clearUploadError();
      const duplicates = Number(result.import_report?.duplicates || 0);
      showToast(duplicates ? `Файл загружен, дублей пропущено: ${duplicates}` : "Файл успешно загружен");
      await refreshAfterDataMutation();
    } catch (err) {
      const message = err.message || "Не удалось импортировать файл";
      showUploadError(message);
      showToast(message);
    }
  });

  document.getElementById("exp-chart-back").addEventListener("click", () => switchToBase("expense"));
  document.getElementById("inc-chart-back").addEventListener("click", () => switchToBase("income"));
  const transferBack = document.getElementById("transfer-chart-back");
  if (transferBack) {
    transferBack.addEventListener("click", () => {
      state.transfers.mode = "base";
      state.transfers.selected = null;
      state.transfers.merchantData = [];
      renderTransfersChart();
    });
  }

  document.querySelectorAll(".nav-btn[data-target]").forEach((btn) => {
    btn.addEventListener("click", () => switchSection(btn.dataset.target, btn));
  });

  document.querySelectorAll(".nav-btn[data-analytics-target]").forEach((btn) => {
    btn.addEventListener("click", () => switchAnalytics(btn.dataset.analyticsTarget, btn));
  });
  syncAnalyticsControlState();

  document.querySelectorAll(".seg-btn[data-quick]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-quick]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      applyQuickRange(btn.dataset.quick);
    });
  });

  // expense analytics toggles
  const top5 = document.getElementById("exp-top-5");
  const top10 = document.getElementById("exp-top-10");
  if (top5 && top10) {
    const toggleTop = (n, btn) => {
      state.expenseTopN = n;
      [top5, top10].forEach((b) => b.classList.toggle("active", b === btn));
      renderExpenseTopCategoriesChart();
    };
    top5.addEventListener("click", () => toggleTop(5, top5));
    top10.addEventListener("click", () => toggleTop(10, top10));
  }
  const topReset = document.getElementById("exp-top-reset");
  if (topReset) {
    topReset.addEventListener("click", () => {
      state.expenseFilterCategory = null;
      renderExpenseTopCategoriesChart();
      showToast("Фильтр по категориям сброшен");
    });
  }
  const dynMonth = document.getElementById("exp-dyn-month");
  const dynWeek = document.getElementById("exp-dyn-week");
  if (dynMonth && dynWeek) {
    const toggleDyn = (mode, btn) => {
      state.expenseDynMode = mode;
      [dynMonth, dynWeek].forEach((b) => b.classList.toggle("active", b === btn));
      renderExpenseDynamicsChart();
    };
    dynMonth.addEventListener("click", () => toggleDyn("month", dynMonth));
    dynWeek.addEventListener("click", () => toggleDyn("week", dynWeek));
  }

  // income timeline toggle (если добавим переключатель позже)
  document.querySelectorAll(".seg-btn[data-income-trend]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-income-trend]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderIncomeTimelineChart();
    });
  });

  document.querySelectorAll(".seg-btn[data-analytics-quick]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.analyticsTab;
      document
        .querySelectorAll(`.seg-btn[data-analytics-tab="${tab}"]`)
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      applyAnalyticsQuickRange(tab, btn.dataset.analyticsQuick);
    });
  });

  ["expense", "income", "transfers", "subscriptions"].forEach((tab) => {
    const startEl = document.getElementById(`analytics-start-${tab}`);
    const endEl = document.getElementById(`analytics-end-${tab}`);
    if (startEl) {
      startEl.addEventListener("change", () => {
        state.analyticsByTab[tab].period.start = startEl.value;
        if (tab === activeAnalyticsTab) refresh();
      });
    }
    if (endEl) {
      endEl.addEventListener("change", () => {
        state.analyticsByTab[tab].period.end = endEl.value;
        if (tab === activeAnalyticsTab) refresh();
      });
    }
  });

  document.getElementById("hist-apply").addEventListener("click", () => loadOperations());

  setupHistoryDefaults();
  setupAnalyticsDefaults();
  setupAgent();
  setupProfileForm();
  setupHistoryTools();
  hydrateGoalsFromStorage();
  const mainTransferBack = document.getElementById("main-transfer-back");
  if (mainTransferBack) {
    mainTransferBack.addEventListener("click", () => {
      state.mainTransfersMode = "base";
      state.mainTransfersSelected = null;
      state.mainTransfersMerchants = [];
      renderMainTransfersChart();
    });
  }
  ensureBaseCategoriesLoaded().catch(() => {});
  refresh();
}

async function refresh() {
  const { start, end } = state.analyticsByTab[activeAnalyticsTab].period;
  const params = new URLSearchParams();
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  params.set("exclude_transfers", activeAnalyticsTab === "transfers" ? "false" : "true");

  const homePromise = apiJson("/api/analytics?exclude_transfers=true");
  const tabPromise = apiJson(`/api/analytics?${params.toString()}`);
  const [homeAnalytics, analytics] = await Promise.all([homePromise, tabPromise]);

  state.homeAnalytics = homeAnalytics;
  updateCards();
  renderHomeSummary();

  state.analyticsByTab[activeAnalyticsTab].data = analytics;
  if ((!start || !end) && analytics.period_all) {
    state.analyticsByTab[activeAnalyticsTab].period = {
      start: start || analytics.period_all.start,
      end: end || analytics.period_all.end,
    };
    syncAnalyticsInputs();
  }
  state.analytics = analytics;
  renderAnalyticsForTab(activeAnalyticsTab);
  await renderFiles();
  await loadOperations();
  await loadRecentOperations();
  await loadUnknown();
  await loadCorrections();
}

function resetDrilldowns() {
  ["expense", "income", "transfers"].forEach((kind) => {
    state[kind].mode = "base";
    state[kind].selected = null;
    state[kind].merchantData = [];
  });
  state.mainTransfersMode = "base";
  state.mainTransfersSelected = null;
  state.mainTransfersMerchants = [];
  state.expenseFilterCategory = null;
  state.subscriptions.selected = null;
  state.subscriptions.items = [];
  state.subscriptions.operations = [];
}

function invalidateAnalyticsCache({ resetPeriods = false } = {}) {
  Object.keys(state.analyticsByTab).forEach((tab) => {
    state.analyticsByTab[tab].data = null;
    if (resetPeriods) {
      state.analyticsByTab[tab].period = { start: "", end: "" };
    }
  });
  state.analytics = null;
  state.homeAnalytics = null;
  state.recentOps = [];
  state.unknownItems = [];
  state.corrections = [];
  resetDrilldowns();
  if (resetPeriods) {
    syncAnalyticsInputs();
  }
}

async function refreshAfterDataMutation({ resetPeriods = true } = {}) {
  invalidateAnalyticsCache({ resetPeriods });
  await refresh();
}

function hydrateGoalsFromStorage() {
  updateHomeGoals({
    goal_title: document.getElementById("profile-goal-title")?.value || "",
    goal_amount: document.getElementById("profile-goal-amount")?.value || "",
    goal_saved: document.getElementById("profile-goal-saved")?.value || "",
    goal_deadline: document.getElementById("profile-goal-deadline")?.value || "",
    goals: document.getElementById("agent-goals")?.value || localStorage.getItem("user_goals") || "",
  });
}

function setupProfileForm() {
  const fields = {
    name: document.getElementById("profile-name"),
    currency: document.getElementById("profile-currency"),
    language: document.getElementById("profile-language"),
    timezone: document.getElementById("profile-timezone"),
    income: document.getElementById("profile-income"),
    payday: document.getElementById("profile-payday"),
    mode: document.getElementById("profile-mode"),
    goal_title: document.getElementById("profile-goal-title"),
    goal_amount: document.getElementById("profile-goal-amount"),
    goal_saved: document.getElementById("profile-goal-saved"),
    goal_deadline: document.getElementById("profile-goal-deadline"),
    goals: document.getElementById("agent-goals"),
    priority: document.getElementById("profile-priority"),
    tone: document.getElementById("profile-tone"),
  };
  const saveBtn = document.getElementById("profile-save-btn");
  if (!saveBtn) return;
  let saveTimer = null;

  const localProfileCandidate = () => {
    const profile = {};
    try {
      const raw = localStorage.getItem("user_profile");
      if (raw) {
        const data = JSON.parse(raw);
        Object.assign(profile, data || {});
      }
    } catch (e) {
      console.warn("Failed to parse saved profile", e);
    }
    const goals = localStorage.getItem("user_goals");
    if (goals) profile.goals = goals;
    delete profile.pin;
    return profile;
  };

  const applyProfile = (profile = {}) => {
    state.profile = { ...profile };
    Object.entries(fields).forEach(([key, el]) => {
      if (el && profile[key] !== undefined) el.value = profile[key];
    });
    Object.values(fields).forEach((el) => syncCustomSelect(el));
    syncGoalsTextarea();
    updateHomeGoals(profilePayload());
  };

  const hasAnyValue = () =>
    Object.values(fields).some((el) => el && typeof el.value === "string" && el.value.trim().length);

  const toggleButton = () => {
    saveBtn.disabled = !hasAnyValue();
  };

  const profilePayload = () => {
    const payload = {};
    Object.entries(fields).forEach(([key, el]) => {
      payload[key] = el ? el.value : "";
    });
    return payload;
  };

  const saveProfile = async ({ silent = false } = {}) => {
    const payload = profilePayload();
    const data = await apiJson("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: payload }),
    });
    applyProfile(data.profile || payload);
    localStorage.removeItem("user_profile");
    localStorage.removeItem("user_goals");
    if (!silent) showToast("Профиль сохранён");
    toggleButton();
  };

  const scheduleSave = () => {
    if (saveTimer) window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      saveProfile({ silent: true }).catch(() => {});
    }, 700);
  };

  const syncGoalsTextarea = () => {
    const goals = fields.goals;
    if (!goals) return;
    goals.style.height = "auto";
    goals.style.height = Math.min(goals.scrollHeight + 4, 600) + "px";
  };

  Object.entries(fields).forEach(([key, el]) => {
    if (!el) return;
    el.addEventListener("input", () => {
      toggleButton();
      if (el === fields.goals) {
        if (el.value.length > 5000) el.value = el.value.slice(0, 5000);
        syncGoalsTextarea();
        updateHomeGoals(profilePayload());
      } else if (key.startsWith("goal_")) {
        updateHomeGoals(profilePayload());
      }
      scheduleSave();
    });
    el.addEventListener("change", () => {
      toggleButton();
      if (el !== fields.goals) scheduleSave();
    });
  });
  saveBtn.addEventListener("click", () => saveProfile().catch(() => showToast("Не удалось сохранить профиль")));

  const loadProfile = async () => {
    const data = await apiJson("/api/profile");
    let profile = data.profile || {};
    const localProfile = localProfileCandidate();
    if (!data.exists && Object.keys(localProfile).length) {
      profile = { ...profile, ...localProfile };
      applyProfile(profile);
      await saveProfile({ silent: true });
      return;
    }
    applyProfile(profile);
  };

  reloadProfileFromBackend = async () => {
    await loadProfile();
    toggleButton();
  };

  reloadProfileFromBackend()
    .catch(() => {
      applyProfile(localProfileCandidate());
    })
    .finally(toggleButton);
  toggleButton();
}

function renderAnalyticsForTab(tab) {
  if (!state.analyticsByTab[tab].data) return;
  const analytics = state.analyticsByTab[tab].data;
  state.analytics = analytics;

  if (tab === "expense") {
    state.expense.baseData = analytics.by_base_expense || analytics.by_base || [];
    switchToBase("expense", false);
    renderCategoryChart("expense");
    renderExpenseTopCategoriesChart();
    renderExpenseDynamicsChart();
    renderExpenseCumulativeChart();
  } else if (tab === "income") {
    state.income.baseData = analytics.by_base_income || [];
    switchToBase("income", false);
    renderCategoryChart("income");
    renderIncomeSourcesChart();
    renderIncomeTimelineChart();
    renderIncomeNetChart();
  } else if (tab === "transfers") {
    state.transfers.baseData = analytics.transfers || [];
    renderTransfersChart();
    renderTransfers();
    renderTransfersPlaceholders();
  } else if (tab === "subscriptions") {
    state.subscriptions.items = analytics.subscriptions || [];
    renderSubscriptions();
  }
  updateCards();
}

function switchSection(targetId, btn) {
  document.querySelectorAll(".section").forEach((sec) => sec.classList.add("hidden"));
  document.getElementById(targetId).classList.remove("hidden");
  document.querySelectorAll(".nav-btn[data-target]").forEach((b) => b.classList.remove("active"));
  btn?.classList.add("active");
}

function switchAnalytics(targetId, btn) {
  document.querySelectorAll(".analytics-view").forEach((sec) => sec.classList.add("hidden"));
  document.getElementById(targetId).classList.remove("hidden");
  document.querySelectorAll(".nav-btn[data-analytics-target]").forEach((b) => b.classList.remove("active"));
  const activeBtn = btn || document.querySelector(`.nav-btn[data-analytics-target="${targetId}"]`);
  activeBtn?.classList.add("active");
  syncAnalyticsControlState();
  activeAnalyticsTab = targetId.replace("-view", "");
  syncAnalyticsInputs();
  if (state.analyticsByTab[activeAnalyticsTab].data) {
    renderAnalyticsForTab(activeAnalyticsTab);
  } else {
    refresh();
  }
}

function syncAnalyticsControlState() {
  document.querySelectorAll(".analytics-card").forEach((card) => {
    const tabButton = card.querySelector(".nav-btn[data-analytics-target]");
    card.classList.toggle("is-active", Boolean(tabButton?.classList.contains("active")));
  });
}

function updateCards(data) {
  const source = data || state.homeAnalytics;
  if (!source) return;
  const format = (v) => formatCurrency(v);
  document.getElementById("income").textContent = format(source.totals.income);
  document.getElementById("expense").textContent = format(source.totals.expense);
  document.getElementById("net").textContent = format(source.totals.net);
  document.getElementById("unknown").textContent = source.unknown;
  const unmappedEl = document.getElementById("unmapped");
  if (unmappedEl) unmappedEl.textContent = source.unmapped.length;
  const opsCount =
    (source && (source.ops_count_total || source.ops_count)) || (state.homeAnalytics && state.homeAnalytics.ops_count_total) || 0;
  const opsEl = document.getElementById("profile-ops-count");
  if (opsEl) opsEl.textContent = opsCount;
}

function renderHomeSummary() {
  updateHomeGoals(state.profile || localStorage.getItem("user_goals") || "");
  renderHomeQuickAnswers(state.homeAnalytics?.quick_answers || {});
  renderRecentOperations(state.recentOps || []);
  renderMainTransfersChart();
}

function switchToBase(kind, rerender = true) {
  const s = state[kind];
  s.mode = "base";
  s.selected = null;
  s.merchantData = [];
  if (rerender) renderCategoryChart(kind);
}

async function drillToMerchants(kind, baseId) {
  if (kind === "transfers") {
    await drillToMerchantsTransfers(baseId);
    return;
  }
  const s = state[kind];
  s.selected = baseId;
  const data = await apiJson(
    `/api/merchant-breakdown?base_id=${encodeURIComponent(baseId)}&op_type=${kind === "expense" ? "expense" : "income"}`
  );
  s.merchantData = data.items || [];
  s.mode = "merchant";
  renderCategoryChart(kind);
}

async function drillToMerchantsTransfers(baseId) {
  state.transfers.selected = baseId;
  const data = await apiJson(`/api/merchant-breakdown?base_id=${encodeURIComponent(baseId)}`);
  state.transfers.merchantData = data.items || [];
  state.transfers.mode = "merchant";
  renderTransfersChart();
}

function renderCategoryChart(kind) {
  const s = state[kind];
  const isExpense = kind === "expense";
  const ctx = document.getElementById(isExpense ? "expChart" : "incChart");
  const legend = document.getElementById(isExpense ? "expLegend" : "incLegend");
  const titleEl = document.getElementById(isExpense ? "exp-chart-title" : "inc-chart-title");
  const subtitleEl = document.getElementById(isExpense ? "exp-chart-subtitle" : "inc-chart-subtitle");
  const backBtn = document.getElementById(isExpense ? "exp-chart-back" : "inc-chart-back");

  legend.innerHTML = "";

  let labels = [];
  let values = [];
  let colors = [];

  if (s.mode === "base") {
    const filtered = s.baseData.filter((i) => (isExpense ? i.amount < 0 : i.amount > 0));
    if (!filtered.length) {
      if (s.chart) s.chart.destroy();
      legend.textContent = "Нет данных";
      titleEl.textContent = isExpense ? "Расходы по категориям" : "Доходы по категориям";
      subtitleEl.textContent = isExpense ? "Доли трат по base_* категориям" : "Доли доходов по base_* категориям";
      backBtn.hidden = true;
      return;
    }
    labels = filtered.map((i) => i.name);
    values = filtered.map((i) => Math.abs(i.amount));
    colors = labels.map((_, idx) => SYS_COLORS[idx % SYS_COLORS.length]);
    legend.appendChild(buildInteractiveLegend(filtered, colors, kind));
    titleEl.textContent = isExpense ? "Расходы по категориям" : "Доходы по категориям";
    subtitleEl.textContent = isExpense ? "Доли трат по base_* категориям" : "Доли доходов по base_* категориям";
    backBtn.hidden = true;
  } else {
    const items = s.merchantData || [];
    if (!items.length) {
      if (s.chart) s.chart.destroy();
      legend.textContent = "Нет данных по мерчантам";
      titleEl.textContent = "Мерчанты";
      subtitleEl.textContent = "Выберите категорию";
      backBtn.hidden = false;
      return;
    }
    labels = items.map((i) => i.merchant || "unknown");
    values = items.map((i) => i.amount);
    colors = labels.map((_, idx) => hexToRgba(SYS_COLORS[idx % SYS_COLORS.length], 0.85));
    legend.appendChild(buildLegend(labels, colors, "Мерчанты"));
    titleEl.textContent = "Мерчанты";
    subtitleEl.textContent = "Траты внутри выбранной категории";
    backBtn.hidden = false;
  }

  if (s.chart) s.chart.destroy();
  s.chart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          hoverOffset: 4,
          cutout: "72%",
          borderWidth: 0,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const value = ctx.parsed;
              const total = values.reduce((sum, v) => sum + (v || 0), 0);
              const percent = total ? ((value / total) * 100).toFixed(1) : 0;
              return `${ctx.label}: ${formatCurrency(value)} (${percent}%)`;
            },
          },
        },
      },
    },
  });
}

// Доп. графики: доходы/трансферы
function renderIncomeSourcesChart() {
  const canvas = document.getElementById("incSourcesChart");
  if (!canvas) return;
  const items = state.income.baseData || [];
  if (state.incomeCharts.sources) state.incomeCharts.sources.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  const labels = items.map((i) => i.name);
  const values = items.map((i) => i.amount);
  const colors = labels.map((_, idx) => hexToRgba(SYS_COLORS[idx % SYS_COLORS.length], 0.9));
  state.incomeCharts.sources = new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x)}` } } },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { display: false } },
      },
    },
  });
}

function renderIncomeTimelineChart() {
  const canvas = document.getElementById("incTimelineChart");
  if (!canvas || !state.analytics) return;
  const items = state.analytics.trend || [];
  if (state.incomeCharts.timeline) state.incomeCharts.timeline.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  const labels = items.map((i) => i.label);
  const values = items.map((i) => i.income || 0);
  state.incomeCharts.timeline = new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [{ label: "Доходы", data: values, borderColor: "#5bb4ff", backgroundColor: "rgba(91, 180, 255, 0.12)", tension: 0.35, fill: true }] },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.y)}` } } },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() }, beginAtZero: true },
      },
    },
  });
}

function renderIncomeNetChart() {
  const canvas = document.getElementById("incNetChart");
  if (!canvas || !state.analytics) return;
  const items = state.analytics.trend || [];
  if (state.incomeCharts.net) state.incomeCharts.net.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  const labels = items.map((i) => i.label);
  const net = items.map((i) => (i.income || 0) + (i.expense || 0));
  state.incomeCharts.net = new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: net, backgroundColor: net.map((v) => (v >= 0 ? "#5bb4ff" : "#ff9b9b")), borderWidth: 0 }] },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.y)}` } } },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() }, beginAtZero: true },
      },
    },
  });
}

function renderTransfersPlaceholders() {
  // Пока нет детальных данных по способам/парам счетов – оставляем плейсхолдеры
}

function renderExpenseTopCategoriesChart() {
  const canvas = document.getElementById("expTopCategoriesChart");
  if (!canvas) return;
  const raw = (state.expense.baseData || []).filter((i) => i.amount < 0);
  const sorted = raw.sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
  const topN = state.expenseTopN || 5;
  const slice = sorted.slice(0, topN);
  const labels = slice.map((i) => i.name);
  const values = slice.map((i) => Math.abs(i.amount || 0));
  const colors = labels.map((_, idx) => hexToRgba(SYS_COLORS[idx % SYS_COLORS.length], 0.9));
  if (state.expenseCharts.top) state.expenseCharts.top.destroy();
  if (!slice.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  state.expenseCharts.top = new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      layout: { padding: { top: 4, right: 4, bottom: 0, left: 0 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x)} (${((ctx.parsed.x / values.reduce((s, v) => s + v, 0)) * 100).toFixed(1)}%)`,
          },
        },
      },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { display: false } },
      },
      onClick: (evt, elements) => {
        if (!elements.length) return;
        const idx = elements[0].index;
        state.expenseFilterCategory = slice[idx]?.id || null;
        showToast(`Фильтр по категории: ${slice[idx]?.name || ""}`);
      },
    },
  });
}

function renderExpenseDynamicsChart() {
  const canvas = document.getElementById("expDynamicsChart");
  if (!canvas || !state.analytics) return;
  const mode = state.expenseDynMode === "week" ? "weekly" : "monthly";
  const map = { monthly: state.analytics.trend, weekly: state.analytics.trend_weekly };
  const items = map[mode] || [];
  const labels = items.map((i) => i.label);
  const values = items.map((i) => Math.abs(i.expense || 0));
  if (state.expenseCharts.dynamics) state.expenseCharts.dynamics.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  state.expenseCharts.dynamics = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Расходы",
          data: values,
          borderColor: "#ff9b9b",
          backgroundColor: "rgba(255, 155, 155, 0.15)",
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() }, beginAtZero: true },
      },
    },
  });
}

function renderExpenseCumulativeChart() {
  const canvas = document.getElementById("expCumulativeChart");
  if (!canvas || !state.analytics) return;
  const items = state.analytics.trend_daily || [];
  if (state.expenseCharts.cumulative) state.expenseCharts.cumulative.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  const labels = items.map((i) => i.label || i.date);
  const expenses = items.map((i) => Math.abs(i.expense || 0));
  const cumulative = expenses.reduce((acc, v) => {
    const last = acc.length ? acc[acc.length - 1] : 0;
    acc.push(last + v);
    return acc;
  }, []);
  state.expenseCharts.cumulative = new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [{ label: "Накопленные расходы", data: cumulative, borderColor: "#ff9b9b", fill: false, tension: 0.25 }] },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() }, beginAtZero: true },
      },
    },
  });
}

function renderOperations(items) {
  const body = document.getElementById("ops-body");
  body.innerHTML = "";
  items.forEach((op) => {
    const categoryLabel = op.category_name || op.category_id || "-";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDate(op.date)}</td>
      <td>${op.bank}</td>
      <td>${escapeHtml(op.description || "")}</td>
      <td>
        <button
          type="button"
          class="btn ghost small op-cat-btn"
          data-op-id="${op.id}"
          data-category-id="${op.category_id || ""}"
          title="Изменить категорию"
        >
          ${escapeHtml(categoryLabel)}
        </button>
      </td>
      <td class="${op.amount < 0 ? "amount-neg" : "amount-pos"}">${formatCurrency(op.amount)}</td>
    `;
    body.appendChild(tr);
  });
  body.querySelectorAll(".op-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await ensureBaseCategoriesLoaded();
      const baseCategoryMap = {};
      state.baseCategories.forEach((item) => {
        baseCategoryMap[item.id] = item.name;
      });
      const current = btn.dataset.categoryId || "";
      const next = prompt("Введите base_* категорию", current || "base_unknown");
      if (!next) return;
      const categoryId = next.trim();
      if (!baseCategoryMap[categoryId]) {
        return showToast("Неизвестная категория");
      }
      const opId = btn.dataset.opId;
      await apiJson(`/api/operations/${encodeURIComponent(opId)}/category`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_id: categoryId, reason: "manual ui correction" }),
      });
      showToast("Категория обновлена");
      await refreshAfterDataMutation({ resetPeriods: false });
    });
  });
}

function renderRecentOperations(items) {
  const body = document.getElementById("home-recent-body");
  if (!body) return;
  body.innerHTML = "";
  if (!items.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" class="muted">Нет операций за последнюю неделю</td>`;
    body.appendChild(tr);
    return;
  }
  items.forEach((op) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDate(op.date)}</td>
      <td>${op.bank}</td>
      <td>${escapeHtml(op.description || "")}</td>
      <td>${op.category_name || "-"}</td>
      <td class="${op.amount < 0 ? "amount-neg" : "amount-pos"}">${formatCurrency(op.amount)}</td>
    `;
    body.appendChild(tr);
  });
}

function transferLabel(item) {
  const id = item?.id || "";
  const name = (item?.name || id || "").toLowerCase();
  if (id === "base_transfer_in" || name.includes("вход")) return "Входящие";
  if (id === "base_transfer_out" || name.includes("исход")) return "Исходящие";
  if (id === "base_topup" || name.includes("пополн")) return "Пополнение";
  return item?.name || item?.id || "Перевод";
}

function compactText(value, max = 28) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trim()}…`;
}

function titleCaseMerchant(value) {
  return String(value || "")
    .split(" ")
    .filter(Boolean)
    .map((word) => {
      if (/^(ооо|ип|омс|iss|alfa|ru)$/i.test(word)) return word.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

function mainTransferMerchantLabel(value, max = 44) {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  if (!raw) return "Контрагент";
  const lower = raw.toLowerCase();
  if (lower.includes("внесение средств")) return "Внесение средств";
  if (lower.includes("продажа металла")) return "Продажа металла с ОМС";
  if (lower.includes("возврат по операц")) return "Возврат по операции";
  if (lower.includes("выплата по обращ")) return "Выплата по обращению";

  const accountMatch = lower.match(/\b(\d{4})\s+(\d{4})\s+(\d{6,})\b/);
  const accountTail = accountMatch ? accountMatch[3].slice(-4) : "";
  let cleaned = lower
    .replace(/\b\d{2}\s+\d{2}\s+\d{2}\b/g, " ")
    .replace(/\b\d[\d\s]{10,}\b/g, " ")
    .replace(/\b\d+(?:[.,]\d+)?\b/g, " ")
    .replace(/\b(ru|moskva|moscow|russia)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (cleaned.includes("alfa iss")) return accountTail ? `Alfa ISS • ${accountTail}` : "Alfa ISS";
  if (!cleaned) return accountTail ? `Счёт/карта • ${accountTail}` : "Контрагент";
  return compactText(titleCaseMerchant(cleaned), max);
}

function renderMainTransfersChart() {
  const canvas = document.getElementById("mainTransferChart");
  const legend = document.getElementById("mainTransferLegend");
  const backBtn = document.getElementById("main-transfer-back");
  const subtitle = document.getElementById("main-transfer-subtitle");
  if (!canvas || !legend) return;

  legend.innerHTML = "";
  const mode = state.mainTransfersMode || "base";
  canvas.closest(".transfer-card")?.classList.toggle("merchant-mode", mode === "merchant");
  const colorHex = (idx) => SYS_COLORS[idx % SYS_COLORS.length];
  const colorFill = (idx, alpha) => hexToRgba(colorHex(idx), alpha);

  let labels = [];
  let fullLabels = [];
  let values = [];
  let colors = [];

  if (mode === "base") {
    const data = state.homeAnalytics?.transfers || [];
    if (!data.length) {
      if (state.mainTransferChart) state.mainTransferChart.destroy();
      legend.textContent = "Нет данных по переводам";
      if (backBtn) backBtn.hidden = true;
      if (subtitle) subtitle.textContent = "Движение денег";
      return;
    }
    labels = data.map((i) => transferLabel(i));
    fullLabels = labels;
    values = data.map((i) => Math.abs(i.amount || 0));
    colors = labels.map((_, idx) => colorFill(idx, 0.95));
    legend.appendChild(
      buildLegendWithHandler(
        data,
        colors,
        "Типы переводов",
        (item) => drillMainTransfers(item.id),
        (item) => transferLabel(item),
      )
    );
    if (backBtn) backBtn.hidden = true;
    if (subtitle) subtitle.textContent = "Движение денег";
  } else {
    const raw = state.mainTransfersMerchants || [];
    const filtered = raw.filter((i) => !((i.merchant || "").toLowerCase().includes("между своими счетами")));
    const data = (filtered.length ? filtered : raw)
      .filter((item) => Math.abs(item.amount || 0) > 0)
      .sort((left, right) => Math.abs(right.amount || 0) - Math.abs(left.amount || 0))
      .slice(0, 10);
    if (!data.length) {
      if (state.mainTransferChart) state.mainTransferChart.destroy();
      state.mainTransferChart = null;
      legend.textContent = "Нет данных по контрагентам";
      if (backBtn) backBtn.hidden = false;
      if (subtitle) subtitle.textContent = "Контрагенты переводов";
      return;
    }
    fullLabels = data.map((i) => i.merchant || "unknown");
    labels = fullLabels.map((label) => mainTransferMerchantLabel(label, 44));
    values = data.map((i) => Math.abs(i.amount || 0));
    colors = data.map((_, idx) => colorFill(idx, 0.85));
    legend.appendChild(buildLegend(labels, colors, "Контрагенты", fullLabels));
    if (backBtn) backBtn.hidden = false;
    if (subtitle) subtitle.textContent = raw.length > data.length ? `Топ-${data.length} контрагентов` : "Контрагенты переводов";
  }

  if (state.mainTransferChart) state.mainTransferChart.destroy();
  const chartType = mode === "merchant" ? "bar" : "doughnut";

  canvas.classList.toggle("bar-chart", chartType === "bar");

  const maxValue = Math.max(...values, 0);
  const suggestedMax = maxValue ? maxValue * 1.12 : 1;
  const tooltipLabel = (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x ?? ctx.parsed ?? 0)}`;

  state.mainTransferChart = new Chart(canvas, {
    type: chartType,
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          borderWidth: chartType === "bar" ? 1 : 0,
          borderColor: chartType === "bar" ? labels.map((_, idx) => colorFill(idx, 0.4)) : undefined,
          barPercentage: chartType === "bar" ? 0.58 : undefined,
          categoryPercentage: chartType === "bar" ? 0.72 : undefined,
          maxBarThickness: chartType === "bar" ? 22 : undefined,
        },
      ],
    },
    options:
      chartType === "bar"
        ? {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 220, easing: "easeOutCubic" },
            transitions: {
              active: { animation: { duration: 160 } },
            },
            indexAxis: "y",
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: (items) => {
                    const idx = items?.[0]?.dataIndex ?? 0;
                    return compactText(fullLabels[idx] || labels[idx] || "", 96);
                  },
                  label: (ctx) => formatCurrency(ctx.parsed.x ?? 0),
                },
              },
            },
            scales: {
              x: { beginAtZero: true, suggestedMax, ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
              y: {
                afterFit: (axis) => {
                  axis.width = axis.chart.width < 640 ? 170 : 260;
                },
                ticks: {
                  color: chartTextColor(),
                  font: { size: 12, lineHeight: 1.35 },
                  callback: function(val) {
                    const s = this.getLabelForValue(val) || String(val);
                    return compactText(s, this.chart.width < 640 ? 26 : 44);
                  },
                },
                grid: { color: chartGridColor() },
              },
            },
          }
        : {
            responsive: true,
            maintainAspectRatio: false,
            animation: { animateRotate: true, animateScale: true, duration: 240, easing: "easeOutCubic" },
            transitions: {
              active: { animation: { duration: 160 } },
            },
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: tooltipLabel } },
            },
            cutout: "52%",
            onHover: (evt, elements) => {
              evt.native.target.style.cursor = elements.length ? "pointer" : "default";
            },
            onClick: (evt, elements) => {
              if (elements.length) {
                const idx = elements[0].index;
                const baseId = (state.homeAnalytics?.transfers || [])[idx]?.id;
                if (baseId) drillMainTransfers(baseId);
              }
            },
          },
  });
}

function renderHomeQuickAnswers(qa) {
  const exp = document.getElementById("home-qa-expenses");
  const inc = document.getElementById("home-qa-incomes");
  if (!exp || !inc) return;
  exp.innerHTML = "";
  inc.innerHTML = "";
  const renderList = (list, target) => {
    if (!list || !list.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Нет данных";
      target.appendChild(li);
      return;
    }
    list.slice(0, 3).forEach((item) => {
      const li = document.createElement("li");
      const date = formatDate(item.date);
      const title = item.title || "-";
      const amount = formatCurrency(item.amount);
      li.className = "summary-row detail-trigger";
      li.tabIndex = 0;
      li.dataset.detailTitle = title;
      li.dataset.detailBody = `${date}\n${title}\nСумма: ${amount}`;
      li.innerHTML = `
        <span class="summary-date">${date}</span>
        <span class="summary-label">${escapeHtml(title)}</span>
        <span class="amount">${amount}</span>
      `;
      target.appendChild(li);
    });
  };
  renderList(qa?.top_expenses, exp);
  renderList(qa?.top_incomes, inc);
}

function goalSummary(profileOrText) {
  if (!profileOrText || typeof profileOrText !== "object") {
    const text = String(profileOrText || "").trim();
    return { text, detail: text };
  }

  const title = (profileOrText.goal_title || "").trim();
  const notes = (profileOrText.goals || "").trim();
  const amountRaw = Number(profileOrText.goal_amount || 0);
  const savedRaw = Number(profileOrText.goal_saved || 0);
  const amount = Number.isFinite(amountRaw) ? amountRaw : 0;
  const saved = Number.isFinite(savedRaw) ? savedRaw : 0;
  const deadline = (profileOrText.goal_deadline || "").trim();
  const hasStructured = Boolean(title || amount || saved || deadline);

  if (!hasStructured) {
    return { text: notes, detail: notes };
  }

  const heading = title || "Финансовая цель";
  const parts = [];
  const detailParts = [];
  if (amount > 0) {
    parts.push(formatCurrency(amount));
    detailParts.push(`Сумма цели: ${formatCurrency(amount)}`);
  }
  if (saved > 0) {
    detailParts.push(`Уже накоплено: ${formatCurrency(saved)}`);
  }
  if (amount > 0) {
    detailParts.push(`Осталось: ${formatCurrency(Math.max(amount - saved, 0))}`);
  }
  if (deadline) {
    parts.push(`до ${formatDate(deadline)}`);
    detailParts.push(`Срок: ${formatDate(deadline)}`);
  }
  if (notes) {
    detailParts.push(`Заметки: ${notes}`);
  }

  return {
    text: parts.length ? `${heading} · ${parts.join(" · ")}` : heading,
    detail: [heading, ...detailParts].join("\n"),
  };
}

function updateHomeGoals(profileOrText) {
  const target = document.getElementById("home-goals-text");
  if (!target) return;
  const summary = goalSummary(profileOrText);
  const value = (summary.text || "").trim();
  target.textContent = value || "Цели пока не заданы";
  target.classList.toggle("muted", !value);
  target.classList.toggle("detail-trigger", Boolean(value));
  if (value) {
    target.tabIndex = 0;
    target.dataset.detailTitle = "Цели";
    target.dataset.detailBody = summary.detail || value;
  } else {
    target.removeAttribute("tabindex");
    delete target.dataset.detailTitle;
    delete target.dataset.detailBody;
  }
}

async function renderFiles() {
  const data = await apiJson("/api/files");
  const list = document.getElementById("file-list");
  if (list) {
    list.innerHTML = "";
  }
  const select = document.getElementById("profile-file-select");
  if (select) {
    select.innerHTML = `<option value="">Нет файлов</option>`;
  }
  if (!data.files.length) {
    syncCustomSelect(select);
    return;
  }
  data.files.forEach((f) => {
    if (list) {
      const li = document.createElement("li");
      li.className = "file-item";
      li.innerHTML = `
        <div class="file-meta">
          <span class="name">${escapeHtml(f.name)}</span>
          <span class="sub">${f.bank} · ${f.count} операций</span>
        </div>
      `;
      list.appendChild(li);
    }
    if (select) {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = `${f.name} · ${f.bank} · ${f.count}`;
      select.appendChild(opt);
    }
  });
  syncCustomSelect(select);
}

async function loadOperations() {
  const start = document.getElementById("hist-start").value;
  const end = document.getElementById("hist-end").value;
  const type = document.getElementById("hist-type").value;
  const excludeTransfers = document.getElementById("hist-exclude-transfers").checked;
  const params = new URLSearchParams();
  params.set("limit", "500");
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (type !== "all") params.set("type", type);
  if (excludeTransfers) params.set("exclude_transfers", "true");
  const data = await apiJson(`/api/operations?${params.toString()}`);
  renderOperations(data.items || []);
}

function renderUnknown(items) {
  const body = document.getElementById("unknown-body");
  if (!body) return;
  body.innerHTML = "";
  if (!items.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" class="muted">Нет unknown операций</td>`;
    body.appendChild(tr);
    return;
  }
  items.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDate(item.date)}</td>
      <td>${escapeHtml(item.bank || "")}</td>
      <td>${escapeHtml(item.description || "")}</td>
      <td>${escapeHtml(item.bank_category || "")}</td>
      <td class="${item.amount < 0 ? "amount-neg" : "amount-pos"}">${formatCurrency(item.amount || 0)}</td>
    `;
    body.appendChild(tr);
  });
}

async function loadUnknown() {
  const body = document.getElementById("unknown-body");
  if (!body) return;
  const data = await apiJson("/api/unknown?limit=200");
  state.unknownItems = data.items || [];
  renderUnknown(state.unknownItems);
}

function renderCorrections(items) {
  const body = document.getElementById("corrections-body");
  const countEl = document.getElementById("corr-count");
  if (!body) return;
  body.innerHTML = "";
  if (countEl) {
    countEl.textContent = `${items.length} записей`;
  }
  if (!items.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="6" class="muted">Журнал пока пуст</td>`;
    body.appendChild(tr);
    return;
  }
  items.forEach((item) => {
    const tr = document.createElement("tr");
    const ts = item.timestamp ? formatDateTime(item.timestamp) : "-";
    const oldCategory = item.old_category_id || "unknown";
    const newCategory = item.new_category_id || "unknown";
    const source = `${item.old_source || "-"} → ${item.new_source || "-"}`;
    tr.innerHTML = `
      <td>${escapeHtml(ts)}</td>
      <td title="${escapeHtml(item.operation_id || "")}">${escapeHtml(shortId(item.operation_id || "-"))}</td>
      <td>${escapeHtml(oldCategory)}</td>
      <td>${escapeHtml(newCategory)}</td>
      <td>${escapeHtml(source)}</td>
      <td>${escapeHtml(item.reason || "-")}</td>
    `;
    body.appendChild(tr);
  });
}

async function loadCorrections() {
  const body = document.getElementById("corrections-body");
  if (!body) return;
  const data = await apiJson("/api/corrections");
  state.corrections = data.items || [];
  renderCorrections(state.corrections);
}

function setupHistoryTools() {
  const refreshUnknownBtn = document.getElementById("hist-load-unknown");
  if (refreshUnknownBtn) {
    refreshUnknownBtn.addEventListener("click", async () => {
      await loadUnknown();
      showToast("Unknown обновлен");
    });
  }

  const refreshCorrectionsBtn = document.getElementById("corr-refresh");
  if (refreshCorrectionsBtn) {
    refreshCorrectionsBtn.addEventListener("click", async () => {
      await loadCorrections();
      showToast("Журнал правок обновлен");
    });
  }

  const applyMappingBtn = document.getElementById("map-apply");
  if (applyMappingBtn) {
    applyMappingBtn.addEventListener("click", async () => {
      await ensureBaseCategoriesLoaded();
      const bank = (document.getElementById("map-bank").value || "").trim().toLowerCase();
      const bankCategory = (document.getElementById("map-bank-category").value || "").trim();
      const baseId = (document.getElementById("map-base-id").value || "").trim();
      if (!bank || !bankCategory || !baseId) {
        return showToast("Заполните bank, bank_category и base_id");
      }
      await apiJson("/api/mappings/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bank, bank_category: bankCategory, base_id: baseId }),
      });
      showToast("Custom mapping сохранен");
      await refreshAfterDataMutation({ resetPeriods: false });
    });
  }

  const undoBtn = document.getElementById("corr-undo");
  if (undoBtn) {
    undoBtn.addEventListener("click", async () => {
      const response = await safeApiFetch("/api/corrections/undo", { method: "POST" });
      if (!response.ok) {
        return showToast("Нет изменений для отката");
      }
      showToast("Последняя правка откатана");
      await refreshAfterDataMutation({ resetPeriods: false });
    });
  }
}

async function loadRecentOperations() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 7);
  const params = new URLSearchParams();
  params.set("limit", "15");
  params.set("start_date", start.toISOString().slice(0, 10));
  params.set("end_date", end.toISOString().slice(0, 10));
  const data = await apiJson(`/api/operations?${params.toString()}`);
  state.recentOps = data.items || [];
  renderRecentOperations(state.recentOps);
}

function setupHistoryDefaults() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 30);
  document.getElementById("hist-start").value = start.toISOString().slice(0, 10);
  document.getElementById("hist-end").value = end.toISOString().slice(0, 10);
}

function setupAnalyticsDefaults() {
  Object.keys(state.analyticsByTab).forEach((tab) => {
    state.analyticsByTab[tab].period = { start: "", end: "" };
  });
  syncAnalyticsInputs();
}

function applyQuickRange(mode) {
  const end = new Date();
  const start = new Date();
  if (mode === "week") start.setDate(end.getDate() - 7);
  else if (mode === "month") start.setMonth(end.getMonth() - 1);
  else if (mode === "year") start.setFullYear(end.getFullYear() - 1);
  document.getElementById("hist-start").value = start.toISOString().slice(0, 10);
  document.getElementById("hist-end").value = end.toISOString().slice(0, 10);
  loadOperations();
}

function applyAnalyticsQuickRange(tab, mode) {
  const end = new Date();
  const start = new Date();
  if (mode === "week") start.setDate(end.getDate() - 7);
  else if (mode === "month") start.setMonth(end.getMonth() - 1);
  else if (mode === "year") start.setFullYear(end.getFullYear() - 1);
  const startStr = start.toISOString().slice(0, 10);
  const endStr = end.toISOString().slice(0, 10);
  const startEl = document.getElementById(`analytics-start-${tab}`);
  const endEl = document.getElementById(`analytics-end-${tab}`);
  if (startEl) startEl.value = startStr;
  if (endEl) endEl.value = endStr;
  document.querySelectorAll(`.seg-btn[data-analytics-tab="${tab}"]`).forEach((b) => {
    b.classList.toggle("active", b.dataset.analyticsQuick === mode);
  });
  state.analyticsByTab[tab].period = { start: startStr, end: endStr };
  if (tab === activeAnalyticsTab) refresh();
}

function syncAnalyticsInputs() {
  const period = state.analyticsByTab[activeAnalyticsTab].period;
  const startEl = document.getElementById(`analytics-start-${activeAnalyticsTab}`);
  const endEl = document.getElementById(`analytics-end-${activeAnalyticsTab}`);
  if (startEl) startEl.value = period.start || "";
  if (endEl) endEl.value = period.end || "";
}

function renderTransfers() {
  const list = document.getElementById("transfer-list");
  if (!list) return;
  list.innerHTML = "";
  const items = state.transfers.baseData || [];
  if (!items.length) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="tag">Нет переводов в выбранном периоде</span>`;
    list.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    const title = transferLabel(item);
    const amount = Math.abs(item.amount || 0);
    li.innerHTML = `<span class="tag">${title}</span><span class="amount-pos">${formatCurrency(amount)}</span>`;
    list.appendChild(li);
  });
}

function renderSubscriptions() {
  const items = state.subscriptions.items || [];
  const list = document.getElementById("subscription-list");
  if (!list) return;
  if (items.length && !items.some((item) => item.key === state.subscriptions.selected)) {
    state.subscriptions.selected = items[0].key;
  }
  renderSubscriptionButtons(items, list, {
    emptyText: "Подписок в выбранном периоде не найдено",
    selectedKey: state.subscriptions.selected,
    onClick: (item) => {
      state.subscriptions.selected = item.key;
      renderSubscriptions();
    },
  });
  loadSubscriptionOperations(state.subscriptions.selected).catch(() => {});
}

function renderSubscriptionButtons(items, list, { emptyText, selectedKey = "", onClick }) {
  list.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = emptyText;
    list.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    const subtitle = `${formatCurrency(item.amount || 0)} в месяц · ${item.operations_count || 0} спис. · последнее ${formatDate(item.last_date)}`;
    button.type = "button";
    button.className = `subscription-item${item.key === selectedKey ? " active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(String(item.name || item.key || "Подписка"))}</strong>
      <span>${escapeHtml(subtitle)}</span>
    `;
    button.addEventListener("click", () => onClick(item));
    li.appendChild(button);
    list.appendChild(li);
  });
}

async function loadSubscriptionOperations(key) {
  const title = document.getElementById("subscription-detail-title");
  const subtitle = document.getElementById("subscription-detail-subtitle");
  const body = document.getElementById("subscription-ops-body");
  if (!body) return;
  body.innerHTML = "";
  const item = (state.subscriptions.items || []).find((candidate) => candidate.key === key);
  if (!key || !item) {
    if (title) title.textContent = "Операции по подписке";
    if (subtitle) subtitle.textContent = "Выберите компанию слева";
    body.innerHTML = `<tr><td colspan="5" class="muted">Нет выбранной подписки</td></tr>`;
    return;
  }
  if (title) title.textContent = item.name || "Подписка";
  if (subtitle) {
    subtitle.textContent = `Оценка: ${formatCurrency(item.amount || 0)} в месяц · интервал ${item.median_interval_days || "-"} дн.`;
  }
  const period = state.analyticsByTab.subscriptions.period || {};
  const params = new URLSearchParams();
  params.set("limit", "200");
  params.set("type", "expense");
  params.set("exclude_transfers", "true");
  params.set("subscription_key", key);
  if (period.start) params.set("start_date", period.start);
  if (period.end) params.set("end_date", period.end);
  const data = await apiJson(`/api/operations?${params.toString()}`);
  state.subscriptions.operations = data.items || [];
  renderSubscriptionOperations(state.subscriptions.operations);
}

function renderSubscriptionOperations(items) {
  const body = document.getElementById("subscription-ops-body");
  if (!body) return;
  body.innerHTML = "";
  if (!items.length) {
    body.innerHTML = `<tr><td colspan="5" class="muted">Нет операций за выбранный период</td></tr>`;
    return;
  }
  items.forEach((op) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDate(op.date)}</td>
      <td>${escapeHtml(op.bank || "")}</td>
      <td>${escapeHtml(op.description || "")}</td>
      <td>${escapeHtml(op.category_name || op.category_id || "-")}</td>
      <td class="${op.amount < 0 ? "amount-neg" : "amount-pos"}">${formatCurrency(op.amount)}</td>
    `;
    body.appendChild(tr);
  });
}

function buildLegendWithHandler(dataItems, colors, title, onClick, labelGetter = null) {
  const wrapper = document.createElement("div");
  wrapper.className = "legend-group";
  const heading = document.createElement("p");
  heading.className = "legend-title";
  heading.textContent = title;
  wrapper.appendChild(heading);
  const list = document.createElement("div");
  list.className = "legend-list";
  dataItems.forEach((item, idx) => {
    const el = document.createElement("div");
    el.className = "legend-item clickable";
    const label = String((labelGetter ? labelGetter(item) : item.name || item.id) || "");
    el.title = label;
    el.innerHTML = `<span class="dot" style="background:${colors[idx]};"></span><span>${escapeHtml(label)}</span>`;
    el.addEventListener("click", () => onClick(item));
    list.appendChild(el);
  });
  wrapper.appendChild(list);
  return wrapper;
}

async function drillMainTransfers(baseId) {
  state.mainTransfersSelected = baseId;
  state.mainTransfersMode = "merchant";
  const data = await apiJson(`/api/merchant-breakdown?base_id=${encodeURIComponent(baseId)}`);
  state.mainTransfersMerchants = data.items || [];
  renderMainTransfersChart();
}

function renderTransfersChart() {
  const ctx = document.getElementById("transferChart");
  const legend = document.getElementById("transferLegend");
  const titleEl = document.getElementById("transfer-chart-title");
  const subtitleEl = document.getElementById("transfer-chart-subtitle");
  const backBtn = document.getElementById("transfer-chart-back");
  if (!ctx || !legend) return;

  legend.innerHTML = "";
  const mode = state.transfers.mode || "base";
  const colorHex = (idx) => SYS_COLORS[idx % SYS_COLORS.length];
  const colorFill = (idx, alpha) => hexToRgba(colorHex(idx), alpha);

  let labels = [];
  let values = [];
  let colors = [];

  if (mode === "base") {
    const data = (state.transfers.baseData || []).filter((i) => Math.abs(i.amount || 0) > 0);
    if (!data.length) {
      if (state.transfers.chart) state.transfers.chart.destroy();
      titleEl.textContent = "Типы переводов";
      subtitleEl.textContent = "Нет данных за выбранный период";
      if (backBtn) backBtn.hidden = true;
      return;
    }
    labels = data.map((i) => transferLabel(i));
    values = data.map((i) => Math.abs(i.amount || 0));
    colors = labels.map((_, idx) => colorFill(idx, 0.9));
    legend.appendChild(buildInteractiveLegend(data, colors, "transfers"));
    titleEl.textContent = "Типы переводов";
    subtitleEl.textContent = "Входящие, исходящие и пополнения";
    if (backBtn) backBtn.hidden = true;
  } else {
    const raw = state.transfers.merchantData || [];
    const filtered = raw.filter((i) => !((i.merchant || "").toLowerCase().includes("между своими счетами")));
    const data = filtered.length ? filtered : raw;
    if (!data.length) {
      if (state.transfers.chart) state.transfers.chart.destroy();
      titleEl.textContent = "Контрагенты";
      subtitleEl.textContent = "Нет данных по контрагентам";
      if (backBtn) backBtn.hidden = false;
      return;
    }
    labels = data.map((i) => i.merchant || "unknown");
    values = data.map((i) => i.amount);
    colors = labels.map((_, idx) => colorFill(idx, 0.82));
    legend.appendChild(buildLegend(labels, colors, "Контрагенты"));
    titleEl.textContent = "Контрагенты";
    subtitleEl.textContent = "Крупнейшие получатели и отправители";
    if (backBtn) backBtn.hidden = false;
  }

  if (state.transfers.chart) state.transfers.chart.destroy();
  const chartType = mode === "merchant" ? "bar" : "doughnut";
  const maxValue = Math.max(...values, 0);
  const suggestedMax = maxValue ? maxValue * 1.12 : 1;
  const tooltipLabel = (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x ?? ctx.parsed ?? 0)}`;

  state.transfers.chart = new Chart(ctx, {
    type: chartType,
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors,
          borderWidth: chartType === "bar" ? 1 : 0,
          borderColor: chartType === "bar" ? labels.map((_, idx) => colorFill(idx, 0.45)) : undefined,
        },
      ],
    },
    options:
      chartType === "bar"
        ? {
            indexAxis: "y",
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: tooltipLabel } } },
            scales: {
              x: { beginAtZero: true, suggestedMax, ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
              y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
            },
          }
        : {
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: tooltipLabel } } },
            cutout: "50%",
            onHover: (evt, elements) => {
              evt.native.target.style.cursor = elements.length ? "pointer" : "default";
            },
          },
  });
}

function setupAgent() {
  const toggle = document.getElementById("agent-toggle");
  const panel = document.getElementById("agent-panel");
  const closeBtn = document.getElementById("agent-close");
  const sendBtn = document.getElementById("agent-send");
  const input = document.getElementById("agent-question");
  const messages = document.getElementById("agent-messages");
  const status = document.getElementById("agent-status");

  toggle.title = "Открыть финансового агента";

  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      panel.hidden = false;
      requestAnimationFrame(() => panel.classList.add("is-open"));
      input.focus();
    } else {
      panel.classList.remove("is-open");
      window.setTimeout(() => {
        if (!panel.classList.contains("is-open")) panel.hidden = true;
      }, 220);
    }
  };

  function setStatus(text) {
    if (status) status.textContent = text;
  }

  function appendInlineFormatted(parent, text) {
    const source = String(text || "");
    const pattern = /(\*\*[^*]+?\*\*|`[^`]+?`)/g;
    let lastIndex = 0;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      if (match.index > lastIndex) {
        parent.appendChild(document.createTextNode(source.slice(lastIndex, match.index)));
      }
      const token = match[0];
      const node = document.createElement(token.startsWith("`") ? "code" : "strong");
      node.textContent = token.slice(token.startsWith("`") ? 1 : 2, token.endsWith("`") ? -1 : -2);
      parent.appendChild(node);
      lastIndex = match.index + token.length;
    }
    if (lastIndex < source.length) {
      parent.appendChild(document.createTextNode(source.slice(lastIndex)));
    }
  }

  function appendParagraph(container, lines) {
    const text = lines.join(" ").replace(/\s+/g, " ").trim();
    if (!text) return;
    const p = document.createElement("p");
    appendInlineFormatted(p, text);
    container.appendChild(p);
  }

  function appendListItem(list, text) {
    const li = document.createElement("li");
    appendInlineFormatted(li, text);
    list.appendChild(li);
  }

  function renderAgentContent(container, text) {
    container.innerHTML = "";
    const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    let paragraph = [];
    let list = null;
    let listType = "";

    const flushParagraph = () => {
      appendParagraph(container, paragraph);
      paragraph = [];
    };
    const closeList = () => {
      list = null;
      listType = "";
    };
    const ensureList = (type) => {
      if (!list || listType !== type) {
        flushParagraph();
        list = document.createElement(type === "ordered" ? "ol" : "ul");
        container.appendChild(list);
        listType = type;
      }
      return list;
    };

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        flushParagraph();
        closeList();
        return;
      }

      const bullet = trimmed.match(/^[-*]\s+(.+)$/);
      if (bullet) {
        appendListItem(ensureList("unordered"), bullet[1]);
        return;
      }

      const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
      if (numbered) {
        appendListItem(ensureList("ordered"), numbered[1]);
        return;
      }

      closeList();
      const heading = trimmed.match(/^\*\*(.+?)\*\*:?\s*$/);
      const plainHeading = !heading && trimmed.length <= 72 && /:$/.test(trimmed) && !/[.!?]$/.test(trimmed.slice(0, -1));
      if (heading || plainHeading) {
        flushParagraph();
        const h = document.createElement("h4");
        appendInlineFormatted(h, heading ? heading[1] : trimmed.slice(0, -1));
        container.appendChild(h);
        return;
      }

      paragraph.push(trimmed);
    });
    flushParagraph();
  }

  function streamTextInto(body, text) {
    const tokens = String(text || "").match(/\S+\s*/g) || [""];
    const step = tokens.length > 220 ? 4 : tokens.length > 120 ? 3 : tokens.length > 60 ? 2 : 1;
    let index = 0;
    let visible = "";
    return new Promise((resolve) => {
      const tick = () => {
        for (let i = 0; i < step && index < tokens.length; i += 1) {
          visible += tokens[index];
          index += 1;
        }
        renderAgentContent(body, visible);
        messages.scrollTop = messages.scrollHeight;
        if (index < tokens.length) {
          window.setTimeout(tick, 22);
        } else {
          resolve();
        }
      };
      tick();
    });
  }

  function appendMessage(text, role = "agent", meta = "") {
    const div = document.createElement("div");
    div.className = `agent-msg ${role === "user" ? "user" : "agent"}`;
    const body = document.createElement("div");
    body.className = "agent-content";
    if (role === "agent") {
      renderAgentContent(body, text);
    } else {
      body.textContent = text;
    }
    div.appendChild(body);
    if (meta) {
      const metaEl = document.createElement("span");
      metaEl.className = "agent-meta";
      metaEl.textContent = meta;
      div.appendChild(metaEl);
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  async function appendStreamingMessage(text, meta = "") {
    const div = document.createElement("div");
    div.className = "agent-msg agent streaming";
    const body = document.createElement("div");
    body.className = "agent-content";
    div.appendChild(body);
    if (meta) {
      const metaEl = document.createElement("span");
      metaEl.className = "agent-meta";
      metaEl.textContent = meta;
      div.appendChild(metaEl);
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    await streamTextInto(body, text || "Нет ответа");
    div.classList.remove("streaming");
    return div;
  }

  function appendLoading() {
    const div = document.createElement("div");
    div.className = "agent-msg agent loading";
    div.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  async function sendMessage() {
    const q = input.value.trim();
    if (!q || sendBtn.disabled) return;
    appendMessage(q, "user", "Вы");
    input.value = "";
    sendBtn.disabled = true;
    input.disabled = true;
    setStatus("Анализирую запрос");
    const loading = appendLoading();
    try {
      const data = await apiJson("/api/agent-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      loading.remove();
      const sourceLabel =
        data.source === "llm"
          ? `LLM · ${data.model || "модель"}`
          : data.tier === "conversation"
            ? "Локально"
          : data.tier === "factual"
            ? "Локально · навигация"
            : "Локально · расчёт";
      setStatus("Печатаю ответ");
      await appendStreamingMessage(data.answer || "Нет ответа", sourceLabel);
      setStatus("Готов к вопросам");
    } catch (e) {
      loading.remove();
      const msg = appendMessage("Не удалось получить ответ. Проверь подключение или попробуй ещё раз.", "agent", "Ошибка");
      msg.classList.add("error");
      setStatus("Ошибка ответа");
    } finally {
      sendBtn.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  toggle.addEventListener("click", () => {
    setOpen(panel.hidden || !panel.classList.contains("is-open"));
  });
  closeBtn.addEventListener("click", () => {
    setOpen(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) {
      setOpen(false);
    }
  });
  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });
}

async function revokeCurrentSession() {
  if (!authToken) return;
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch (e) {
    // Локальная блокировка всё равно должна сработать.
  }
}

function lockApp(subtitle = "Введите пароль, чтобы открыть данные") {
  authToken = "";
  localStorage.removeItem("auth_token");
  const passwordInput = document.getElementById("auth-password");
  if (passwordInput) passwordInput.value = "";
  showAuthLoginScreen(subtitle);
}

async function changeAccountPassword(values) {
  const currentPassword = (values.current || "").trim();
  const newPassword = (values.next || "").trim();
  const repeatedPassword = (values.repeat || "").trim();
  if (!currentPassword || !newPassword || !repeatedPassword) {
    throw new Error("Заполните все поля");
  }
  if (newPassword.length < 4) {
    throw new Error("Новый пароль должен быть не короче 4 символов");
  }
  if (newPassword !== repeatedPassword) {
    throw new Error("Новый пароль и повтор не совпадают");
  }

  const res = await apiFetch("/api/auth/change", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (data.error === "invalid_current_password") {
      throw new Error("Текущий пароль указан неверно");
    }
    if (data.error === "too_short") {
      throw new Error("Новый пароль должен быть не короче 4 символов");
    }
    if (data.error === "unauthorized") {
      handleUnauthorized();
      throw new Error("Сессия истекла. Войдите заново");
    }
    throw new Error("Не удалось сменить пароль");
  }
  authToken = data.token || "";
  localStorage.setItem("auth_token", authToken);
  showToast("Пароль изменён");
}

function setupSecurityActions() {
  const lockBtn = document.getElementById("account-lock-now");
  const logoutBtn = document.getElementById("account-logout");
  const changePasswordBtn = document.getElementById("account-change-password");
  const deleteAll = document.getElementById("delete-all");

  if (lockBtn) {
    lockBtn.addEventListener("click", () => {
      showActionDialog({
        title: "Заблокировать доступ",
        message: "Текущая сессия будет завершена. Для продолжения потребуется пароль приложения.",
        confirmText: "Заблокировать",
        onConfirm: async () => {
          await revokeCurrentSession();
          lockApp("Доступ заблокирован. Введите пароль, чтобы продолжить");
        },
      });
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      showActionDialog({
        title: "Выйти",
        message: "Текущая сессия на этом устройстве будет завершена. Данные останутся на месте.",
        confirmText: "Выйти",
        onConfirm: async () => {
          await revokeCurrentSession();
          lockApp("Вы вышли. Введите пароль, чтобы открыть данные");
        },
      });
    });
  }

  if (changePasswordBtn) {
    changePasswordBtn.addEventListener("click", () => {
      showActionDialog({
        title: "Сменить пароль",
        message: "После смены пароля текущие токены будут отозваны, а данные будут сохранены с новым ключом.",
        confirmText: "Сменить пароль",
        fields: [
          { id: "current", label: "Текущий пароль", type: "password" },
          { id: "next", label: "Новый пароль", type: "password" },
          { id: "repeat", label: "Повторите новый пароль", type: "password" },
        ],
        onConfirm: changeAccountPassword,
      });
    });
  }

  if (deleteAll) {
    deleteAll.addEventListener("click", () => {
      showActionDialog({
        title: "Удалить данные",
        message: "Будут удалены загруженные файлы, операции, правки категорий и custom mapping. Пароль входа останется.",
        confirmText: "Удалить данные",
        danger: true,
        onConfirm: async () => {
          await safeApiFetch("/api/reset", { method: "POST" });
          showToast("Данные удалены");
          await refreshAfterDataMutation();
        },
      });
    });
  }
}

// Профиль: удаление файла
document.addEventListener("DOMContentLoaded", () => {
  const deleteBtn = document.getElementById("profile-file-delete");
  const select = document.getElementById("profile-file-select");
  if (deleteBtn && select) {
    deleteBtn.addEventListener("click", async () => {
      const id = select.value;
      if (!id) return;
      await safeApiFetch("/api/files/" + id, { method: "DELETE" });
      showToast("Файл удалён");
      await refreshAfterDataMutation();
    });
  }

  setupSecurityActions();

  const profileResetBtn = document.getElementById("profile-reset-btn");
  if (profileResetBtn) {
    profileResetBtn.addEventListener("click", async () => {
      await safeApiFetch("/api/reset", { method: "POST" });
      showToast("Сессия сброшена");
      await refreshAfterDataMutation();
    });
  }
});

function showToast(text) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
  }
  // всегда размещаем поверх, чтобы видеть из любой секции
  document.body.appendChild(toast);
  toast.classList.add("toast-floating");
  toast.textContent = text;
  toast.hidden = false;
  setTimeout(() => (toast.hidden = true), 2500);
}

function formatCurrency(value) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);
}

function formatDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

function formatDateTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const datePart = formatDate(value);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${datePart} ${hh}:${mm}`;
}

function shortId(value) {
  if (!value) return "-";
  if (value.length <= 10) return value;
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function formatPercent(value) {
  if (value === undefined || value === null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function hexToRgba(hex, alpha = 1) {
  const sanitized = hex.replace("#", "");
  const bigint = parseInt(sanitized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function buildLegend(labels, colors, title, detailLabels = []) {
  const wrapper = document.createElement("div");
  wrapper.className = "legend-group";
  const heading = document.createElement("p");
  heading.className = "legend-title";
  heading.textContent = title;
  wrapper.appendChild(heading);
  const list = document.createElement("div");
  list.className = "legend-list";
  labels.forEach((label, idx) => {
    const safeLabel = String(label || "");
    const fullLabel = String(detailLabels[idx] || safeLabel);
    const item = document.createElement("div");
    item.className = "legend-item detail-trigger";
    item.tabIndex = 0;
    item.title = fullLabel;
    item.dataset.detailTitle = title || "Детали";
    item.dataset.detailBody = fullLabel;
    item.innerHTML = `<span class="dot" style="background:${colors[idx]};"></span><span>${escapeHtml(safeLabel)}</span>`;
    list.appendChild(item);
  });
  wrapper.appendChild(list);
  return wrapper;
}

function buildInteractiveLegend(dataItems, colors, kind) {
  const labels = dataItems.map((i) => (kind === "transfers" ? transferLabel(i) : i.name));
  const wrapper = document.createElement("div");
  wrapper.className = "legend-group";
  const heading = document.createElement("p");
  heading.className = "legend-title";
  heading.textContent = "Категории";
  wrapper.appendChild(heading);
  const list = document.createElement("div");
  list.className = "legend-list";
  labels.forEach((label, idx) => {
    const item = document.createElement("div");
    item.className = "legend-item clickable";
    item.innerHTML = `<span class="dot" style="background:${colors[idx]};"></span><span>${label}</span>`;
    item.addEventListener("click", () => drillToMerchants(kind, dataItems[idx].id));
    list.appendChild(item);
  });
  wrapper.appendChild(list);
  return wrapper;
}
