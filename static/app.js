// Browser code: uploads the file, sends questions, and shows the answers.
// Everything is written with textContent (never innerHTML), so an answer can never run as HTML.

// Shows a short status message.
function show(el, text, isError) {
  el.textContent = text;
  el.classList.toggle("error", !!isError);
}

// Splits "| a | b |" into ["a", "b"].
function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

// Puts text into an element, turning **bold**, *italic* and `code` into real tags (no innerHTML).
function addInline(el, text) {
  text.split(/(\*\*.+?\*\*|`.+?`|\*[^*\s][^*]*?\*)/).forEach((part) => {
    if (!part) return;
    let tag = null;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) tag = "strong";
    else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) tag = "code";
    else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) tag = "em";
    if (!tag) { el.append(part); return; }
    const child = document.createElement(tag);
    child.textContent = part.slice(tag === "strong" ? 2 : 1, tag === "strong" ? -2 : -1);
    el.appendChild(child);
  });
}

// Shows an answer. Tables become HTML tables, "- " lines become bullet lists,
// "# " lines become headings, and the rest becomes paragraphs.
function showAnswer(el, text) {
  el.classList.remove("error");
  el.replaceChildren();
  const lines = text.split("\n");
  const isBullet = (l) => /^\s*([-*•]|\d+[.)])\s+/.test(l);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    if (/^#{1,6}\s/.test(line)) { // heading
      const h = document.createElement("h4");
      addInline(h, line.replace(/^#+\s*/, ""));
      el.appendChild(h);
      i++;
      continue;
    }
    if (isBullet(line)) { // list
      const list = document.createElement(/^\s*\d/.test(line) ? "ol" : "ul");
      while (i < lines.length && isBullet(lines[i])) {
        addInline(list.appendChild(document.createElement("li")), lines[i++].replace(/^\s*([-*•]|\d+[.)])\s+/, ""));
      }
      el.appendChild(list);
      continue;
    }
    if (!line.trim().startsWith("|")) { // normal paragraph: until a blank line or another block starts
      const start = i;
      while (i < lines.length && lines[i].trim() && !lines[i].trim().startsWith("|")
             && !isBullet(lines[i]) && !/^#{1,6}\s/.test(lines[i])) i++;
      const p = document.createElement("p");
      addInline(p, lines.slice(start, i).join("\n"));
      el.appendChild(p);
      continue;
    }
    // Collect the table lines: header row, separator row (|---|---|), then data rows.
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
    const table = document.createElement("table");
    rows.forEach((line, n) => {
      if (/^[\s|:-]+$/.test(line)) return; // skip the |---|---| separator row
      const tr = table.insertRow();
      splitRow(line).forEach((cell) => {
        const td = document.createElement(n === 0 ? "th" : "td");
        addInline(td, cell);
        tr.appendChild(td);
      });
    });
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    el.appendChild(wrap);
  }
}

// Reads the server's JSON reply. If the server sent something else (e.g. an HTML error page), use a fallback message.
async function readJson(res) {
  try {
    return await res.json();
  } catch (err) {
    return { error: `Server error (${res.status})` };
  }
}

const chat = document.getElementById("chat");

// Adds one message ("user" or "bot") to the conversation and returns its element.
function addMessage(role) {
  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();
  const el = document.createElement("div");
  el.className = "msg " + role;
  chat.appendChild(el);
  return el;
}

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

// Attaching a file uploads it straight away.
document.getElementById("file").addEventListener("change", async (e) => {
  const status = document.getElementById("upload-status");
  const input = e.target;
  const file = input.files[0];
  if (!file) return;

  const body = new FormData();
  body.append("file", file);
  show(status, "Uploading...");
  try {
    const res = await fetch("/upload", { method: "POST", body });
    const data = await readJson(res);
    if (!res.ok) show(status, data.error, true);
    else show(status, `${data.file}: ${data.rows} rows, ${data.columns.length} columns`);
  } catch (err) {
    // The browser may cut the connection when a file is far too big.
    show(status, "Upload failed. The file may be too big (max 10 MB) or the server is down.", true);
  }
  input.value = ""; // lets the same file be chosen again
});

document.getElementById("composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("ask-btn");
  const box = document.getElementById("query");
  const query = box.value.trim();
  if (!query) return;

  addMessage("user").textContent = query;
  box.value = "";
  const answer = addMessage("bot");
  show(answer, "Thinking...");
  scrollDown();
  btn.disabled = true;
  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, allow_outside: document.getElementById("allow-outside").checked }),
    });
    const data = await readJson(res);
    if (!res.ok) show(answer, data.error, true);
    else showAnswer(answer, data.answer);
  } catch (err) {
    show(answer, "Could not reach the server: " + err, true);
  } finally {
    btn.disabled = false;
    scrollDown();
  }
});
