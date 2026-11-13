// Calculon's website: typing sheets, the right-click menu, download links.
// The sheets and their answers come from sheets.js, made by scripts/build_site.py.
(() => {
  "use strict";

  const lang = document.documentElement.lang === "uk" ? "uk" : "en";
  const DATA = window.CALCULON[lang];
  const ASSETS = new URL(".", document.currentScript.src);
  const REPO = "sprytnyk/calculon";
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const TEXT = {
    en: {
      linux: "Download for Linux",
      windows: "Download for Windows",
      mac_arm64: "macOS · Apple Silicon",
      mac_x64: "macOS · Intel",
      linux_short: "Linux",
      windows_short: "Windows",
      all: "All downloads",
      version: (v, d) => `Version ${v}, released ${d}. It's free and open source, under the MIT licence.`,
      date: { year: "numeric", month: "long", day: "numeric" },
    },
    uk: {
      linux: "Завантажити для Linux",
      windows: "Завантажити для Windows",
      mac_arm64: "macOS · Apple Silicon",
      mac_x64: "macOS · Intel",
      linux_short: "Linux",
      windows_short: "Windows",
      all: "Усі завантаження",
      version: (v, d) => `Версія ${v}, випущена ${d}. Він безкоштовний і має відкритий код під ліцензією MIT.`,
      date: { year: "numeric", month: "long", day: "numeric" },
    },
  }[lang];

  // ---- small helpers ----

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const icon = (name) => {
    const node = el("span", "icon");
    const url = `url("${new URL(`icons/${name}.svg`, ASSETS)}")`;
    node.style.maskImage = url;
    node.style.webkitMaskImage = url;
    node.style.background = `var(--icon-${DATA.icon_groups[name] || "neutral"})`;
    node.setAttribute("aria-hidden", "true");
    return node;
  };

  const sleep = (ms, run) =>
    new Promise((resolve, reject) => {
      const id = setTimeout(resolve, ms);
      run.cancel.push(() => {
        clearTimeout(id);
        reject(new Error("stopped"));
      });
    });

  const remember = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      // private mode: the choice just isn't kept
    }
  };

  // ---- one sheet, typed in line by line ----

  // pieces of a line, each with its colour class, cut at the misspelled word
  function pieces(line, miss) {
    const cuts = new Set([0, line.text.length]);
    for (const [a, b] of line.spans) cuts.add(a).add(b);
    if (miss) cuts.add(miss[0]).add(miss[1]);
    const points = [...cuts].filter((x) => x <= line.text.length).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < points.length - 1; i++) {
      const [a, b] = [points[i], points[i + 1]];
      const span = line.spans.find(([s, e]) => s <= a && b <= e);
      out.push({ a, b, cls: span ? span[2] : "", miss: miss && miss[0] <= a && b <= miss[1] });
    }
    return out;
  }

  class Sheet {
    constructor(box, sheet, status) {
      this.box = box;
      this.sheet = sheet;
      this.status = status;
      this.rows = [];
      this.run = { cancel: [] };
    }

    stop() {
      this.run.cancel.forEach((f) => f());
      this.run = { cancel: [] };
    }

    clear() {
      this.stop();
      this.box.textContent = "";
      this.rows = [];
      if (this.status) this.status.textContent = "";
    }

    missFor(n) {
      const m = this.sheet.misspelled;
      return m && m.line === n ? [m.start, m.end] : null;
    }

    addRow(n) {
      const row = el("div", "line");
      row.append(el("span", "n", String(n + 1)), el("span", "src"), el("span", "ans"));
      this.box.append(row);
      this.rows.push(row);
      return row;
    }

    // show `typed` characters of line n; the misspelled word is underlined once the
    // cursor has left it, like in the app
    draw(n, typed, caret) {
      const line = this.sheet.lines[n];
      const src = this.rows[n].querySelector(".src");
      const miss = this.missFor(n);
      const showMiss = miss && typed > miss[1];
      src.textContent = "";
      for (const p of pieces(line, showMiss ? miss : null)) {
        if (p.a >= typed) break;
        const part = el("span", [p.cls, p.miss ? "miss" : ""].join(" ").trim());
        part.textContent = line.text.slice(p.a, Math.min(p.b, typed));
        if (p.miss) part.dataset.miss = "";
        src.append(part);
      }
      if (caret) src.append(el("span", "caret"));
    }

    answer(n) {
      const line = this.sheet.lines[n];
      const ans = this.rows[n].querySelector(".ans");
      ans.textContent = line.answer;
      ans.classList.toggle("total", line.total);
      ans.classList.add("shown");
    }

    showAll() {
      this.clear();
      this.sheet.lines.forEach((_, n) => {
        this.addRow(n);
        this.draw(n, Infinity, false);
        this.answer(n);
      });
      if (this.status) this.status.textContent = this.sheet.total;
    }

    async type() {
      this.clear();
      const run = this.run;
      const lines = this.sheet.lines;
      await sleep(400, run);
      for (let n = 0; n < lines.length; n++) {
        const row = this.addRow(n);
        this.rows.forEach((r) => r.classList.toggle("current", r === row));
        const text = lines[n].text;
        for (let i = 0; i <= text.length; i++) {
          this.draw(n, i, true);
          if (i < text.length) await sleep(text[i] === " " ? 30 : 38 + Math.random() * 40, run);
        }
        this.draw(n, Infinity, n === lines.length - 1);
        this.answer(n);
        if (this.status && lines[n].total) this.status.textContent = this.sheet.total;
        await sleep(n === 0 ? 300 : 420, run);
      }
      if (this.status) this.status.textContent = this.sheet.total;
    }
  }

  // ---- the right-click menu over the misspelled word ----

  function contextMenu(box, sheet) {
    const menu = el("div", "ctxmenu");
    sheet.suggestions.forEach((word, i) => {
      menu.append(el("div", `item suggestion${i === 0 ? " hl" : ""}`, word));
    });
    menu.append(el("hr"));
    for (const [key, name] of [
      ["spell_add", "spell_add"],
      ["spell_ignore", "spell_ignore"],
    ]) {
      const item = el("div", "item");
      item.append(icon(name), el("span", "", DATA.ui[key]));
      menu.append(item);
    }
    for (const group of DATA.ui.menu) {
      menu.append(el("hr"));
      for (const [label, keys, name] of group) {
        const item = el("div", "item");
        item.append(icon(name), el("span", "", label), el("span", "keys", keys));
        menu.append(item);
      }
    }
    box.append(menu);
    const word = box.querySelector("[data-miss]");
    if (word) {
      const at = word.getBoundingClientRect();
      const base = box.getBoundingClientRect();
      const left = Math.min(at.left - base.left + 8, base.width - menu.offsetWidth - 8);
      menu.style.left = `${Math.max(8, left)}px`;
      menu.style.top = `${at.bottom - base.top + 6}px`;
      // the menu is taller than the sheet: let the window grow so none of it is cut off
      box.style.minHeight = `${at.bottom - base.top + 6 + menu.offsetHeight + 16}px`;
    }
    requestAnimationFrame(() => menu.classList.add("shown"));
    return menu;
  }

  // ---- the window at the top of the page ----

  function heroWindow() {
    const win = document.querySelector("[data-hero]");
    if (!win) return;
    const menubar = win.querySelector(".menubar");
    DATA.ui.menus.forEach((name) => menubar.append(el("span", "", name)));
    const side = win.querySelector(".side");
    const row = (name, text, cls) => {
      const r = el("div", `row ${cls || ""}`);
      r.append(icon(name), el("span", "", text));
      side.append(r);
    };
    const title = el("div", "row muted", DATA.ui.sheets);
    title.style.fontSize = "12.5px";
    side.append(title);
    for (const [folder, keys] of DATA.sidebar) {
      if (folder) row("folder", folder);
      for (const key of keys) {
        row("sheet", DATA.sheets[key].name, `${folder ? "child" : ""} ${key === "hero" ? "current" : ""}`);
      }
    }
    side.append(el("div", "gap"));
    row("help", DATA.ui.help);
    row("trash", DATA.ui.trash);
    win.querySelector(".rates").textContent = DATA.ui.rates;
    const sheet = new Sheet(win.querySelector(".sheet"), DATA.sheets.hero, win.querySelector(".total"));
    if (calm) return sheet.showAll();
    whenSeen(win, () => sheet.type().catch(() => {}));
  }

  // ---- the examples, one tab at a time ----

  function examples() {
    const root = document.querySelector("[data-examples]");
    if (!root) return;
    const tabs = [...root.querySelectorAll("[role=tab]")];
    const win = root.querySelector(".window");
    const box = win.querySelector(".sheet");
    const title = win.querySelector(".titlebar .name");
    const status = win.querySelector(".total");
    let current = null;
    let auto = !calm;
    let timer = 0;

    for (const tab of tabs) {
      const strong = tab.querySelector("strong");
      strong.prepend(icon(tab.dataset.icon));
    }

    async function show(i) {
      clearTimeout(timer);
      if (current) current.stop();
      tabs.forEach((t, k) => {
        t.setAttribute("aria-selected", String(k === i));
        t.tabIndex = k === i ? 0 : -1;
      });
      const key = tabs[i].dataset.sheet;
      const data = DATA.sheets[key];
      title.textContent = data.name;
      current = new Sheet(box, data, status);
      box.querySelector(".ctxmenu")?.remove();
      box.style.minHeight = "";
      try {
        if (calm) current.showAll();
        else await current.type();
      } catch {
        return; // another tab was picked
      }
      if (data.suggestions) {
        await new Promise((r) => setTimeout(r, calm ? 0 : 600));
        if (current.sheet === data) contextMenu(box, data);
      }
      if (auto) timer = setTimeout(() => show((i + 1) % tabs.length), data.suggestions ? 7000 : 3500);
    }

    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => {
        auto = false;
        show(i);
      });
      tab.addEventListener("keydown", (e) => {
        const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
        if (!step) return;
        e.preventDefault();
        const next = (i + step + tabs.length) % tabs.length;
        tabs[next].focus();
        auto = false;
        show(next);
      });
    });
    root.querySelector(".rates-note [data-rates-date]").textContent = DATA.rates_date;
    whenSeen(root, () => show(0));
  }

  function whenSeen(node, run) {
    if (!("IntersectionObserver" in window)) return run();
    const seen = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        seen.disconnect();
        run();
      }
    }, { threshold: 0.35 });
    seen.observe(node);
  }

  // ---- download links from the latest GitHub release ----

  function system() {
    const p = `${navigator.userAgentData?.platform || ""} ${navigator.platform || ""} ${navigator.userAgent}`;
    if (/android|iphone|ipad|ipod/i.test(p)) return "";
    if (/win/i.test(p)) return "windows";
    if (/mac/i.test(p)) return "mac";
    if (/linux|x11|cros/i.test(p)) return "linux";
    return "";
  }

  async function latestRelease() {
    try {
      const kept = sessionStorage.getItem("release");
      if (kept) return JSON.parse(kept);
    } catch {
      // no session storage: ask GitHub
    }
    const reply = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!reply.ok) throw new Error(`GitHub said ${reply.status}`);
    const release = await reply.json();
    const kept = {
      tag: release.tag_name,
      url: release.html_url,
      date: release.published_at,
      files: Object.fromEntries(release.assets.map((a) => [a.name, a.browser_download_url])),
    };
    try {
      sessionStorage.setItem("release", JSON.stringify(kept));
    } catch {
      // fine, we'll ask again next time
    }
    return kept;
  }

  async function downloads() {
    const boxes = [...document.querySelectorAll("[data-downloads]")];
    if (!boxes.length) return;
    let release;
    try {
      release = await latestRelease();
    } catch {
      return; // the buttons already point at the releases page
    }
    const file = (suffix) => Object.entries(release.files).find(([name]) => name.endsWith(suffix))?.[1];
    const links = {
      linux: file("_linux_x64.tar.gz"),
      windows: file("_windows_x64.zip"),
      mac_arm64: file("_macos_arm64.zip"),
      mac_x64: file("_macos_x64.zip"),
    };
    const os = system();
    const main = {
      linux: [["linux", TEXT.linux]],
      windows: [["windows", TEXT.windows]],
      mac: [
        ["mac_arm64", TEXT.mac_arm64],
        ["mac_x64", TEXT.mac_x64],
      ],
    }[os] || [
      ["linux", TEXT.linux_short],
      ["windows", TEXT.windows_short],
      ["mac_arm64", TEXT.mac_arm64],
      ["mac_x64", TEXT.mac_x64],
    ];
    const when = new Date(release.date).toLocaleDateString(lang === "uk" ? "uk-UA" : "en-GB", TEXT.date);
    for (const box of boxes) {
      const buttons = box.querySelector(".downloads");
      buttons.textContent = "";
      for (const [key, label] of main) {
        if (!links[key]) continue;
        const a = el("a", `button${os ? " primary" : ""}`, label);
        a.href = links[key];
        buttons.append(a);
      }
      const all = el("a", "button", TEXT.all);
      all.href = release.url;
      buttons.append(all);
      const note = box.querySelector(".download-note");
      if (note) note.textContent = TEXT.version(release.tag.replace(/^v/, ""), when);
    }
  }

  // ---- language links ----

  for (const link of document.querySelectorAll("[data-lang]")) {
    link.addEventListener("click", () => remember("lang", link.dataset.lang));
  }

  heroWindow();
  examples();
  downloads();
})();
