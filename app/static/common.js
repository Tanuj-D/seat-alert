// Helpers shared by the search and manage pages.

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function notify(text, ok = true) {
  const n = $("notice");
  n.textContent = text;
  n.className = "notice " + (ok ? "ok" : "err");
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => n.classList.add("hidden"), ok ? 6000 : 7000);
}

async function api(path, options) {
  const resp = await fetch(path, options);
  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  if (!resp.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = "Please check your email address.";
    if (resp.status === 429) msg = "You're going a bit fast. Wait a minute and try again.";
    throw new Error(msg || "Something went wrong. Try again in a minute.");
  }
  return data;
}

function timeAgo(iso) {
  if (!iso) return "";
  // SQLite returns times without a timezone; they're stored in UTC.
  const t = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  const mins = Math.round((Date.now() - t.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function seatBadge(seats) {
  if (seats == null) return el("span", "badge", "Checking…");
  return seats > 0 ? el("span", "badge open", `${seats} open`) : el("span", "badge full", "Full");
}

// localStorage can throw (private mode, blocked storage), so never rely on it.
const store = {
  get(key) { try { return localStorage.getItem(key) || ""; } catch { return ""; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
};
