import { enhanceTimezoneSelect } from "./timezone-picker.js";

const app = document.querySelector("#timezone-app");
const status = document.querySelector("#detection-status");
const selector = document.querySelector("#simulated-timezone");
const dialog = document.querySelector("#timezone-dialog");
const retry = document.querySelector("#retry-detection");
const csrf = app.querySelector("[name=csrfmiddlewaretoken]").value;
const simulationKey = `timezone-demo-simulation:${app.dataset.user}`;
let busy = false;
let queued = false;
let lastReading = null;
let suggestion = null;
let dirty = Boolean(document.querySelector(".errorlist"));
app.querySelectorAll("form").forEach(form => {
  form.addEventListener("input", () => { dirty = true; });
  form.addEventListener("change", () => { dirty = true; });
});
try { selector.value = sessionStorage.getItem(simulationKey) || ""; } catch { /* optional */ }
const searchData = JSON.parse(document.querySelector("#timezone-search-data").textContent);
enhanceTimezoneSelect(document.querySelector("#id_display_timezone"), searchData);
enhanceTimezoneSelect(selector, searchData);


async function post(url, data) {
  const response = await fetch(url, {
    method: "POST", credentials: "same-origin", signal: AbortSignal.timeout(8000),
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || "Request failed. Please retry.");
    error.status = response.status;
    throw error;
  }
  return result;
}

async function detect() {
  if (busy || dialog.open) { queued = true; return; }
  busy = true;
  retry.hidden = true;
  selector.disabled = true;
  try {
    const actual = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const zone = selector.value || actual;
    const source = selector.value ? "simulation" : "browser";
    document.querySelector("#actual-browser-zone").textContent = actual;
    document.querySelector("#detected-zone").textContent = `${zone} (${source})`;
    const reading = `${source}:${zone}`;
    if (reading === lastReading) return;
    // Only this authenticated example sends detection to Django. The homepage never does.
    const result = await post(app.dataset.detectUrl, { timezone: zone, source });
    lastReading = reading;
    status.textContent = `Detected ${zone}. Saved account timezone: ${result.display_timezone}.`;
    if (result.initialized) {
      if (!dirty) { location.reload(); return; }
      status.textContent += " Account timezone initialized. Reload after saving your edits to update displayed times.";
    } else if (result.suggestion) {
      suggestion = result.suggestion;
      document.querySelector("#suggestion-text").textContent =
        `We detected your timezone changed. Would you like to set it to ${suggestion.to}?`;
      document.querySelector("#suggestion-transition").textContent =
        `${suggestion.from} → ${suggestion.to}. This pair will not be offered again in this browser session.`;
      document.querySelector("#accept-timezone").textContent = `Set to ${suggestion.to}`;
      document.querySelector("#unsaved-warning").hidden = !dirty;
      document.querySelector("#suggestion-error").textContent = "";
      dialog.showModal();
    } else {
      status.textContent += " No new suggestion (baseline, unchanged, already saved, or previously offered).";
    }
  } catch (error) {
    status.textContent = `Detection unavailable: ${error.message}`;
    retry.hidden = false;
  } finally {
    selector.disabled = false;
    busy = false;
    if (queued && !dialog.open) { queued = false; detect(); }
  }
}

async function decide(action) {
  if (busy || !suggestion) return;
  busy = true;
  const buttons = [...dialog.querySelectorAll("button")];
  buttons.forEach(button => { button.disabled = true; });
  try {
    const result = await post(app.dataset.suggestionUrl, { id: suggestion.id, action });
    suggestion = null;
    dialog.close();
    if (action === "accept") {
      location.reload();
    } else {
      status.textContent = `Kept ${result.display_timezone}. This transition will not prompt again in this browser session.`;
    }
  } catch (error) {
    if (error.status === 409) {
      suggestion = null;
      dialog.close();
      status.textContent = "This suggestion expired (for example, another tab changed the account). Reload to see the current saved timezone.";
    } else {
      document.querySelector("#suggestion-error").textContent = error.message;
    }
  } finally {
    buttons.forEach(button => { button.disabled = false; });
    busy = false;
    if (queued && !dialog.open) { queued = false; detect(); }
  }
}

selector.addEventListener("change", () => {
  try {
    if (selector.value) sessionStorage.setItem(simulationKey, selector.value);
    else sessionStorage.removeItem(simulationKey);
  } catch { /* Simulation still works without persistence. */ }
  detect();
});
document.querySelector("#accept-timezone").addEventListener("click", () => decide("accept"));
document.querySelector("#dismiss-timezone").addEventListener("click", () => decide("dismiss"));
dialog.addEventListener("cancel", event => { event.preventDefault(); decide("dismiss"); });
retry.addEventListener("click", detect);
window.addEventListener("focus", detect);
document.addEventListener("visibilitychange", () => { if (!document.hidden) detect(); });
detect();
