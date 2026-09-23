// Read-only browser inspection: no fetch, cookies, localStorage, or sessionStorage.
const instant = new Date(JSON.parse(document.querySelector("#sample-instant").textContent));

function inspect() {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    document.querySelector("#browser-zone").textContent = zone || "Not reported";
    document.querySelector("#browser-time").textContent = new Intl.DateTimeFormat(undefined, {
      dateStyle: "full", timeStyle: "long",
    }).format(instant);
    const minutes = -instant.getTimezoneOffset();
    const hours = String(Math.floor(Math.abs(minutes) / 60)).padStart(2, "0");
    const remainder = String(Math.abs(minutes) % 60).padStart(2, "0");
    document.querySelector("#browser-offset").textContent =
      `UTC${minutes >= 0 ? "+" : "−"}${hours}:${remainder}`;
  } catch {
    document.querySelector("#browser-status").textContent =
      "Browser timezone information is unavailable. The server values above remain valid.";
  }
}

inspect();
window.addEventListener("focus", inspect);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) inspect();
});


const clockTimeOptions = { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" };
const clockDateOptions = { month: "short", day: "numeric", timeZoneName: "shortOffset" };
const utcFormatter = new Intl.DateTimeFormat(undefined, { ...clockTimeOptions, timeZone: "UTC" });
const worldClocks = [...document.querySelectorAll(".world-clock")].map(element => ({
  time: element.querySelector("time"),
  details: element.querySelector(".clock-details"),
  formatter: new Intl.DateTimeFormat(undefined, {
    ...clockTimeOptions, timeZone: element.dataset.timezone,
  }),
  dateFormatter: new Intl.DateTimeFormat(undefined, {
    ...clockDateOptions, timeZone: element.dataset.timezone,
  }),
}));

function setClock(element, label, instant) {
  element.textContent = label;
  element.dateTime = instant.toISOString();
}

function tick() {
  // Re-read the device clock each tick: background-tab throttling cannot accumulate drift.
  const now = new Date();
  const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  setClock(document.querySelector("#local-clock"),
    new Intl.DateTimeFormat(undefined, clockTimeOptions).format(now), now);
  document.querySelector("#local-clock-details").textContent =
    `${new Intl.DateTimeFormat(undefined, { dateStyle: "full" }).format(now)} · ${localZone}`;
  setClock(document.querySelector("#utc-clock"), utcFormatter.format(now), now);
  worldClocks.forEach(clock => {
    setClock(clock.time, clock.formatter.format(now), now);
    clock.details.textContent = clock.dateFormatter.format(now);
  });
}

tick();
setInterval(tick, 1000);
window.addEventListener("focus", tick);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) tick();
});
