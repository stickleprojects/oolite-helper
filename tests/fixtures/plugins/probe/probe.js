// A test plugin: shows the "clock" topic and tries everything the sandbox
// must refuse. Each result is sent as an oolite.log() line "probe NAME: ...".
const report = (name, result) => oolite.log(`probe ${name}: ${result}`);

oolite.on("clock", (v) => { document.getElementById("clock").textContent = v.seconds; });
document.getElementById("button").addEventListener("click", () => report("click", "ok"));

async function probe(name, attempt) {
  try {
    report(name, `ALLOWED ${await attempt()}`);
  } catch (e) {
    report(name, `blocked (${e})`);
  }
}

Promise.all([
  probe("fetch_https", () => fetch("https://example.com/").then((r) => r.status)),
  probe("fetch_file", () => fetch("file:///etc/passwd").then((r) => r.status)),
  probe("fetch_escape", () => fetch("plugin://probe/../../../../etc/passwd").then((r) => r.status)),
  probe("fetch_escape_encoded", () => fetch("plugin://probe/%2e%2e/%2e%2e/%2e%2e/etc/passwd").then((r) => r.status)),
  probe("fetch_other_plugin", () => fetch("plugin://other/index.html").then((r) => r.status)),
  probe("websocket", () => new Promise((resolve, reject) => {
    const socket = new WebSocket("ws://127.0.0.1:8563");
    socket.onopen = () => resolve("open");
    socket.onerror = () => reject("error");
  })),
  probe("eval", () => eval("1 + 1")),
  probe("inline_script", () => {
    const s = document.createElement("script");
    s.textContent = "window.inlineRan = true";
    document.body.appendChild(s);
    return window.inlineRan ? "ran" : Promise.reject("didn't run");
  }),
  probe("window_open", () => window.open("https://example.com/") || Promise.reject("null")),
  probe("replace_bridge", () => { window.oolite = null; return window.oolite === null ? "replaced" : Promise.reject("read-only"); }),
  // connect-src 'none' covers the plugin's own files too: data comes only through oolite.on().
  probe("fetch_own_file", () => fetch("plugin://probe/style.css").then((r) => r.status)),
]).then(() => {
  report("done", "all");
  setTimeout(() => { location.href = "https://example.com/"; report("navigate", "tried"); }, 200);
});
