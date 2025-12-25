let trendChart;
const SYS_COLORS = ["#A55DE8", "#5BB4FF", "#FFB86B", "#FF8FA3", "#7C4DFF", "#4EC2FF", "#6FCF97", "#F2C94C"];

const state = {
  expense: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  income: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  transfers: { mode: "base", selected: null, baseData: [], merchantData: [], chart: null },
  trendMode: "monthly",
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
  quickCharts: { balance: null, topCats: null },
  recentOps: [],
  analyticsByTab: {
    expense: { period: { start: "", end: "" }, data: null },
    income: { period: { start: "", end: "" }, data: null },
    transfers: { period: { start: "", end: "" }, data: null },
    quick: { period: { start: "", end: "" }, data: null },
  },
};
let activeAnalyticsTab = "expense";

let authToken = localStorage.getItem("auth_token") || "";
let appInitialized = false;

document.addEventListener("DOMContentLoaded", () => {
  setupAuth();
});

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
  return res;
}

function handleUnauthorized() {
  authToken = "";
  localStorage.removeItem("auth_token");
  const screen = document.getElementById("auth-screen");
  if (screen) screen.style.display = "flex";
  appInitialized = false;
}

function setupAuth() {
  const screen = document.getElementById("auth-screen");
  const loginForm = document.getElementById("auth-login-form");
  const createForm = document.getElementById("auth-create-form");
  const loginError = document.getElementById("auth-error");
  const createError = document.getElementById("auth-create-error");
  const title = document.getElementById("auth-title");
  const subtitle = document.getElementById("auth-subtitle");

  const showLogin = () => {
    screen.style.display = "flex";
    loginForm.classList.remove("hidden");
    createForm.classList.add("hidden");
    title.textContent = "Вход";
    subtitle.textContent = "Введите пароль, чтобы открыть данные";
  };

  const showCreate = () => {
    screen.style.display = "flex";
    loginForm.classList.add("hidden");
    createForm.classList.remove("hidden");
    title.textContent = "Создание пароля";
    subtitle.textContent = "Задайте пароль, чтобы защитить доступ";
  };

  const hideScreen = () => {
    screen.style.display = "none";
  };

  // показать форму сразу, чтобы не оставлять пустой экран даже если статус не загрузился
  showLogin();

  fetch("/api/auth/status")
    .then((r) => r.json())
    .then((data) => {
      if (data.password_set) {
        showLogin();
        if (authToken) {
          hideScreen();
          startApp();
        }
      } else {
        showCreate();
      }
    })
    .catch(() => {
      showLogin();
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
    hideScreen();
    startApp();
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
    hideScreen();
    startApp();
  });
}

function startApp() {
  if (appInitialized) return;
  appInitialized = true;

  const form = document.getElementById("upload-form");
  const demoBtn = document.getElementById("demo-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const bank = document.getElementById("bank").value;
    const fileInput = document.getElementById("file");
    if (!fileInput.files.length) {
      return showToast("Выберите CSV-файл");
    }
    const data = new FormData();
    data.append("bank", bank);
    data.append("file", fileInput.files[0]);
    await safeApiFetch("/api/import", { method: "POST", body: data });
    showToast("Импорт завершён");
    refresh();
  });

  demoBtn.addEventListener("click", async () => {
    await safeApiFetch("/api/import-demo", { method: "POST" });
    showToast("Демо-данные загружены");
    refresh();
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

  document.querySelectorAll(".seg-btn[data-trend]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-trend]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.trendMode = btn.dataset.trend;
      renderTrendChart();
    });
  });

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

  ["expense", "income", "transfers", "quick"].forEach((tab) => {
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
}

function hydrateGoalsFromStorage() {
  const goalsEl = document.getElementById("agent-goals");
  const stored = localStorage.getItem("user_goals") || "";
  if (goalsEl) {
    goalsEl.value = stored;
  }
  updateHomeGoals(stored);
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
    priority: document.getElementById("profile-priority"),
    tone: document.getElementById("profile-tone"),
    pin: document.getElementById("profile-pin"),
  };
  const saveBtn = document.getElementById("profile-save-btn");
  if (!saveBtn) return;

  const loadProfile = () => {
    const raw = localStorage.getItem("user_profile");
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      Object.entries(fields).forEach(([key, el]) => {
        if (el && data[key] !== undefined) el.value = data[key];
      });
    } catch (e) {
      console.warn("Failed to parse saved profile", e);
    }
  };

  const hasAnyValue = () =>
    Object.values(fields).some((el) => el && typeof el.value === "string" && el.value.trim().length);

  const toggleButton = () => {
    saveBtn.disabled = !hasAnyValue();
  };

  const saveProfile = () => {
    const payload = {};
    Object.entries(fields).forEach(([key, el]) => {
      payload[key] = el ? el.value : "";
    });
    localStorage.setItem("user_profile", JSON.stringify(payload));
    showToast("Профиль сохранён локально");
    toggleButton();
  };

  Object.values(fields).forEach((el) => {
    if (!el) return;
    el.addEventListener("input", toggleButton);
  });
  saveBtn.addEventListener("click", saveProfile);

  loadProfile();
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
  } else if (tab === "quick") {
    state.expense.baseData = analytics.by_base_expense || [];
    state.income.baseData = analytics.by_base_income || [];
    renderQuickAnswers();
    renderTrendChart();
    renderQuickBalanceSpark();
    renderQuickTopExpenseCats();
    renderQuickBestWorst();
  }
  updateCards();
}

function switchSection(targetId, btn) {
  document.querySelectorAll(".section").forEach((sec) => sec.classList.add("hidden"));
  document.getElementById(targetId).classList.remove("hidden");
  document.querySelectorAll(".nav-btn[data-target]").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
}

function switchAnalytics(targetId, btn) {
  document.querySelectorAll(".analytics-view").forEach((sec) => sec.classList.add("hidden"));
  document.getElementById(targetId).classList.remove("hidden");
  document.querySelectorAll(".nav-btn[data-analytics-target]").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  activeAnalyticsTab = targetId.replace("-view", "");
  syncAnalyticsInputs();
  if (state.analyticsByTab[activeAnalyticsTab].data) {
    renderAnalyticsForTab(activeAnalyticsTab);
  } else {
    refresh();
  }
}

function updateCards(data) {
  const source = data || state.homeAnalytics;
  if (!source) return;
  const format = (v) => formatCurrency(v);
  document.getElementById("income").textContent = format(source.totals.income);
  document.getElementById("expense").textContent = format(source.totals.expense);
  document.getElementById("net").textContent = format(source.totals.net);
  document.getElementById("unknown").textContent = source.unknown;
  document.getElementById("unmapped").textContent = source.unmapped.length;
  const opsCount =
    (source && (source.ops_count_total || source.ops_count)) || (state.homeAnalytics && state.homeAnalytics.ops_count_total) || 0;
  const opsEl = document.getElementById("profile-ops-count");
  if (opsEl) opsEl.textContent = opsCount;
}

function renderHomeSummary() {
  const storedGoals = localStorage.getItem("user_goals") || "";
  updateHomeGoals(storedGoals);
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

function renderTrendChart() {
  if (!state.analytics) return;
  const mode = state.trendMode;
  const map = {
    monthly: state.analytics.trend,
    weekly: state.analytics.trend_weekly,
    daily: state.analytics.trend_daily,
  };
  const items = map[mode] || [];
  const ctx = document.getElementById("trendChart");
  const labels = items.map((i) => i.label);
  const income = items.map((i) => i.income);
  const expense = items.map((i) => i.expense);
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Доходы",
          data: income,
          borderColor: "#5bb4ff",
          backgroundColor: "rgba(91, 180, 255, 0.18)",
          tension: 0.35,
          fill: true,
        },
        {
          label: "Расходы",
          data: expense,
          borderColor: "#ff9b9b",
          backgroundColor: "rgba(255, 155, 155, 0.18)",
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#e9edf5" } } },
      scales: {
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.06)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.06)" } },
      },
    },
  });
}

// Доп. графики: доходы/трансферы/быстрые ответы
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
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { display: false } },
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
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" }, beginAtZero: true },
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
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" }, beginAtZero: true },
      },
    },
  });
}

function renderTransfersPlaceholders() {
  // Пока нет детальных данных по способам/парам счетов – оставляем плейсхолдеры
}

function renderQuickBalanceSpark() {
  const canvas = document.getElementById("quickBalanceSpark");
  if (!canvas || !state.analytics) return;
  const items = state.analytics.trend || [];
  if (state.quickCharts.balance) state.quickCharts.balance.destroy();
  if (!items.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  let acc = 0;
  const values = items.map((i) => {
    acc += (i.income || 0) + (i.expense || 0);
    return acc;
  });
  const labels = items.map((i) => i.label);
  state.quickCharts.balance = new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [{ data: values, borderColor: "#7bb4ff", backgroundColor: "rgba(123, 180, 255, 0.12)", tension: 0.3, fill: true, pointRadius: 0 }] },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.y)}` } } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

function renderQuickTopExpenseCats() {
  const canvas = document.getElementById("quickTopExpenseCats");
  if (!canvas) return;
  const data = (state.expense.baseData || []).filter((i) => i.amount < 0);
  const sorted = data.sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount)).slice(0, 3);
  if (state.quickCharts.topCats) state.quickCharts.topCats.destroy();
  if (!sorted.length) {
    canvas.replaceWith(canvas.cloneNode());
    return;
  }
  const labels = sorted.map((i) => i.name);
  const values = sorted.map((i) => Math.abs(i.amount || 0));
  const colors = labels.map((_, idx) => hexToRgba(SYS_COLORS[idx % SYS_COLORS.length], 0.9));
  state.quickCharts.topCats = new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x)}` } } },
      scales: { x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" } }, y: { ticks: { color: "#e9edf5" }, grid: { display: false } } },
      onClick: (evt, elements) => {
        if (!elements.length) return;
        const idx = elements[0].index;
        const cat = sorted[idx];
        if (cat?.id) {
          state.expenseFilterCategory = cat.id;
          showToast(`Фильтр по категории: ${cat.name}`);
        }
      },
    },
  });
}

function renderQuickBestWorst() {
  const placeholder = document.getElementById("quickBestWorstPlaceholder");
  if (!placeholder) return;
  placeholder.textContent = "Нет достаточных данных для расчёта";
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
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed.x)} (${((ctx.parsed.x / values.reduce((s, v) => s + v, 0)) * 100).toFixed(1)}%)`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { display: false } },
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
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" }, beginAtZero: true },
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
        x: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.1)" }, beginAtZero: true },
      },
    },
  });
}

function renderOperations(items) {
  const body = document.getElementById("ops-body");
  body.innerHTML = "";
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

function renderMainTransfersChart() {
  const canvas = document.getElementById("mainTransferChart");
  const legend = document.getElementById("mainTransferLegend");
  const backBtn = document.getElementById("main-transfer-back");
  if (!canvas || !legend) return;

  legend.innerHTML = "";
  const mode = state.mainTransfersMode || "base";
  const colorHex = (idx) => SYS_COLORS[idx % SYS_COLORS.length];
  const colorFill = (idx, alpha) => hexToRgba(colorHex(idx), alpha);

  let labels = [];
  let values = [];
  let colors = [];

  if (mode === "base") {
    const data = state.homeAnalytics?.transfers || [];
    if (!data.length) {
      if (state.mainTransferChart) state.mainTransferChart.destroy();
      legend.textContent = "Нет данных по переводам";
      if (backBtn) backBtn.hidden = true;
      return;
    }
    labels = data.map((i) => i.name || i.id);
    values = data.map((i) => Math.abs(i.amount || 0));
    colors = labels.map((_, idx) => colorFill(idx, 0.95));
    legend.appendChild(buildLegendWithHandler(data, colors, "Категории переводов", (item) => drillMainTransfers(item.id)));
    if (backBtn) backBtn.hidden = true;
  } else {
    const raw = state.mainTransfersMerchants || [];
    const filtered = raw.filter((i) => !((i.merchant || "").toLowerCase().includes("между своими счетами")));
    const data = filtered.length ? filtered : raw;
    if (!data.length) {
      if (state.mainTransferChart) state.mainTransferChart.destroy();
      legend.textContent = "Нет данных по мерчантам";
      if (backBtn) backBtn.hidden = false;
      return;
    }
    labels = data.map((i) => i.merchant || "unknown");
    values = data.map((i) => i.amount);
    colors = labels.map((_, idx) => colorFill(idx, 0.85));
    legend.appendChild(buildLegend(labels, colors, "Мерчанты"));
    if (backBtn) backBtn.hidden = false;
  }

  if (state.mainTransferChart) state.mainTransferChart.destroy();
  const chartType = mode === "merchant" ? "bar" : "doughnut";
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
        },
      ],
    },
    options:
      chartType === "bar"
        ? {
            indexAxis: "y",
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: tooltipLabel } } },
            scales: {
              x: { beginAtZero: true, suggestedMax, ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.14)" } },
              y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
            },
          }
        : {
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: tooltipLabel } },
            },
            cutout: "52%",
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
      li.innerHTML = `<span>${formatDate(item.date)}</span><span>${escapeHtml(item.title)}</span><span class="amount">${formatCurrency(item.amount)}</span>`;
      target.appendChild(li);
    });
  };
  renderList(qa?.top_expenses, exp);
  renderList(qa?.top_incomes, inc);
}

function updateHomeGoals(text) {
  const target = document.getElementById("home-goals-text");
  if (!target) return;
  const value = (text || "").trim();
  target.textContent = value || "Цели пока не заданы";
  target.classList.toggle("muted", !value);
}

async function renderFiles() {
  const data = await apiJson("/api/files");
  const list = document.getElementById("file-list");
  list.innerHTML = "";
  const select = document.getElementById("profile-file-select");
  if (select) {
    select.innerHTML = `<option value="">Нет файлов</option>`;
  }
  if (!data.files.length) {
    list.innerHTML = `<li class="file-item"><div class="file-meta"><span class="name">Нет загруженных файлов</span><span class="sub">Импортируйте CSV</span></div></li>`;
    return;
  }
  data.files.forEach((f) => {
    const li = document.createElement("li");
    li.className = "file-item";
    li.innerHTML = `
      <div class="file-meta">
        <span class="name">${escapeHtml(f.name)}</span>
        <span class="sub">${f.bank} · ${f.count} операций</span>
      </div>
    `;
    list.appendChild(li);
    if (select) {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = `${f.name} · ${f.bank} · ${f.count}`;
      select.appendChild(opt);
    }
  });
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
    const title = item.name || item.id;
    const amount = Math.abs(item.amount || 0);
    li.innerHTML = `<span class="tag">${title}</span><span class="amount-pos">${formatCurrency(amount)}</span>`;
    list.appendChild(li);
  });
}

function buildLegendWithHandler(dataItems, colors, title, onClick) {
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
    el.innerHTML = `<span class="dot" style="background:${colors[idx]};"></span><span>${item.name || item.id}</span>`;
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
      titleEl.textContent = "Переводы по категориям";
      subtitleEl.textContent = "Нет данных за выбранный период";
      if (backBtn) backBtn.hidden = true;
      return;
    }
    labels = data.map((i) => i.name || i.id);
    values = data.map((i) => Math.abs(i.amount || 0));
    colors = labels.map((_, idx) => colorFill(idx, 0.9));
    legend.appendChild(buildInteractiveLegend(data, colors, "transfers"));
    titleEl.textContent = "Переводы по категориям";
    subtitleEl.textContent = "Пополнения, снятия и внутренние движения";
    if (backBtn) backBtn.hidden = true;
  } else {
    const raw = state.transfers.merchantData || [];
    const filtered = raw.filter((i) => !((i.merchant || "").toLowerCase().includes("между своими счетами")));
    const data = filtered.length ? filtered : raw;
    if (!data.length) {
      if (state.transfers.chart) state.transfers.chart.destroy();
      titleEl.textContent = "Мерчанты";
      subtitleEl.textContent = "Нет данных по мерчантам";
      if (backBtn) backBtn.hidden = false;
      return;
    }
    labels = data.map((i) => i.merchant || "unknown");
    values = data.map((i) => i.amount);
    colors = labels.map((_, idx) => colorFill(idx, 0.82));
    legend.appendChild(buildLegend(labels, colors, "Мерчанты"));
    titleEl.textContent = "Мерчанты";
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
              x: { beginAtZero: true, suggestedMax, ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.15)" } },
              y: { ticks: { color: "#e9edf5" }, grid: { color: "rgba(255,255,255,0.08)" } },
            },
          }
        : {
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: tooltipLabel } } },
            cutout: "50%",
          },
  });
}

function renderQuickAnswers() {
  const ul = document.getElementById("quick-answers");
  if (!ul || !state.analytics) return;
  ul.innerHTML = "";
  const qa = state.analytics.quick_answers;
  if (!qa) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="tag">Нет данных для выбранного периода</span>`;
    ul.appendChild(li);
    return;
  }

  const cards = [];
  const fmtList = (items) =>
    items
      .map((i) => `<div class="qa-row"><span>${formatDate(i.date)}</span><span class="dot"></span><span>${escapeHtml(i.title)}</span><span class="qa-amount">${formatCurrency(i.amount)}</span></div>`)
      .join("");

  cards.push({
    title: "Топ 5 трат",
    content:
      qa.top_expenses && qa.top_expenses.length
        ? `<div class="qa-list">${fmtList(qa.top_expenses)}</div>`
        : "<div class=\"qa-row muted\">Нет данных</div>",
  });
  cards.push({
    title: "Топ 5 доходов",
    content:
      qa.top_incomes && qa.top_incomes.length
        ? `<div class="qa-list">${fmtList(qa.top_incomes)}</div>`
        : "<div class=\"qa-row muted\">Нет данных</div>",
  });

  if (qa.balance) {
    cards.push({
      title: "Баланс за период",
      content: `<div class="qa-row"><span>Доходы</span><span class="qa-amount">${formatCurrency(qa.balance.income)}</span></div>
                <div class="qa-row"><span>Расходы</span><span class="qa-amount">${formatCurrency(qa.balance.expense)}</span></div>
                <div class="qa-row"><span>Итог</span><span class="qa-amount">${formatCurrency(qa.balance.net)}</span></div>`,
    });
  }

  cards.push({
    title: "Самая затратная категория",
    content: qa.top_expense_category
      ? `<div class="qa-row"><span>${qa.top_expense_category.name}</span><span class="qa-amount">${formatCurrency(Math.abs(qa.top_expense_category.amount))}</span></div>`
      : `<div class="qa-row muted">Нет данных</div>`,
  });

  cards.push({
    title: "Самая доходная категория",
    content: qa.top_income_category
      ? `<div class="qa-row"><span>${qa.top_income_category.name}</span><span class="qa-amount">${formatCurrency(Math.abs(qa.top_income_category.amount))}</span></div>`
      : `<div class="qa-row muted">Нет данных</div>`,
  });

  if (qa.delta) {
    cards.push({
      title: "Изменения к прошлому периоду",
      content: `<div class="qa-row"><span>Расходы</span><span class="qa-amount">${formatCurrency(qa.delta.expense)}</span></div>
                <div class="qa-row"><span>Доходы</span><span class="qa-amount">${formatCurrency(qa.delta.income)}</span></div>`,
    });
  }

  cards.forEach((card) => {
    const li = document.createElement("li");
    li.className = "qa-card";
    li.innerHTML = `<div class="qa-title">${card.title}</div><div class="qa-body">${card.content}</div>`;
    ul.appendChild(li);
  });
}
function setupAgent() {
  const toggle = document.getElementById("agent-toggle");
  const panel = document.getElementById("agent-panel");
  const closeBtn = document.getElementById("agent-close");
  const sendBtn = document.getElementById("agent-send");
  const input = document.getElementById("agent-question");
  const messages = document.getElementById("agent-messages");

  function appendMessage(text, role = "agent") {
    const div = document.createElement("div");
    div.className = `agent-msg ${role === "user" ? "user" : ""}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
  });
  closeBtn.addEventListener("click", () => {
    panel.hidden = true;
  });
  sendBtn.addEventListener("click", async () => {
    const q = input.value.trim();
    if (!q) return;
    appendMessage(q, "user");
    input.value = "";
    const data = await apiJson("/api/agent-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    appendMessage(data.answer || "Нет ответа");
  });
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
      refresh();
    });
  }

  const goals = document.getElementById("agent-goals");
  if (goals) {
    goals.addEventListener("input", () => {
      if (goals.value.length > 5000) {
        goals.value = goals.value.slice(0, 5000);
      }
      goals.style.height = "auto";
      goals.style.height = Math.min(goals.scrollHeight + 4, 600) + "px";
      localStorage.setItem("user_goals", goals.value);
      updateHomeGoals(goals.value);
    });
  }

  const deleteAll = document.getElementById("delete-all");
  if (deleteAll) {
    deleteAll.addEventListener("click", async () => {
      const first = confirm("Удалить все загруженные и сохранённые данные?");
      if (!first) return;
      const second = confirm("Точно удалить всё? Это действие необратимо.");
      if (!second) return;
      await safeApiFetch("/api/reset", { method: "POST" });
      showToast("Данные удалены");
      refresh();
    });
  }

  const profileResetBtn = document.getElementById("profile-reset-btn");
  if (profileResetBtn) {
    profileResetBtn.addEventListener("click", async () => {
      await safeApiFetch("/api/reset", { method: "POST" });
      showToast("Сессия сброшена");
      refresh();
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

function buildLegend(labels, colors, title) {
  const wrapper = document.createElement("div");
  wrapper.className = "legend-group";
  const heading = document.createElement("p");
  heading.className = "legend-title";
  heading.textContent = title;
  wrapper.appendChild(heading);
  const list = document.createElement("div");
  list.className = "legend-list";
  labels.forEach((label, idx) => {
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `<span class="dot" style="background:${colors[idx]};"></span><span>${label}</span>`;
    list.appendChild(item);
  });
  wrapper.appendChild(list);
  return wrapper;
}

function buildInteractiveLegend(dataItems, colors, kind) {
  const labels = dataItems.map((i) => i.name);
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
