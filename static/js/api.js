/* api.js — thin fetch() wrapper used by every other module. */
const API_BASE = "/api";

async function apiGet(path, params) {
  let qs = "";
  if (params) {
    qs = "?" + (typeof params === "string" ? params : new URLSearchParams(params).toString());
  }
  const res = await fetch(API_BASE + path + qs);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `GET ${path} failed (${res.status})`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `POST ${path} failed (${res.status})`);
  return data;
}

async function apiDelete(path) {
  const res = await fetch(API_BASE + path, { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `DELETE ${path} failed (${res.status})`);
  return data;
}

function downloadUrl(path, params) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return API_BASE + path + qs;
}

function triggerDownload(path, params) {
  const a = document.createElement("a");
  a.href = downloadUrl(path, params);
  document.body.appendChild(a);
  a.click();
  a.remove();
}

let _toastTimer = null;
function showToast(message, isError) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.className = "toast show" + (isError ? " error" : "");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
