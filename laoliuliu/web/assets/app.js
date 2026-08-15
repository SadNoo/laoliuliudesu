"use strict";

const state = {
  csrf: null,
  user: null,
  currentView: "analysis",
  drawPage: 1,
  drawTotal: 0,
  drawPageSize: 30,
  analysis: null,
  temporaryCredential: null,
};

const viewMeta = {
  analysis: ["TRANSITION FREQUENCY", "下一期平码生肖"],
  draws: ["2026 DRAW RECORDS", "开奖数据"],
  users: ["USER AUTHORIZATION", "用户授权"],
  settings: ["DATA & AI SETTINGS", "数据与 AI"],
};

const zodiacLabels = {
  rat: "鼠", ox: "牛", tiger: "虎", rabbit: "兔", dragon: "龍", snake: "蛇",
  horse: "馬", goat: "羊", monkey: "猴", rooster: "雞", dog: "狗", pig: "豬",
};

class ApiError extends Error {
  constructor(code, message, requestId, status) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.status = status;
  }
}

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD" && state.csrf) headers["X-CSRF-Token"] = state.csrf;
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: "same-origin",
  });
  let document;
  try {
    document = await response.json();
  } catch (_) {
    throw new ApiError("INVALID_RESPONSE", "服务器响应格式无效", null, response.status);
  }
  if (!response.ok || !document.success) {
    const error = document.error || {};
    throw new ApiError(error.code || "REQUEST_FAILED", error.message || "请求失败", document.request_id, response.status);
  }
  return document.data;
}

function byId(id) { return document.getElementById(id); }

function setMessage(id, message, type = "") {
  const element = byId(id);
  element.textContent = message || "";
  element.className = `form-message${type ? ` ${type}` : ""}`;
}

function describeError(error) {
  if (!(error instanceof ApiError)) return "操作失败，请稍后重试。";
  return `${error.message}${error.requestId ? ` · Request ID: ${error.requestId}` : ""}`;
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 3200);
}

function setBusy(button, busy, label) {
  if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.originalLabel;
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Hong_Kong", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(new Date(value));
  } catch (_) {
    return value;
  }
}

function clearChildren(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function textCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value === null || value === undefined ? "—" : String(value);
  return cell;
}

async function restoreSession() {
  try {
    const data = await api("/auth/me");
    state.user = data.user;
    state.csrf = data.csrf_token;
    if (state.user.must_change_password) {
      showAuthenticatedShell(false);
      showPasswordDialog(true);
    } else {
      showAuthenticatedShell(true);
      await loadView("analysis");
    }
  } catch (error) {
    showLogin();
    if (error instanceof ApiError && error.status !== 401) setMessage("loginMessage", describeError(error), "error");
  }
}

function showLogin() {
  state.user = null;
  state.csrf = null;
  byId("appView").hidden = true;
  byId("loginView").hidden = false;
  byId("loginPassword").value = "";
}

function showAuthenticatedShell(loadContent) {
  byId("loginView").hidden = true;
  byId("appView").hidden = false;
  byId("sessionUsername").textContent = state.user.username;
  byId("sessionRole").textContent = state.user.role === "admin" ? "管理员" : "授权用户";
  byId("adminNavigation").hidden = state.user.role !== "admin";
  if (!loadContent) {
    document.querySelectorAll(".resource-view").forEach((view) => { view.hidden = true; });
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const button = byId("loginButton");
  setBusy(button, true, "正在登录…");
  setMessage("loginMessage", "");
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: { username: byId("loginUsername").value, password: byId("loginPassword").value },
    });
    state.user = data.user;
    state.csrf = data.csrf_token;
    byId("loginPassword").value = "";
    showAuthenticatedShell(!state.user.must_change_password);
    if (state.user.must_change_password) showPasswordDialog(true);
    else await loadView("analysis");
  } catch (error) {
    byId("loginPassword").value = "";
    setMessage("loginMessage", describeError(error), "error");
  } finally {
    setBusy(button, false, "");
  }
}

function showPasswordDialog(required) {
  byId("passwordDialogDescription").textContent = required
    ? "这是一次性密码。首次登录必须设置自己的密码后才能继续。"
    : "输入当前密码，并设置至少 12 位且包含字母和数字的新密码。";
  byId("closePasswordDialog").hidden = required;
  byId("currentPassword").value = "";
  byId("newPassword").value = "";
  byId("confirmPassword").value = "";
  setMessage("passwordMessage", "");
  byId("passwordDialog").showModal();
}

async function handlePasswordChange(event) {
  event.preventDefault();
  const newPassword = byId("newPassword").value;
  if (newPassword !== byId("confirmPassword").value) {
    setMessage("passwordMessage", "两次输入的新密码不一致。", "error");
    return;
  }
  const button = event.submitter;
  setBusy(button, true, "正在保存…");
  try {
    await api("/auth/change-password", {
      method: "POST",
      body: { current_password: byId("currentPassword").value, new_password: newPassword },
    });
    state.user.must_change_password = false;
    byId("passwordDialog").close();
    showAuthenticatedShell(true);
    showToast("密码已更新");
    await loadView("analysis");
  } catch (error) {
    setMessage("passwordMessage", describeError(error), "error");
  } finally {
    setBusy(button, false, "");
  }
}

async function logout() {
  const button = byId("logoutButton");
  setBusy(button, true, "退出中…");
  try { await api("/auth/logout", { method: "POST", body: {} }); } catch (_) { /* local reset remains safe */ }
  finally { setBusy(button, false, ""); showLogin(); }
}

async function loadView(name) {
  if ((name === "users" || name === "settings") && state.user.role !== "admin") return;
  state.currentView = name;
  document.querySelectorAll(".resource-view").forEach((view) => { view.hidden = view.id !== `${name}View`; });
  document.querySelectorAll(".nav-button").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  byId("viewEyebrow").textContent = viewMeta[name][0];
  byId("viewTitle").textContent = viewMeta[name][1];
  byId("appView").classList.remove("menu-open");
  try {
    if (name === "analysis") await loadAnalysis();
    if (name === "draws") await loadDraws();
    if (name === "users") await loadUsers();
    if (name === "settings") await loadSettings();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) showLogin();
    else showToast(describeError(error));
  }
}

async function loadAnalysis() {
  byId("topSixGrid").classList.add("loading-grid");
  clearChildren(byId("topSixGrid"));
  try {
    const [analysis, runs] = await Promise.all([api("/analysis/latest"), api("/analysis/runs?limit=12")]);
    state.analysis = analysis;
    renderAnalysis(analysis);
    renderAnalysisRuns(runs.items);
  } catch (error) {
    byId("topSixGrid").classList.remove("loading-grid");
    if (error instanceof ApiError && error.code.startsWith("INSUFFICIENT")) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = error.message;
      byId("topSixGrid").appendChild(empty);
      return;
    }
    throw error;
  }
}

function renderAnalysis(analysis) {
  byId("latestIssue").textContent = analysis.latest_issue;
  byId("latestSpecial").textContent = String(analysis.latest_special_number).padStart(2, "0");
  byId("latestZodiac").textContent = analysis.latest_special_zodiac_label;
  byId("sampleCount").textContent = analysis.sample_count;
  byId("occurrenceTotal").textContent = analysis.total_regular_occurrences;

  const grid = byId("topSixGrid");
  clearChildren(grid);
  grid.classList.remove("loading-grid");
  analysis.top_six.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "zodiac-card";
    const rank = document.createElement("span"); rank.className = "zodiac-rank"; rank.textContent = `RANK ${String(entry.rank).padStart(2, "0")}`;
    const name = document.createElement("strong"); name.className = "zodiac-name"; name.textContent = entry.label;
    const data = document.createElement("div"); data.className = "zodiac-data";
    const count = document.createElement("strong"); count.textContent = `${entry.occurrences} 次`;
    const frequency = document.createElement("span"); frequency.textContent = `历史频率 ${(entry.frequency * 100).toFixed(2)}%`;
    data.append(count, frequency); card.append(rank, name, data); grid.appendChild(card);
  });

  const body = byId("rankingTableBody");
  clearChildren(body);
  analysis.ranking.forEach((entry) => {
    const row = document.createElement("tr");
    const rankCell = document.createElement("td"); const badge = document.createElement("span"); badge.className = "rank-badge"; badge.textContent = entry.rank; rankCell.appendChild(badge);
    row.append(rankCell, textCell(entry.label), textCell(`${entry.occurrences} 次`), textCell(`${(entry.frequency * 100).toFixed(2)}%`));
    body.appendChild(row);
  });
}

function renderAnalysisRuns(items) {
  const container = byId("analysisRuns"); clearChildren(container);
  if (!items.length) { const empty = document.createElement("div"); empty.className = "empty-state"; empty.textContent = "暂无记录。"; container.appendChild(empty); return; }
  items.forEach((item) => {
    const row = document.createElement("div"); row.className = "run-item";
    const copy = document.createElement("div"); const title = document.createElement("strong"); title.textContent = `第 ${item.latest_issue} 期 · ${zodiacLabels[item.special_zodiac] || item.special_zodiac}`;
    const time = document.createElement("span"); time.textContent = formatDate(item.created_at); copy.append(title, time);
    const status = document.createElement("div"); status.className = `run-status${item.status === "failed" ? " failed" : ""}`; status.textContent = item.status === "succeeded" ? "已完成" : item.error_code || "失败";
    row.append(copy, status); container.appendChild(row);
  });
}

async function runAi() {
  const button = byId("runAiButton"); setBusy(button, true, "AI 解读中…"); setMessage("aiMessage", "");
  try {
    const data = await api("/analysis/ai", { method: "POST", body: {} });
    byId("aiEmpty").hidden = true; byId("aiResult").hidden = false; byId("aiSummary").textContent = data.ai_result.summary;
    const list = byId("aiObservations"); clearChildren(list);
    data.ai_result.observations.forEach((value) => { const item = document.createElement("li"); item.textContent = value; list.appendChild(item); });
    setMessage("aiMessage", "AI 解读已保存。", "success");
    const runs = await api("/analysis/runs?limit=12"); renderAnalysisRuns(runs.items);
  } catch (error) { setMessage("aiMessage", describeError(error), "error"); }
  finally { setBusy(button, false, ""); }
}

async function loadDraws() {
  const data = await api(`/draws?page=${state.drawPage}&page_size=${state.drawPageSize}`);
  state.drawTotal = data.total;
  const body = byId("drawsTableBody"); clearChildren(body); byId("drawsEmpty").hidden = data.items.length > 0;
  data.items.forEach((draw) => {
    const row = document.createElement("tr"); row.appendChild(textCell(draw.issue));
    const regularCell = document.createElement("td"); const numberRow = document.createElement("div"); numberRow.className = "number-row";
    draw.regular_numbers.forEach((number) => { const ball = document.createElement("span"); ball.className = "number-ball"; ball.textContent = String(number).padStart(2, "0"); numberRow.appendChild(ball); });
    regularCell.appendChild(numberRow);
    const specialCell = document.createElement("td"); const special = document.createElement("span"); special.className = "number-ball special"; special.textContent = String(draw.special_number).padStart(2, "0"); specialCell.appendChild(special);
    row.append(regularCell, specialCell, textCell(formatDate(draw.open_time))); body.appendChild(row);
  });
  const pages = Math.max(1, Math.ceil(data.total / state.drawPageSize));
  byId("drawsPage").textContent = `第 ${state.drawPage} / ${pages} 页 · ${data.total} 期`;
  byId("drawsPrevious").disabled = state.drawPage <= 1;
  byId("drawsNext").disabled = state.drawPage >= pages;
}

async function loadUsers() {
  const data = await api("/admin/users");
  byId("usersTotal").textContent = data.items.length;
  byId("usersActive").textContent = data.items.filter((user) => user.status === "active").length;
  const body = byId("usersTableBody"); clearChildren(body);
  data.items.forEach((user) => {
    const row = document.createElement("tr"); row.append(textCell(user.username), textCell(user.role === "admin" ? "管理员" : "子用户"));
    const statusCell = document.createElement("td"); const pill = document.createElement("span"); pill.className = `status-pill${user.status === "active" ? "" : " disabled"}`; pill.textContent = user.status === "active" ? "已启用" : "已停用"; statusCell.appendChild(pill);
    row.append(statusCell, textCell(user.must_change_password ? "是" : "否"), textCell(formatDate(user.last_login_at)));
    const actionCell = document.createElement("td");
    if (user.role !== "admin") {
      const button = document.createElement("button"); button.className = `row-button${user.status === "active" ? " danger" : ""}`; button.type = "button"; button.textContent = user.status === "active" ? "停用" : "启用";
      button.addEventListener("click", () => changeUserStatus(user.id, user.status === "active" ? "disabled" : "active", button)); actionCell.appendChild(button);
    } else actionCell.textContent = "—";
    row.appendChild(actionCell); body.appendChild(row);
  });
}

async function changeUserStatus(userId, status, button) {
  setBusy(button, true, "处理中…");
  try { await api(`/admin/users/${userId}/status`, { method: "PATCH", body: { status } }); showToast(status === "active" ? "用户已启用" : "用户已停用"); await loadUsers(); }
  catch (error) { showToast(describeError(error)); }
  finally { setBusy(button, false, ""); }
}

async function createUser(event) {
  event.preventDefault(); const button = event.submitter; setBusy(button, true, "正在创建…"); setMessage("createUserMessage", "");
  try {
    const data = await api("/admin/users", { method: "POST", body: { username: byId("newUsername").value } });
    state.temporaryCredential = { username: data.user.username, password: data.temporary_password };
    byId("createUserDialog").close(); byId("newUsername").value = "";
    byId("credentialUsername").textContent = state.temporaryCredential.username;
    byId("credentialPassword").textContent = state.temporaryCredential.password;
    byId("credentialDialog").showModal(); await loadUsers();
  } catch (error) { setMessage("createUserMessage", describeError(error), "error"); }
  finally { setBusy(button, false, ""); }
}

async function copyCredential() {
  if (!state.temporaryCredential) return;
  const value = `用户名：${state.temporaryCredential.username}\n临时密码：${state.temporaryCredential.password}`;
  try { await navigator.clipboard.writeText(value); showToast("凭据已复制"); }
  catch (_) { showToast("无法自动复制，请手动保存"); }
}

function closeCredentialDialog() {
  state.temporaryCredential = null;
  byId("credentialUsername").textContent = "—"; byId("credentialPassword").textContent = "—"; byId("credentialDialog").close();
}

async function loadSettings() {
  const [providerData, syncData] = await Promise.all([api("/admin/ai-provider"), api("/admin/sync-runs")]);
  const provider = providerData.provider;
  byId("aiDisplayName").value = provider ? provider.display_name : "";
  byId("aiBaseUrl").value = provider ? provider.base_url : "https://api.openai.com/v1";
  byId("aiModel").value = provider ? provider.model : "";
  byId("aiApiKey").value = ""; byId("aiEnabled").checked = provider ? provider.enabled : false; byId("aiClearKey").checked = false;
  byId("aiProviderMeta").textContent = provider ? `Key：${provider.has_api_key ? "已设置" : "未设置"} · 提示词：${providerData.prompt_version} · 更新：${formatDate(provider.updated_at)}` : `尚未配置 · 提示词：${providerData.prompt_version}`;
  renderSyncRuns(syncData.items);
}

async function saveProvider(event) {
  event.preventDefault(); const button = event.submitter; setBusy(button, true, "正在保存…"); setMessage("aiProviderMessage", "");
  const apiKey = byId("aiApiKey").value;
  try {
    await api("/admin/ai-provider", { method: "PUT", body: {
      display_name: byId("aiDisplayName").value, base_url: byId("aiBaseUrl").value,
      model: byId("aiModel").value, api_key: apiKey || null,
      clear_api_key: byId("aiClearKey").checked, enabled: byId("aiEnabled").checked,
    }});
    byId("aiApiKey").value = ""; setMessage("aiProviderMessage", "AI 配置已保存。", "success"); await loadSettings();
  } catch (error) { setMessage("aiProviderMessage", describeError(error), "error"); }
  finally { setBusy(button, false, ""); }
}

async function runSync(kind, button) {
  if (kind === "history" && !window.confirm("将从同源历史接口重新核对 2026 年全部记录，继续吗？")) return;
  setBusy(button, true, kind === "history" ? "正在核对历史…" : "正在同步…"); setMessage("syncMessage", "");
  try {
    const result = await api(`/admin/sync/${kind}`, { method: "POST", body: {} });
    setMessage("syncMessage", `完成：读取 ${result.fetched} 期，新增 ${result.inserted} 期，跳过 ${result.skipped} 期。`, "success");
    const runs = await api("/admin/sync-runs"); renderSyncRuns(runs.items);
  } catch (error) { setMessage("syncMessage", describeError(error), "error"); }
  finally { setBusy(button, false, ""); }
}

function renderSyncRuns(items) {
  const container = byId("syncRuns"); clearChildren(container);
  if (!items.length) { const empty = document.createElement("div"); empty.className = "empty-state"; empty.textContent = "暂无同步记录。"; container.appendChild(empty); return; }
  items.slice(0, 8).forEach((item) => {
    const row = document.createElement("div"); row.className = "run-item";
    const copy = document.createElement("div"); const title = document.createElement("strong"); title.textContent = item.sync_kind === "history" ? "历史核对" : "增量同步";
    const detail = document.createElement("span"); detail.textContent = `${formatDate(item.started_at)} · 新增 ${item.inserted_count} · 跳过 ${item.skipped_count}`; copy.append(title, detail);
    const status = document.createElement("div"); status.className = `run-status${item.status === "failed" ? " failed" : ""}`; status.textContent = item.status === "succeeded" ? "成功" : item.status === "running" ? "进行中" : item.error_code || "失败";
    row.append(copy, status); container.appendChild(row);
  });
}

function bindEvents() {
  byId("loginForm").addEventListener("submit", handleLogin);
  byId("passwordForm").addEventListener("submit", handlePasswordChange);
  byId("logoutButton").addEventListener("click", logout);
  byId("changePasswordButton").addEventListener("click", () => showPasswordDialog(false));
  byId("closePasswordDialog").addEventListener("click", () => byId("passwordDialog").close());
  document.querySelectorAll(".password-toggle").forEach((button) => button.addEventListener("click", () => {
    const input = byId(button.dataset.passwordTarget); const show = input.type === "password"; input.type = show ? "text" : "password"; button.textContent = show ? "隐藏" : "显示";
  }));
  document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", () => loadView(button.dataset.view)));
  byId("menuButton").addEventListener("click", () => byId("appView").classList.toggle("menu-open"));
  byId("refreshAnalysisButton").addEventListener("click", loadAnalysis);
  byId("runAiButton").addEventListener("click", runAi);
  byId("drawsPrevious").addEventListener("click", async () => { if (state.drawPage > 1) { state.drawPage -= 1; await loadDraws(); } });
  byId("drawsNext").addEventListener("click", async () => { state.drawPage += 1; await loadDraws(); });
  byId("openCreateUserButton").addEventListener("click", () => { setMessage("createUserMessage", ""); byId("createUserDialog").showModal(); });
  byId("closeCreateUserDialog").addEventListener("click", () => byId("createUserDialog").close());
  byId("createUserForm").addEventListener("submit", createUser);
  byId("copyCredentialButton").addEventListener("click", copyCredential);
  byId("closeCredentialDialog").addEventListener("click", closeCredentialDialog);
  byId("aiProviderForm").addEventListener("submit", saveProvider);
  byId("syncCurrentButton").addEventListener("click", (event) => runSync("current", event.currentTarget));
  byId("syncHistoryButton").addEventListener("click", (event) => runSync("history", event.currentTarget));
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await restoreSession();
});
