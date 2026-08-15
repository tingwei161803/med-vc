/* =========================================================================
   med-vc · app.js  (vanilla, zero build)

   Page-level layout engine. shell.js has already injected the shared chrome
   (app bar, cross-page nav, footer, #dialog) and published window.LDW. This
   picks a renderer by <body data-page>'s layout, paints #page, wires it, and
   re-renders on language switch so nothing is ever left in one language.

   Layouts: hub · directory · analysis · methodology  (data in window.MED_VC)
   ========================================================================= */
(function () {
  "use strict";

  function boot() {
    if (!window.LDW || !window.LDW.ready) {
      document.addEventListener("ldw:shell-ready", boot, { once: true });
      return;
    }
    var L = window.LDW;
    var t = L.t, esc = L.escapeHtml, r = L.r, state = L.state;
    var pageEl = document.getElementById("page");
    var teardowns = [];
    var DB = window.MED_VC || { entities: [], taxonomy: {}, stats: {} };
    var TAX = DB.taxonomy || {};
    var STATS = DB.stats || {};

    /* ---- bilingual UI strings emitted by renderers ---- */
    var UI = {
      en: {
        pitch: "An open, sourced directory of the money behind medicine, in two halves that point at each other: the investors — life-science VCs, pharma & medtech corporate arms, crossover funds, bio accelerators, university & hospital funds, disease-foundation venture philanthropy, government programs — and the companies they fund. Every link between them is resolved from the data, never hand-written.",
        browse: "Browse the directory", explore: "Explore",
        search: "Search name, thesis, company, city…",
        filters: "Filters", reset: "Reset", results: "results", result: "result",
        exportCsv: "Export CSV", noResults: "No investors match these filters.",
        clearAll: "Clear all filters",
        axisRegion: "Region", axisType: "Type", axisSector: "Sector",
        axisModality: "Modality", axisIndication: "Indication", axisStage: "Stage",
        axisConf: "Confidence", axisBacker: "Backed by",
        backers: "Backed by", backerNone: "No notable institutional backer on record",
        portfolioHint: "is a portfolio company. These listed investors backed it:",
        portfolioHintMore: "and more",
        investorsOnly: "This directory catalogues investors, not the companies they fund — searching a startup name only works if a listed investor names it among its notable investments.",
        conf_high: "High", conf_medium: "Medium", conf_low: "Low",
        founded: "Founded", hq: "HQ", status: "Status", website: "Website",
        stages: "Stages", checkSize: "Check size", thesis: "Thesis",
        modalities: "Modalities", indications: "Indications",
        aum: "AUM", currentFund: "Current fund", portfolio: "Portfolio",
        notable: "Notable investments", program: "Program",
        invest: "Investment", equity: "Equity", labSpace: "Lab space", apply: "Apply",
        sources: "Sources & evidence", confidence: "Confidence",
        yes: "Yes", visit: "Visit site",
        byRegion: "Investors by region", ofTotal: "of total",
        capBy: "By region", capType: "By organization type", capSector: "By sector",
        capModality: "By modality (top 10)", capIndication: "By indication (top 10)",
        capConf: "By source confidence",
        provenance: "Provenance", quoteBacked: "quote-backed", entities: "institutions",
        regionsN: "regions", typesN: "organization types", sourcesN: "sources",

        /* ---- companies page ---- */
        coSearch: "Search company, product, investor, city…",
        coNone: "No companies match these filters.",
        coCount: "companies", coCount1: "company",
        axisCategory: "Sector", axisStatus: "Status", axisDev: "Stage of development",
        coWhat: "What it does", coRaised: "Total raised", coVal: "Valuation",
        coLastRound: "Last round", coInvestors: "Investors", coDev: "Development stage",
        coLead: "Lead program", coReg: "Regulatory", coExit: "Exit", coUnicorn: "Unicorn",
        coPortfolio: "Portfolio in this directory",
        coInvestorsNone: "No investors recorded yet",
        coNotListed: "not in this directory",
        coOpenInvestor: "Open investor profile",
        coOpenCompany: "Open company profile",
        coBacklog: "companies named by listed investors are not profiled yet — coverage is being filled in region by region.",
        coInvestorHint: "is an investor. Companies here that it backed:",
        coEmptyNote: "This half of the directory is newer than the investor half and still filling in.",
        companiesN: "companies", linksN: "investor–company links",
        secInvestors: "Investors", secCompanies: "Companies & the link graph",
        capCoRegion: "Companies by region", capCoCategory: "Companies by sector",
        capCoStatus: "By corporate status", capCoDev: "By stage of development",
        capLinks: "Link coverage",
        linkBoth: "Confirmed by both sides", linkCo: "Companies with a listed investor",
        linkInv: "Investors with a profiled company", linkPending: "Named but not yet profiled"
      },
      zh: {
        pitch: "一份開放、逐筆帶來源的「醫療背後的錢」名錄,分成互相指向的兩半:一半是出錢的人 —— 生醫創投、藥廠與醫材企業創投、公私跨界基金、生醫加速器、大學與醫院基金、疾病基金會公益創投、政府計畫;另一半是拿錢的公司。兩邊之間的每一條連結都由資料解析而來,不是手寫的。",
        browse: "瀏覽名錄", explore: "前往",
        search: "搜尋機構名、論點、被投公司、城市…",
        filters: "篩選", reset: "重設", results: "筆結果", result: "筆結果",
        exportCsv: "匯出 CSV", noResults: "沒有符合這些條件的機構。",
        clearAll: "清除所有篩選",
        axisRegion: "地區", axisType: "類型", axisSector: "子領域",
        axisModality: "治療模式", axisIndication: "適應症", axisStage: "階段",
        axisConf: "信心度", axisBacker: "背後金主",
        backers: "背後金主", backerNone: "查無重要機構出資方",
        portfolioHint: "是被投公司。名錄中投資過它的機構:",
        portfolioHintMore: "等",
        investorsOnly: "本站收錄的是投資機構,不是被投公司 —— 用新創公司名搜尋,只有在某家收錄機構把它列為代表投資時才查得到。",
        conf_high: "高", conf_medium: "中", conf_low: "低",
        founded: "成立", hq: "總部", status: "狀態", website: "官網",
        stages: "投資階段", checkSize: "單筆金額", thesis: "投資論點",
        modalities: "治療模式", indications: "適應症",
        aum: "管理資產", currentFund: "當前基金", portfolio: "投資組合",
        notable: "代表投資", program: "計畫",
        invest: "投資額", equity: "股權", labSpace: "實驗室空間", apply: "申請",
        sources: "來源與佐證", confidence: "信心度",
        yes: "是", visit: "前往官網",
        byRegion: "各地區機構數", ofTotal: "佔總數",
        capBy: "依地區", capType: "依機構類型", capSector: "依子領域",
        capModality: "依治療模式(前 10)", capIndication: "依適應症(前 10)",
        capConf: "依來源信心度",
        provenance: "溯源", quoteBacked: "帶原文引用", entities: "家機構",
        regionsN: "個地區", typesN: "種機構類型", sourcesN: "條來源",

        /* ---- companies page ---- */
        coSearch: "搜尋公司名、產品、投資人、城市…",
        coNone: "沒有符合這些條件的公司。",
        coCount: "家公司", coCount1: "家公司",
        axisCategory: "領域", axisStatus: "公司狀態", axisDev: "發展階段",
        coWhat: "在做什麼", coRaised: "累計募資", coVal: "估值",
        coLastRound: "最近一輪", coInvestors: "投資人", coDev: "發展階段",
        coLead: "主力產品/管線", coReg: "法規核准", coExit: "退出", coUnicorn: "獨角獸",
        coPortfolio: "名錄中的投資組合",
        coInvestorsNone: "尚無投資人紀錄",
        coNotListed: "未收錄於本名錄",
        coOpenInvestor: "查看投資機構",
        coOpenCompany: "查看公司",
        coBacklog: "家被收錄機構點名、但尚未建檔的公司 —— 正依地區逐輪補齊。",
        coInvestorHint: "是投資機構。名錄中它投過的公司:",
        coEmptyNote: "新創這一半比投資機構那一半年輕,仍在逐輪補齊中。",
        companiesN: "家新創", linksN: "條投資關係連結",
        secInvestors: "投資機構", secCompanies: "新創與連結圖",
        capCoRegion: "各地區新創數", capCoCategory: "依領域",
        capCoStatus: "依公司狀態", capCoDev: "依發展階段",
        capLinks: "連結覆蓋率",
        linkBoth: "兩邊都證實", linkCo: "已連上投資人的公司",
        linkInv: "已連上公司的機構", linkPending: "被點名但尚未建檔"
      }
    };
    function tt(k) { return (UI[state.lang] || UI.en)[k]; }

    /* ---- icon per backer kind (Material Symbols) ---- */
    var BACKER_ICON = {
      "big-tech": "memory", "ai-lab": "neurology", "pharma": "medication",
      "medtech": "cardiology", "payer-insurer": "shield", "diagnostics-tools": "biotech",
      "conglomerate": "domain", "financial-institution": "account_balance",
      "telecom": "cell_tower", "retail-consumer": "storefront", "university": "school",
      "hospital-system": "local_hospital", "government": "gavel", "foundation": "volunteer_activism",
      "family-office": "diversity_3", "other": "corporate_fare"
    };

    /* ---- the company half + the link table between the two halves ---- */
    var COMPANIES = DB.companies || [];
    var LINKS = DB.links || {};
    var I2C = LINKS.i2c || {};          // investor id -> [company id]
    var C2I_EXTRA = LINKS.c2iExtra || {}; // edges only the investor side asserts
    var CSTATS = DB.companyStats || {};
    var ENT_BY_ID = Object.create(null);
    DB.entities.forEach(function (e) { ENT_BY_ID[e.id] = e; });
    var CO_BY_ID = Object.create(null);
    COMPANIES.forEach(function (c) { CO_BY_ID[c.id] = c; });

    /* A company's full investor list is the union of two sources: the names on
       its own record, and edges asserted only by an investor's portfolio page.
       Merging here rather than at build time keeps the payload from carrying
       the same edge twice. */
    function investorsOf(c) {
      var out = [], seen = Object.create(null);
      (c.inv || []).forEach(function (i) {
        out.push({ name: i[0], id: i[1], role: i[2] });
        if (i[1]) seen[i[1]] = 1;
      });
      (C2I_EXTRA[c.id] || []).forEach(function (eid) {
        if (seen[eid] || !ENT_BY_ID[eid]) return;
        out.push({ name: ENT_BY_ID[eid].name.en, id: eid, role: "" });
      });
      return out;
    }

    /* ---- taxonomy label lookup: LABEL[axis][slug] = {en,zh} ---- */
    var LABEL = {};
    ["types", "sectors", "modalities", "indications", "stages", "regions",
     "backerKinds", "backerRels", "companyStatus", "devStages"].forEach(function (axis) {
      LABEL[axis] = {};
      (TAX[axis] || []).forEach(function (x) { LABEL[axis][x.slug] = { en: x.en, zh: x.zh }; });
    });
    var CONF = { high: { en: "High", zh: "高" }, medium: { en: "Medium", zh: "中" }, low: { en: "Low", zh: "低" } };
    function lab(axis, slug) { var m = LABEL[axis] && LABEL[axis][slug]; return m ? t(m) : slug; }
    function typeLab(slug) { return lab("types", slug); }
    function regionLab(slug) { return lab("regions", slug); }

    function num(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

    /* ---- filter/export primitives, shared by both directory pages ---- */
    function set() { return Object.create(null); }
    function anySel(o) { for (var k in o) return true; return false; }
    /* OR within an axis, AND across axes: picking "oncology" and "neurology"
       should widen the result set, while adding a region should narrow it. */
    function arrHit(selSet, vals) {
      if (!anySel(selSet)) return true;
      for (var i = 0; i < (vals || []).length; i++) if (selSet[vals[i]]) return true;
      return false;
    }
    function csvCell(v) {
      v = String(v == null ? "" : v);
      return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    function downloadCsv(filename, cols, rows) {
      var lines = [cols.join(",")].concat(rows.map(function (rw) { return rw.map(csvCell).join(","); }));
      // The BOM is what makes Excel read the CJK columns as UTF-8 rather than mojibake.
      var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    /* ---- SVG bar chart (horizontal, label + value) ---- */
    function barsH(series, accentVar) {
      var max = Math.max.apply(null, series.map(function (d) { return d.value; }).concat([1]));
      var rows = series.map(function (d) {
        var pct = (d.value / max) * 100;
        return '<div class="hbar" data-item>' +
          '<span class="hbar__label" title="' + esc(d.label) + '">' + esc(d.label) + "</span>" +
          '<span class="hbar__track"><span class="hbar__fill" style="width:' + r(pct) + "%" +
            (accentVar ? ";background:var(" + accentVar + ")" : "") + '"></span></span>' +
          '<span class="hbar__value">' + esc(num(d.value)) + "</span></div>";
      }).join("");
      return '<div class="hbars">' + rows + "</div>";
    }
    function statsSeries(map, axis, limit) {
      var arr = Object.keys(map).map(function (k) {
        return { slug: k, value: map[k], label: axis ? lab(axis, k) : k };
      }).sort(function (a, b) { return b.value - a.value; });
      return limit ? arr.slice(0, limit) : arr;
    }

    /* ---- counter animation for hero stat tiles ---- */
    function animateCounters() {
      var els = [].slice.call(pageEl.querySelectorAll("[data-count]"));
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      // Browsers do not run requestAnimationFrame in a hidden tab, so a page
      // opened in a background tab — cmd-click, "open in new tab", a restored
      // session — renders every headline number as a literal 0 and holds it
      // there. The animation is decoration; the number is the content, so when
      // there is no frame loop to animate in, skip straight to the value.
      var noFrames = reduce || document.hidden;
      els.forEach(function (el) {
        var target = parseFloat(el.dataset.count) || 0;
        if (noFrames) { el.textContent = el.dataset.suffix ? num(target) + el.dataset.suffix : num(target); return; }
        var start = null, dur = 900;
        function step(ts) {
          if (start === null) start = ts;
          var p = Math.min((ts - start) / dur, 1);
          var v = Math.round(target * (1 - Math.pow(1 - p, 3)));
          el.textContent = num(v) + (el.dataset.suffix || "");
          if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }

    function head(p) {
      var sub = t(p.subtitle) ? '<p class="page-head__sub">' + esc(t(p.subtitle)) + "</p>" : "";
      return '<header class="page-head"><h1>' + esc(t(p.title)) + "</h1>" + sub + "</header>";
    }

    /* provenance figures (live from stats) */
    var TOTAL = STATS.total || DB.entities.length;
    var SRC = STATS.sources || 0;
    var QUOTE_PCT = TOTAL ? Math.round(((STATS.quoted || 0) / TOTAL) * 100) : 0;
    var REGION_CT = (TAX.regions || []).length || 12;
    var TYPE_CT = (TAX.types || []).length || 15;

    /* =====================================================================
       RENDERERS
       ===================================================================== */
    var RENDERERS = {

      /* ---------------- hub / overview ---------------- */
      hub: function (p) {
        var tiles = [
          { v: TOTAL, s: "", label: tt("entities") },
          { v: CSTATS.total || 0, s: "", label: tt("companiesN") },
          { v: CSTATS.edges || 0, s: "", label: tt("linksN") },
          { v: REGION_CT, s: "", label: tt("regionsN") },
          { v: SRC, s: "", label: tt("sourcesN") },
          { v: QUOTE_PCT, s: "%", label: tt("quoteBacked") }
        ].filter(function (x) { return x.v; }).map(function (x) {
          return '<div class="stat" data-item>' +
            '<b class="stat__value" data-count="' + esc(String(x.v)) + '" data-suffix="' + esc(x.s) + '">0</b>' +
            '<span class="stat__label">' + esc(x.label) + "</span></div>";
        }).join("");

        var region = barsH(statsSeries(STATS.by_region || {}, "regions"), "--primary");

        var cards = L.pages.filter(function (q) { return q.slug !== "home"; }).map(function (q) {
          return '<a class="navcard" data-item href="' + esc(L.pageHref(q)) + '">' +
            '<span class="material-symbols-rounded navcard__icon" aria-hidden="true">' + esc(q.icon || "label") + "</span>" +
            '<span class="navcard__body"><span class="navcard__title">' + esc(t(q.title)) + "</span>" +
            '<span class="navcard__sub">' + esc(t(q.subtitle)) + "</span></span>" +
            '<span class="material-symbols-rounded navcard__go" aria-hidden="true">arrow_forward</span></a>';
        }).join("");

        return '<section class="hero">' +
            '<h1 class="hero__title">' + esc(t(L.meta.title)) + "</h1>" +
            '<p class="hero__subtitle">' + esc(t(L.meta.subtitle)) + "</p>" +
            '<p class="hero__pitch">' + esc(tt("pitch")) + "</p>" +
          "</section>" +
          '<div class="stats">' + tiles + "</div>" +
          '<a class="cta" href="directory.html"><span class="material-symbols-rounded" aria-hidden="true">travel_explore</span>' + esc(tt("browse")) + "</a>" +
          '<section class="panel" data-item><h2 class="panel__title">' + esc(tt("byRegion")) + "</h2>" + region + "</section>" +
          '<nav class="navcards">' + cards + "</nav>";
      },

      /* ---------------- directory (core) ---------------- */
      directory: function (p) {
        var axes = [
          { key: "region", tax: "regions", label: tt("axisRegion"), multi: false },
          { key: "type", tax: "types", label: tt("axisType"), multi: false },
          { key: "sector", tax: "sectors", label: tt("axisSector"), multi: true },
          { key: "modality", tax: "modalities", label: tt("axisModality"), multi: true },
          { key: "indication", tax: "indications", label: tt("axisIndication"), multi: true },
          { key: "stage", tax: "stages", label: tt("axisStage"), multi: true },
          { key: "backer", tax: "backerKinds", label: tt("axisBacker"), multi: true, counts: STATS.by_backer_kind }
        ];
        var facets = axes.map(function (a) {
          var chips = (TAX[a.tax] || []).filter(function (x) {
            // a facet with counts only offers values something actually has —
            // an "AI lab" chip that always yields 0 results is just noise
            return !a.counts || a.counts[x.slug];
          }).map(function (x) {
            var n = a.counts ? ' <span class="fchip__n">' + esc(String(a.counts[x.slug])) + "</span>" : "";
            return '<button class="fchip" type="button" data-axis="' + a.key + '" data-val="' + esc(x.slug) + '">' +
              esc(t(x)) + n + "</button>";
          }).join("");
          return '<div class="facet"><h3 class="facet__title">' + esc(a.label) + "</h3>" +
            '<div class="facet__chips">' + chips + "</div></div>";
        }).join("");
        var confChips = ["high", "medium", "low"].map(function (c) {
          return '<button class="fchip fchip--conf fchip--conf-' + c + '" type="button" data-axis="conf" data-val="' + c + '">' +
            esc(t(CONF[c])) + "</button>";
        }).join("");
        var confFacet = '<div class="facet"><h3 class="facet__title">' + esc(tt("axisConf")) + "</h3>" +
          '<div class="facet__chips">' + confChips + "</div></div>";

        return head(p) +
          '<div class="dir">' +
            '<aside class="dir__filters" id="filters" aria-label="' + esc(tt("filters")) + '">' +
              '<div class="dir__filters-head"><span class="material-symbols-rounded" aria-hidden="true">tune</span>' +
                '<b>' + esc(tt("filters")) + "</b>" +
                '<button class="linkbtn" id="resetBtn" type="button">' + esc(tt("reset")) + "</button></div>" +
              facets + confFacet +
            "</aside>" +
            '<div class="dir__main">' +
              '<div class="dir__bar">' +
                '<div class="searchbox"><span class="material-symbols-rounded" aria-hidden="true">search</span>' +
                  '<input id="search" type="search" autocomplete="off" placeholder="' + esc(tt("search")) + '" aria-label="' + esc(tt("search")) + '"></div>' +
                '<button class="linkbtn" id="mobFilterBtn" type="button" aria-expanded="false"><span class="material-symbols-rounded" aria-hidden="true">tune</span>' + esc(tt("filters")) + "</button>" +
                '<button class="linkbtn linkbtn--ghost" id="csvBtn" type="button"><span class="material-symbols-rounded" aria-hidden="true">download</span>' + esc(tt("exportCsv")) + "</button>" +
                '<span class="dir__count" id="resultCount"></span>' +
              "</div>" +
              '<div id="ctxBanner"></div>' +
              '<div class="dir__grid" id="grid"></div>' +
              '<div class="empty" id="empty" hidden><p>' + esc(tt("noResults")) + "</p>" +
                '<p class="empty__note">' + esc(tt("investorsOnly")) + "</p></div>" +
            "</div>" +
          "</div>";
      },

      /* ---------------- companies ----------------
         Same skeleton as `directory` on purpose: one search box, one facet
         rail, one grid, one dialog. The two halves of the site are different
         data, not different interaction models, and a user who has learned one
         should not have to learn the other. */
      companies: function (p) {
        var axes = [
          { key: "region", tax: "regions", label: tt("axisRegion"), counts: CSTATS.by_region },
          { key: "category", tax: "sectors", label: tt("axisCategory"), counts: CSTATS.by_category },
          { key: "status", tax: "companyStatus", label: tt("axisStatus"), counts: CSTATS.by_status },
          { key: "dev", tax: "devStages", label: tt("axisDev"), counts: CSTATS.by_development_stage },
          { key: "modality", tax: "modalities", label: tt("axisModality") },
          { key: "indication", tax: "indications", label: tt("axisIndication") }
        ];
        var facets = axes.map(function (a) {
          var chips = (TAX[a.tax] || []).filter(function (x) {
            return !a.counts || a.counts[x.slug];
          }).map(function (x) {
            var n = a.counts ? ' <span class="fchip__n">' + esc(String(a.counts[x.slug])) + "</span>" : "";
            return '<button class="fchip" type="button" data-axis="' + a.key + '" data-val="' + esc(x.slug) + '">' +
              esc(t(x)) + n + "</button>";
          }).join("");
          if (!chips) return "";
          return '<div class="facet"><h3 class="facet__title">' + esc(a.label) + "</h3>" +
            '<div class="facet__chips">' + chips + "</div></div>";
        }).join("");

        // State the backlog in the page furniture, not only in the empty state:
        // the count is the honest denominator for everything shown below it.
        var pending = CSTATS.unprofiled_portfolio_names || 0;
        var backlog = pending
          ? '<p class="dir__note"><span class="material-symbols-rounded" aria-hidden="true">pending</span>' +
            num(pending) + " " + esc(tt("coBacklog")) + "</p>"
          : "";

        return head(p) +
          '<div class="dir">' +
            '<aside class="dir__filters" id="filters" aria-label="' + esc(tt("filters")) + '">' +
              '<div class="dir__filters-head"><span class="material-symbols-rounded" aria-hidden="true">tune</span>' +
                '<b>' + esc(tt("filters")) + "</b>" +
                '<button class="linkbtn" id="resetBtn" type="button">' + esc(tt("reset")) + "</button></div>" +
              facets +
            "</aside>" +
            '<div class="dir__main">' +
              '<div class="dir__bar">' +
                '<div class="searchbox"><span class="material-symbols-rounded" aria-hidden="true">search</span>' +
                  '<input id="search" type="search" autocomplete="off" placeholder="' + esc(tt("coSearch")) + '" aria-label="' + esc(tt("coSearch")) + '"></div>' +
                '<button class="linkbtn" id="mobFilterBtn" type="button" aria-expanded="false"><span class="material-symbols-rounded" aria-hidden="true">tune</span>' + esc(tt("filters")) + "</button>" +
                '<button class="linkbtn linkbtn--ghost" id="csvBtn" type="button"><span class="material-symbols-rounded" aria-hidden="true">download</span>' + esc(tt("exportCsv")) + "</button>" +
                '<span class="dir__count" id="resultCount"></span>' +
              "</div>" +
              backlog +
              '<div id="ctxBanner"></div>' +
              '<div class="dir__grid" id="grid"></div>' +
              '<div class="empty" id="empty" hidden><p>' + esc(tt("coNone")) + "</p>" +
                '<p class="empty__note">' + esc(tt("coEmptyNote")) + "</p></div>" +
            "</div>" +
          "</div>";
      },

      /* ---------------- analysis (charts) ---------------- */
      analysis: function (p) {
        var CO_N = CSTATS.total || 0;
        var tiles = [
          { v: TOTAL, s: "", label: tt("entities") },
          { v: CO_N, s: "", label: tt("companiesN") },
          { v: CSTATS.edges || 0, s: "", label: tt("linksN") },
          { v: REGION_CT, s: "", label: tt("regionsN") },
          { v: SRC, s: "", label: tt("sourcesN") },
          { v: QUOTE_PCT, s: "%", label: tt("quoteBacked") }
        ].map(function (x) {
          return '<div class="stat" data-item>' +
            '<b class="stat__value" data-count="' + esc(String(x.v)) + '" data-suffix="' + esc(x.s) + '">0</b>' +
            '<span class="stat__label">' + esc(x.label) + "</span></div>";
        }).join("");
        function panel(cap, series, accent) {
          return '<section class="panel" data-item><h2 class="panel__title">' + esc(cap) + "</h2>" +
            barsH(series, accent) + "</section>";
        }
        var conf = ["high", "medium", "low"].map(function (c) {
          return { slug: c, value: (STATS.by_confidence || {})[c] || 0, label: t(CONF[c]) };
        });

        /* The link graph deserves its own read-out, because its interesting
           number is not the edge count but how much of it is corroborated:
           an edge both sides assert is a stronger claim than either alone. */
        var coverage = CO_N ? [
          { slug: "both", value: CSTATS.edges_confirmed_both_sides || 0, label: tt("linkBoth") },
          { slug: "linkedco", value: CSTATS.linked_companies || 0, label: tt("linkCo") },
          { slug: "linkedinv", value: CSTATS.linked_investors || 0, label: tt("linkInv") },
          { slug: "pending", value: CSTATS.unprofiled_portfolio_names || 0, label: tt("linkPending") }
        ] : [];

        var coPanels = CO_N
          ? panel(tt("capCoCategory"), statsSeries(CSTATS.by_category || {}, "sectors", 12), "--primary") +
            panel(tt("capCoRegion"), statsSeries(CSTATS.by_region || {}, "regions"), "--secondary") +
            panel(tt("capCoStatus"), statsSeries(CSTATS.by_status || {}, "companyStatus"), "--tertiary") +
            panel(tt("capCoDev"), statsSeries(CSTATS.by_development_stage || {}, "devStages"), "--primary") +
            panel(tt("capLinks"), coverage, "--secondary")
          : "";

        return head(p) +
          '<div class="stats">' + tiles + "</div>" +
          '<h2 class="section-head">' + esc(tt("secInvestors")) + "</h2>" +
          '<div class="panels">' +
            panel(tt("capBy"), statsSeries(STATS.by_region || {}, "regions"), "--primary") +
            panel(tt("capType"), statsSeries(STATS.by_type || {}, "types"), "--secondary") +
            panel(tt("capSector"), statsSeries(STATS.by_sector || {}, "sectors", 12), "--primary") +
            panel(tt("capModality"), statsSeries(STATS.by_modality || {}, "modalities", 10), "--tertiary") +
            panel(tt("capIndication"), statsSeries(STATS.by_indication || {}, "indications", 10), "--secondary") +
            panel(tt("capConf"), conf, "--tertiary") +
          "</div>" +
          (coPanels
            ? '<h2 class="section-head">' + esc(tt("secCompanies")) + "</h2>" +
              '<div class="panels">' + coPanels + "</div>"
            : "");
      },

      /* ---------------- methodology (article) ---------------- */
      methodology: function (p) {
        var prov = [
          { v: TOTAL, s: "", label: tt("entities") },
          { v: SRC, s: "", label: tt("sourcesN") },
          { v: QUOTE_PCT, s: "%", label: tt("quoteBacked") }
        ].map(function (x) {
          return '<div class="stat" data-item><b class="stat__value">' + esc(num(x.v) + x.s) + "</b>" +
            '<span class="stat__label">' + esc(x.label) + "</span></div>";
        }).join("");
        /* Counts are interpolated, never typed. Every hardcoded figure in this
           article went stale the first time the dataset grew. */
        var C = STATS.by_confidence || {};
        var CONF_SPLIT = "high " + num(C.high || 0) + " · medium " + num(C.medium || 0) + " · low " + num(C.low || 0);
        var CONF_SPLIT_ZH = "高 " + num(C.high || 0) + " · 中 " + num(C.medium || 0) + " · 低 " + num(C.low || 0);
        var CO_N = CSTATS.total || 0;
        var LINK_EN = CO_N
          ? "The directory has two halves. One catalogues investors; the other catalogues the medical and biomedical companies they fund — " +
            num(CO_N) + " so far, against " + num(TOTAL) + " investors. They are linked by " + num(CSTATS.edges || 0) +
            " investor–company edges, " + num(CSTATS.edges_confirmed_both_sides || 0) +
            " of which both sides independently assert. Those links are resolved by name at build time rather than hand-written, and only on an unambiguous match: a wrong link reads as a fact, while a missing one is visibly missing, so ambiguity is left unresolved and published as a backlog instead of guessed. The two halves share one vocabulary for sector, modality and indication, which is what lets a filter carry across from a fund to the companies it funds. Coverage of the company half is being filled in region by region; " +
            num(CSTATS.unprofiled_portfolio_names || 0) + " companies named by listed investors are not profiled yet, and the Companies page says so on its face."
          : "";
        var LINK_ZH = CO_N
          ? "本名錄有兩半:一半收錄投資機構,另一半收錄它們投資的醫療生醫公司 —— 目前 " +
            num(CO_N) + " 家公司對 " + num(TOTAL) + " 家機構,之間有 " + num(CSTATS.edges || 0) +
            " 條投資關係連結,其中 " + num(CSTATS.edges_confirmed_both_sides || 0) +
            " 條是兩邊各自獨立主張、互相印證的。這些連結不是手寫的,而是在 build 階段用名稱解析出來,而且只在唯一命中時才建立:錯誤的連結會被當成事實,缺少的連結至少看得出來缺,所以模糊的情況一律留空並公開成待辦清單,不用猜的補。兩半共用同一套子領域 / 治療模式 / 適應症詞彙,篩選條件才能從基金一路帶到它投的公司。公司這一半正依地區逐輪補齊;目前還有 " +
            num(CSTATS.unprofiled_portfolio_names || 0) + " 家被收錄機構點名、但尚未建檔的公司,「新創」頁面上就直接寫著這個數字。"
          : "";

        var SECTIONS = {
          en: [
            ["What this is", "med-vc is an open, structured directory of the organizations that invest in medicine and biomedicine worldwide — venture capital firms, pharma / medtech / payer / provider corporate venture arms, crossover funds, bio accelerators and incubators, university and hospital funds, disease-foundation venture philanthropy, government programs, venture studios, angel networks and family offices — together with the companies they fund."],
            ["Sourced per institution", "Every entry carries at least one real source URL, and every quantitative claim — fund size, AUM, check size, founding year, portfolio count — is tied to a verbatim quote from a source. Where a figure could not be verified, the field is left empty rather than guessed. Amounts are kept in their reported currency and string form to avoid fabricated conversions."],
            ["Confidence ratings", "Each institution is rated high (official / primary source), medium (reputable secondary source), or low (a single weak or dated source). The split across the dataset is " + CONF_SPLIT + ". Confidence is shown on every card and in the detail view so you can weigh each entry yourself."],
            ["How it was assembled", "Research was fanned out across 188 slices (organization type × health subsector, per region) so coverage is complementary and overlap is minimal. Each slice was researched independently against live web sources in English and the local language, then everything was merged and de-duplicated — matching on normalized name, website domain, and slug, with accent-folding — into one validated dataset with a controlled vocabulary for type, sector, modality, indication, stage and region."],
            ["Who is behind the money", "Beyond what an institution invests in, every entry can record who stands behind it — the corporate parent, anchor LPs, or sponsoring institution — as structured `backing.backers[]` rows carrying the backer's name, kind (Big Tech, frontier AI lab, pharma, medtech, payer, sovereign fund, university, foundation and nine more), and the nature of the relationship (wholly-owned venture arm vs balance-sheet fund vs anchor LP). Each row is marked verified when a source states the relationship outright, or inferred when it was derived from the institution's own name or description — a corporate venture arm is almost always named after its parent, which makes that inference reliable but not equivalent to a citation. Use the \"Backed by\" filter to see, for instance, every fund in the directory running on Big Tech money."],
            ["Two-layer quality check", "Because the corpus was built over many runs, it went through two checks. A structural pass validated every record against the schema and flagged duplicates, missing sources and off-vocabulary values (0 critical issues remained). Then an agent fact-check audited a 120-institution sample — weighted toward lower-confidence rows — against the live web: it found 0 fabricated organizations and no systematic degradation, and the 16 minor factual corrections it surfaced (a founding year, a stale status, a fund figure) were applied and noted in each record."],
            ["Disclaimer", "This is an unofficial research compilation provided as-is. Figures on fund size, equity, acceptance rates and the like should be confirmed against each institution's official disclosures via the sources listed on every entry before you rely on them."]
          ],
          zh: [
            ["這是什麼", "med-vc 是一份開放、結構化的全球「醫療 / 生醫投資機構」名錄 —— 涵蓋生醫創投、藥廠 / 醫材 / 保險 / 醫療體系的企業創投、公私跨界基金、生醫加速器與育成中心、大學與醫院基金、疾病基金會公益創投、政府計畫、創業工作室、天使網絡與家族辦公室。主角是「投資者本身」,不是被投公司。"],
            ["逐機構溯源", "每一筆都至少有一個真實來源 URL;每個數字 —— 基金規模、管理資產、單筆金額、成立年份、投資組合數 —— 都對應到來源中的一段原文引用。查不到的欄位寧可留空也不猜。金額保留原始幣別與字串,避免虛構換匯。"],
            ["信心評級", "每家機構標為 高(官方 / 一手來源)、中(可靠二手)、或 低(單一弱或過時來源)。全資料集分佈為 " + CONF_SPLIT_ZH + "。信心度顯示在每張卡片與詳情頁,讓你自行判斷。"],
            ["如何蒐集", "研究切成 188 個切片(機構類型 × 健康子領域,依地區),讓覆蓋互補、重疊最小。每個切片以英文與當地語言對照即時網路獨立查證,再以正規化名稱、官網網域與 slug(含重音字折疊)合併去重,匯整成一份通過驗證、對 type / sector / modality / indication / stage / region 使用受控詞彙的資料集。"],
            ["錢是誰的", "除了「投什麼」,每筆資料還可以記錄「背後是誰的錢」——母公司、基石 LP 或主辦機構,以結構化的 `backing.backers[]` 呈現,每列帶金主名稱、金主類型(大型科技公司、前沿 AI 實驗室、藥廠、醫材、保險支付方、主權基金、大學、基金會等 16 類)與出資關係(全資創投部門 / 母公司資產負債表出資 / 基石 LP)。若來源直接寫明關係則標為 verified;若是由機構名稱或描述推得則標為 inferred——企業創投幾乎都以母公司命名,這讓推論相當可靠,但終究不等同於有引用佐證。用「背後金主」篩選器,就能一次看出名錄中哪些基金跑的是大型科技公司的錢。"],
            ["兩層品質檢查", "因資料跨多輪蒐集,做了兩層檢查。結構層對每筆做 schema 驗證,標記重複、缺來源與越界詞彙(最終 0 個嚴重問題)。事實層以 agent 抽樣 120 家機構(偏重低信心筆)對照即時網路查核:發現 0 家捏造機構、無系統性退化,查出的 16 處細節誤差(成立年份、過時狀態、基金數字)已修正並在各筆註記。"],
            ["免責聲明", "本名錄為非官方研究整理,依現況提供。基金規模、股權、錄取率等數字,引用前請依每筆列出的來源,對照各機構官方公開資訊查證。"]
          ]
        };
        /* Insert the link-graph section right after "What this is" — it is the
           structural fact a reader needs before anything else on this page
           makes sense — and only when there is a company half to describe. */
        if (LINK_EN) {
          SECTIONS.en.splice(1, 0, ["Two halves, and the links between them", LINK_EN]);
          SECTIONS.zh.splice(1, 0, ["兩半資料與它們之間的連結", LINK_ZH]);
        }
        var secs = (SECTIONS[state.lang] || SECTIONS.en).map(function (s, i) {
          return '<section class="prose" data-item id="sec-' + i + '"><h2>' + esc(s[0]) + "</h2><p>" + esc(s[1]) + "</p></section>";
        }).join("");
        return head(p) +
          '<div class="stats stats--prov">' + prov + "</div>" +
          '<div class="article">' + secs + "</div>";
      }
    };

    /* =====================================================================
       WIRE
       ===================================================================== */
    var WIRE = {
      hub: function () { animateCounters(); },
      analysis: function () { animateCounters(); },
      methodology: function () {},

      directory: function (p) {
        var ents = DB.entities;
        var grid = document.getElementById("grid");
        var searchEl = document.getElementById("search");
        var countEl = document.getElementById("resultCount");
        var emptyEl = document.getElementById("empty");
        var filtersEl = document.getElementById("filters");
        var sel = { region: set(), type: set(), sector: set(), modality: set(), indication: set(), stage: set(), conf: set(), backer: set() };
        var q = "";
        var visible = [];

        // company -> investors, derived at load from the `notable` lists already
        // in the payload. Costs nothing extra to ship and answers the question
        // people actually arrive with ("who backs Neko Health?") even though
        // this directory only catalogues investors.
        var PORTFOLIO = (function () {
          var idx = Object.create(null);
          ents.forEach(function (e) {
            (e.notable || []).forEach(function (c) {
              var k = String(c).trim().toLowerCase();
              if (!k) return;
              (idx[k] = idx[k] || []).push(e);
            });
          });
          return idx;
        })();

        function backerKinds(e) {
          return (e.backers || []).map(function (b) { return b[1]; });
        }

        function matches(e) {
          if (anySel(sel.region) && !sel.region[e.region]) return false;
          if (anySel(sel.type) && !sel.type[e.type]) return false;
          if (anySel(sel.conf) && !sel.conf[e.conf]) return false;
          if (!arrHit(sel.sector, e.sectors)) return false;
          if (!arrHit(sel.modality, e.modalities)) return false;
          if (!arrHit(sel.indication, e.indications)) return false;
          if (!arrHit(sel.stage, e.stages)) return false;
          if (!arrHit(sel.backer, backerKinds(e))) return false;
          if (q) {
            var hay = (e.name.en + " " + (e.name.local || "") + " " + (e.thesis || "") + " " +
              (e.summary || "") + " " + (e.country || "") + " " + (e.city || "") + " " +
              (e.notable || []).join(" ") + " " +
              (e.backers || []).map(function (b) { return b[0]; }).join(" ")).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
          }
          return true;
        }
        function card(e) {
          var name = esc(e.name.en) + (e.name.local ? ' <span class="ecard__local">' + esc(e.name.local) + "</span>" : "");
          var loc = [e.city, regionLab(e.region)].filter(Boolean).map(esc).join(" · ");
          var tags = (e.sectors || []).slice(0, 2).map(function (s) {
            return '<span class="tag">' + esc(lab("sectors", s)) + "</span>";
          }).join("");
          var mod = (e.modalities || []).slice(0, 1).map(function (m) {
            return '<span class="tag tag--alt">' + esc(lab("modalities", m)) + "</span>";
          }).join("");
          return '<article class="ecard card" tabindex="0" role="button" data-item data-slug="' + esc(e.id) + '" ' +
            'aria-label="' + esc(e.name.en) + '">' +
            '<div class="ecard__head"><h3 class="ecard__name">' + name + "</h3>" +
              '<span class="dot dot--' + esc(e.conf) + '" title="' + esc(t(CONF[e.conf] || {})) + '"></span></div>' +
            '<div class="ecard__meta"><span class="badge">' + esc(typeLab(e.type)) + "</span>" +
              (loc ? '<span class="ecard__loc">' + loc + "</span>" : "") + "</div>" +
            backerLine(e) +
            (tags || mod ? '<div class="ecard__tags">' + tags + mod + "</div>" : "") +
            "</article>";
        }

        function backerLine(e) {
          var bs = e.backers || [];
          if (!bs.length) return "";
          var shown = bs.slice(0, 2).map(function (b) {
            var rel = lab("backerRels", b[2]);
            return '<span class="backer backer--' + esc(b[1]) + '">' +
              '<span class="material-symbols-rounded" aria-hidden="true">' + esc(BACKER_ICON[b[1]] || "corporate_fare") + "</span>" +
              esc(b[0]) + (rel ? ' <i class="backer__rel">' + esc(rel) + "</i>" : "") + "</span>";
          }).join("");
          var more = bs.length > 2 ? '<span class="backer backer--more">+' + (bs.length - 2) + "</span>" : "";
          return '<div class="ecard__backers">' + shown + more + "</div>";
        }

        // Substring search over a big free-text blob has a precision problem on
        // short queries: "anthropic" matches "philanthropic", burying the one
        // Anthropic-linked fund under nine philanthropy foundations. Rather than
        // tighten the filter and lose recall, rank the obviously-intended hits
        // first — a match on a backer or organization name beats a match buried
        // in a thesis paragraph.
        function relevance(e) {
          var hit = function (s) { return (s || "").toLowerCase().indexOf(q) !== -1; };
          if ((e.backers || []).some(function (b) { return hit(b[0]); })) return 0;
          if (hit(e.name.en) || hit(e.name.local)) return 1;
          if ((e.notable || []).some(hit)) return 2;
          return 3;
        }

        function paint() {
          visible = ents.filter(matches);
          if (q) {
            visible = visible
              .map(function (e, i) { return { e: e, r: relevance(e), i: i }; })
              .sort(function (a, b) { return a.r - b.r || a.i - b.i; })
              .map(function (x) { return x.e; });
          }
          if (visible.length > 900) {
            grid.innerHTML = visible.slice(0, 900).map(card).join("");
          } else {
            grid.innerHTML = visible.map(card).join("");
          }
          emptyEl.hidden = visible.length !== 0;
          paintContext();
          countEl.textContent = num(visible.length) + " " + (visible.length === 1 ? tt("result") : tt("results")) +
            (visible.length > 900 ? " · showing 900" : "");
          [].forEach.call(grid.querySelectorAll(".ecard[data-slug]"), function (c) {
            var slug = c.dataset.slug;
            c.addEventListener("click", function () { openItem(slug); });
            c.addEventListener("keydown", function (ev) {
              if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openItem(slug); }
            });
          });
          syncChips();
        }

        // Searching a COMPANY name already returns its investors — the search
        // index covers `notable`. What it does not do is say *why* those rows
        // matched. This banner names the relationship, which is the actual
        // question behind "is Neko Health in here?".
        function paintContext() {
          var el = document.getElementById("ctxBanner");
          if (!el) return;
          var investors = q && PORTFOLIO[q];
          if (!investors || !investors.length) { el.innerHTML = ""; return; }
          var label = q.replace(/\b\w/g, function (c) { return c.toUpperCase(); });
          var links = investors.slice(0, 10).map(function (e) {
            return '<button class="ctx__link" type="button" data-goto="' + esc(e.id) + '">' +
              esc(e.name.en) + ' <span class="ctx__where">' + esc(regionLab(e.region)) + " · " +
              esc(typeLab(e.type)) + "</span></button>";
          }).join("");
          var more = investors.length > 10 ? " " + esc(tt("portfolioHintMore")) : "";
          el.innerHTML = '<div class="ctx">' +
            '<span class="material-symbols-rounded" aria-hidden="true">alt_route</span>' +
            '<div><p class="ctx__lead"><b>' + esc(label) + "</b> " + esc(tt("portfolioHint")) + more + "</p>" +
            '<div class="ctx__links">' + links + "</div></div></div>";
          [].forEach.call(el.querySelectorAll("[data-goto]"), function (b) {
            b.addEventListener("click", function () { openItem(b.dataset.goto); });
          });
        }

        function syncChips() {
          [].forEach.call(pageEl.querySelectorAll(".fchip"), function (chip) {
            var on = sel[chip.dataset.axis] && sel[chip.dataset.axis][chip.dataset.val];
            chip.classList.toggle("fchip--active", !!on);
            chip.setAttribute("aria-pressed", on ? "true" : "false");
          });
        }

        function findItem(slug) {
          for (var i = 0; i < ents.length; i++) if (ents[i].id === slug) return ents[i];
          return null;
        }

        function row(labelKey, valHtml) {
          if (!valHtml) return "";
          return '<div class="drow"><dt>' + esc(tt(labelKey)) + "</dt><dd>" + valHtml + "</dd></div>";
        }
        function slugList(axis, arr) {
          if (!arr || !arr.length) return "";
          return arr.map(function (s) { return '<span class="tag">' + esc(lab(axis, s)) + "</span>"; }).join("");
        }
        function openItem(slug) {
          var e = findItem(slug); if (!e) return;
          var dlg = L.dialog(), body = document.getElementById("dialogBody");
          var title = esc(e.name.en) + (e.name.local ? ' <span class="dlg__local">' + esc(e.name.local) + "</span>" : "");
          var sub = [typeLab(e.type), [e.city, e.country].filter(Boolean).join(", ")].filter(Boolean).map(esc).join("  ·  ");
          var web = e.website ? '<a href="' + esc(e.website) + '" target="_blank" rel="noopener">' + esc(tt("visit")) +
            ' <span class="material-symbols-rounded" aria-hidden="true">open_in_new</span></a>' : "";

          /* Portfolio companies that have their own profile become links to the
             companies page. The remaining `notable` names stay plain text —
             they are real investments this investor claims, just not profiled
             yet, and hiding them would understate the record. Names already
             shown as links are filtered out so the same company is not listed
             twice under two headings. */
          var linked = (I2C[e.id] || []).map(function (cid) { return CO_BY_ID[cid]; }).filter(Boolean);
          var linkedNames = Object.create(null);
          linked.forEach(function (c) { linkedNames[c.name.en.toLowerCase()] = 1; });
          var portfolioHtml = linked.map(function (c) {
            return '<a class="xlink" href="companies.html#' + esc(c.id) + '" title="' + esc(tt("coOpenCompany")) + '">' +
              esc(c.name.en) +
              '<span class="material-symbols-rounded" aria-hidden="true">arrow_outward</span></a>';
          }).join("");
          var notable = (e.notable || []).filter(function (c) {
            return !linkedNames[String(c).toLowerCase()];
          }).map(function (c) { return '<span class="tag">' + esc(c) + "</span>"; }).join("");
          var prog = "";
          if (e.program) {
            var pr = e.program, parts = [];
            if (pr.invest) parts.push(esc(tt("invest")) + ": " + esc(pr.invest));
            if (pr.equity) parts.push(esc(tt("equity")) + ": " + esc(String(pr.equity)));
            if (pr.lab) parts.push(esc(tt("labSpace")) + ": " + esc(tt("yes")));
            if (pr.url) parts.push('<a href="' + esc(pr.url) + '" target="_blank" rel="noopener">' + esc(tt("apply")) + "</a>");
            if (parts.length) prog = parts.join("<br>");
          }
          var backersHtml = (e.backers || []).map(function (b) {
            return '<span class="backer backer--' + esc(b[1]) + '">' +
              '<span class="material-symbols-rounded" aria-hidden="true">' + esc(BACKER_ICON[b[1]] || "corporate_fare") + "</span>" +
              esc(b[0]) + ' <i class="backer__rel">' + esc(lab("backerKinds", b[1])) +
              (b[2] ? " · " + esc(lab("backerRels", b[2])) : "") + "</i></span>";
          }).join("");

          var meta = row("founded", e.founded ? esc(String(e.founded)) : "") +
            row("status", e.status ? esc(e.status) : "") +
            row("website", web) +
            row("backers", backersHtml) +
            row("stages", slugList("stages", e.stages)) +
            row("checkSize", e.check ? esc(e.check) : "") +
            row("aum", e.aum ? esc(e.aum) : "") +
            row("currentFund", e.fund ? esc(e.fund) : "") +
            row("modalities", slugList("modalities", e.modalities)) +
            row("indications", slugList("indications", e.indications)) +
            row("portfolio", e.portfolio ? esc(String(e.portfolio)) : "") +
            row("coPortfolio", portfolioHtml) +
            row("notable", notable) +
            row("program", prog) +
            row("confidence", '<span class="dot dot--' + esc(e.conf) + '"></span> ' + esc(t(CONF[e.conf] || {})));

          var thesis = e.thesis ? '<p class="dlg__thesis">' + esc(e.thesis) + "</p>" :
            (e.summary ? '<p class="dlg__thesis">' + esc(e.summary) + "</p>" : "");

          var sources = (e.sources || []).length
            ? '<div class="dlg__sources"><h3>' + esc(tt("sources")) + "</h3>" +
              (e.sources || []).map(function (s) {
                return '<div class="src"><a href="' + esc(s.url) + '" target="_blank" rel="noopener" class="src__link">' +
                  esc(s.title || s.url) + ' <span class="material-symbols-rounded" aria-hidden="true">open_in_new</span></a>' +
                  (s.quote ? '<blockquote class="src__quote">' + esc(s.quote) + "</blockquote>" : "") + "</div>";
              }).join("") + "</div>"
            : "";

          body.innerHTML = '<h2 id="dialogTitle" class="dlg__title">' + title + "</h2>" +
            (sub ? '<p class="dlg__sub">' + sub + "</p>" : "") +
            thesis +
            '<dl class="dlg__grid">' + meta + "</dl>" +
            sources;
          if (!dlg.open) dlg.showModal();
          if (location.hash.slice(1) !== slug) history.replaceState(null, "", "#" + slug);
        }

        function navBy(d) {
          var slug = location.hash.slice(1);
          var i = -1;
          for (var k = 0; k < visible.length; k++) if (visible[k].id === slug) { i = k; break; }
          if (i === -1) return;
          openItem(visible[(i + d + visible.length) % visible.length].id);
        }

        /* filter chip clicks (event delegation) */
        function onChip(ev) {
          var chip = ev.target.closest && ev.target.closest(".fchip");
          if (!chip) return;
          var axis = chip.dataset.axis, val = chip.dataset.val;
          if (sel[axis][val]) delete sel[axis][val]; else sel[axis][val] = true;
          paint();
        }
        pageEl.addEventListener("click", onChip);

        var resetBtn = document.getElementById("resetBtn");
        function reset() {
          for (var a in sel) sel[a] = set();
          if (searchEl) searchEl.value = ""; q = "";
          paint();
        }
        if (resetBtn) resetBtn.addEventListener("click", reset);

        var mobBtn = document.getElementById("mobFilterBtn");
        if (mobBtn) mobBtn.addEventListener("click", function () {
          var open = filtersEl.classList.toggle("dir__filters--open");
          mobBtn.setAttribute("aria-expanded", open ? "true" : "false");
        });

        var debounce;
        if (searchEl) searchEl.addEventListener("input", function () {
          var v = this.value.trim().toLowerCase();
          clearTimeout(debounce);
          debounce = setTimeout(function () { q = v; paint(); }, 120);
        });

        var csvBtn = document.getElementById("csvBtn");
        if (csvBtn) csvBtn.addEventListener("click", function () {
          downloadCsv("med-vc-investors.csv",
            ["id", "name", "type", "region", "country", "city", "sectors", "modalities",
             "backers", "backer_kinds", "portfolio_in_directory", "confidence", "website"],
            visible.map(function (e) {
              return [e.id, e.name.en, typeLab(e.type), regionLab(e.region), e.country || "", e.city || "",
                (e.sectors || []).map(function (s) { return lab("sectors", s); }).join("; "),
                (e.modalities || []).map(function (m) { return lab("modalities", m); }).join("; "),
                (e.backers || []).map(function (b) { return b[0]; }).join("; "),
                (e.backers || []).map(function (b) { return b[1]; }).join("; "),
                (I2C[e.id] || []).map(function (cid) {
                  return CO_BY_ID[cid] ? CO_BY_ID[cid].name.en : cid;
                }).join("; "),
                e.conf, e.website || ""];
            }));
        });

        /* dialog: deep link + arrow nav */
        var dlg = L.dialog();
        function onKey(ev) {
          if (!dlg.open) return;
          if (ev.key === "ArrowRight") { ev.preventDefault(); navBy(1); }
          else if (ev.key === "ArrowLeft") { ev.preventDefault(); navBy(-1); }
        }
        document.addEventListener("keydown", onKey);
        function onClose() {
          var slug = location.hash.slice(1);
          if (slug && findItem(slug)) history.replaceState(null, "", location.pathname + location.search);
        }
        dlg.addEventListener("close", onClose);
        function syncHash() {
          var slug = location.hash.slice(1);
          if (slug && findItem(slug)) openItem(slug);
        }
        function onHash() { syncHash(); }
        window.addEventListener("hashchange", onHash);

        teardowns.push(function () {
          pageEl.removeEventListener("click", onChip);
          document.removeEventListener("keydown", onKey);
          dlg.removeEventListener("close", onClose);
          window.removeEventListener("hashchange", onHash);
          clearTimeout(debounce);
        });

        paint();
        syncHash();
      },

      /* ---------------- companies ---------------- */
      companies: function () {
        var cos = COMPANIES;
        var grid = document.getElementById("grid");
        var searchEl = document.getElementById("search");
        var countEl = document.getElementById("resultCount");
        var emptyEl = document.getElementById("empty");
        var filtersEl = document.getElementById("filters");
        var sel = { region: set(), category: set(), status: set(), dev: set(),
                    modality: set(), indication: set() };
        var q = "";
        var visible = [];

        /* Mirror of the directory page's PORTFOLIO index, pointing the other
           way: investor name -> companies here that it backed. It lets someone
           type a fund name on the companies page and get its portfolio, which
           is the question this page exists to answer. */
        var BY_INVESTOR = (function () {
          var idx = Object.create(null);
          cos.forEach(function (c) {
            investorsOf(c).forEach(function (i) {
              var k = String(i.name || "").trim().toLowerCase();
              if (!k) return;
              (idx[k] || (idx[k] = [])).push(c);
            });
          });
          return idx;
        })();

        function matches(c) {
          if (anySel(sel.region) && !sel.region[c.region]) return false;
          if (anySel(sel.status) && !sel.status[c.status || "unknown"]) return false;
          if (anySel(sel.dev) && !sel.dev[(c.dev || "unknown")]) return false;
          if (!arrHit(sel.category, c.sectors)) return false;
          if (!arrHit(sel.modality, c.modalities)) return false;
          if (!arrHit(sel.indication, c.indications)) return false;
          if (q) {
            var hay = (c.name.en + " " + (c.name.local || "") + " " + (c.what || "") + " " +
              (c.summary || "") + " " + (c.city || "") + " " + (c.country || "") + " " +
              (c.lead || "") + " " +
              (c.sectors || []).join(" ") + " " +
              investorsOf(c).map(function (i) { return i.name; }).join(" ")).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
          }
          return true;
        }

        function money(m) { return m ? esc(String(m)) : ""; }

        function card(c) {
          var name = esc(c.name.en) + (c.name.local ? ' <span class="ecard__local">' + esc(c.name.local) + "</span>" : "");
          var loc = [c.city, regionLab(c.region)].filter(Boolean).map(esc).join(" · ");
          var tags = (c.sectors || []).slice(0, 2).map(function (s) {
            return '<span class="tag">' + esc(lab("sectors", s)) + "</span>";
          }).join("");
          var dev = c.dev && c.dev !== "unknown"
            ? '<span class="tag tag--alt">' + esc(lab("devStages", c.dev)) + "</span>" : "";
          var invs = investorsOf(c);
          var invLine = invs.length
            ? '<div class="ecard__backers">' + invs.slice(0, 3).map(function (i) {
                return '<span class="backer backer--' + (i.id ? "linked" : "plain") + '">' +
                  '<span class="material-symbols-rounded" aria-hidden="true">' +
                  (i.id ? "account_balance_wallet" : "help") + "</span>" + esc(i.name) + "</span>";
              }).join("") +
              (invs.length > 3 ? '<span class="backer backer--more">+' + (invs.length - 3) + "</span>" : "") +
              "</div>"
            : "";
          var raised = c.raised ? '<span class="ecard__raised">' + money(c.raised) + "</span>" : "";
          var stat = c.status && c.status !== "private"
            ? '<span class="badge badge--' + esc(c.status) + '">' + esc(lab("companyStatus", c.status)) + "</span>" : "";
          return '<article class="ecard card" tabindex="0" role="button" data-item data-slug="' + esc(c.id) + '" ' +
            'aria-label="' + esc(c.name.en) + '">' +
            '<div class="ecard__head"><h3 class="ecard__name">' + name + "</h3>" +
              '<span class="dot dot--' + esc(c.conf) + '" title="' + esc(t(CONF[c.conf] || {})) + '"></span></div>' +
            '<div class="ecard__meta">' + stat +
              (loc ? '<span class="ecard__loc">' + loc + "</span>" : "") + raised + "</div>" +
            (c.what ? '<p class="ecard__what">' + esc(c.what) + "</p>" : "") +
            invLine +
            (tags || dev ? '<div class="ecard__tags">' + tags + dev + "</div>" : "") +
            "</article>";
        }

        function relevance(c) {
          var hit = function (s) { return (s || "").toLowerCase().indexOf(q) !== -1; };
          if (hit(c.name.en) || hit(c.name.local)) return 0;
          if (investorsOf(c).some(function (i) { return hit(i.name); })) return 1;
          if (hit(c.what)) return 2;
          return 3;
        }

        function paint() {
          visible = cos.filter(matches);
          if (q) {
            visible = visible
              .map(function (c, i) { return { c: c, r: relevance(c), i: i }; })
              .sort(function (a, b) { return a.r - b.r || a.i - b.i; })
              .map(function (x) { return x.c; });
          }
          grid.innerHTML = visible.slice(0, 900).map(card).join("");
          emptyEl.hidden = visible.length !== 0;
          paintContext();
          countEl.textContent = num(visible.length) + " " +
            (visible.length === 1 ? tt("coCount1") : tt("coCount")) +
            (visible.length > 900 ? " · showing 900" : "");
          [].forEach.call(grid.querySelectorAll(".ecard[data-slug]"), function (el) {
            var slug = el.dataset.slug;
            el.addEventListener("click", function () { openItem(slug); });
            el.addEventListener("keydown", function (ev) {
              if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openItem(slug); }
            });
          });
          syncChips();
        }

        function paintContext() {
          var el = document.getElementById("ctxBanner");
          if (!el) return;
          var hits = q && BY_INVESTOR[q];
          if (!hits || !hits.length) { el.innerHTML = ""; return; }
          var label = q.replace(/\b\w/g, function (ch) { return ch.toUpperCase(); });
          var links = hits.slice(0, 10).map(function (c) {
            return '<button class="ctx__link" type="button" data-goto="' + esc(c.id) + '">' +
              esc(c.name.en) + ' <span class="ctx__where">' + esc(regionLab(c.region)) +
              (c.cat ? " · " + esc(lab("sectors", c.cat)) : "") + "</span></button>";
          }).join("");
          el.innerHTML = '<div class="ctx">' +
            '<span class="material-symbols-rounded" aria-hidden="true">alt_route</span>' +
            '<div><p class="ctx__lead"><b>' + esc(label) + "</b> " + esc(tt("coInvestorHint")) +
            (hits.length > 10 ? " " + esc(tt("portfolioHintMore")) : "") + "</p>" +
            '<div class="ctx__links">' + links + "</div></div></div>";
          [].forEach.call(el.querySelectorAll("[data-goto]"), function (b) {
            b.addEventListener("click", function () { openItem(b.dataset.goto); });
          });
        }

        function syncChips() {
          [].forEach.call(pageEl.querySelectorAll(".fchip"), function (chip) {
            var on = sel[chip.dataset.axis] && sel[chip.dataset.axis][chip.dataset.val];
            chip.classList.toggle("fchip--active", !!on);
            chip.setAttribute("aria-pressed", on ? "true" : "false");
          });
        }

        function findItem(slug) { return CO_BY_ID[slug] || null; }

        function row(labelKey, valHtml) {
          if (!valHtml) return "";
          return '<div class="drow"><dt>' + esc(tt(labelKey)) + "</dt><dd>" + valHtml + "</dd></div>";
        }
        function slugList(axis, arr) {
          if (!arr || !arr.length) return "";
          return arr.map(function (s) { return '<span class="tag">' + esc(lab(axis, s)) + "</span>"; }).join("");
        }

        function openItem(slug) {
          var c = findItem(slug); if (!c) return;
          var dlg = L.dialog(), body = document.getElementById("dialogBody");
          var title = esc(c.name.en) + (c.name.local ? ' <span class="dlg__local">' + esc(c.name.local) + "</span>" : "");
          var sub = [c.cat ? lab("sectors", c.cat) : "", [c.city, c.country].filter(Boolean).join(", ")]
            .filter(Boolean).map(esc).join("  ·  ");
          var web = c.website ? '<a href="' + esc(c.website) + '" target="_blank" rel="noopener">' + esc(tt("visit")) +
            ' <span class="material-symbols-rounded" aria-hidden="true">open_in_new</span></a>' : "";

          /* The link back to the investor half. An investor we have profiled
             becomes a deep link into the directory page; one we have not stays
             plain text with a quiet "not in this directory" marker, so the
             difference between "no investor" and "investor not yet catalogued"
             is visible rather than inferred from a missing link. */
          var invs = investorsOf(c);
          var invHtml = invs.length ? invs.map(function (i) {
            var role = i.role && i.role !== "unknown" ? ' <i class="backer__rel">' + esc(i.role) + "</i>" : "";
            if (i.id && ENT_BY_ID[i.id]) {
              return '<a class="xlink" href="directory.html#' + esc(i.id) + '" title="' + esc(tt("coOpenInvestor")) + '">' +
                esc(i.name) + role +
                '<span class="material-symbols-rounded" aria-hidden="true">arrow_outward</span></a>';
            }
            return '<span class="xlink xlink--dead" title="' + esc(tt("coNotListed")) + '">' + esc(i.name) + role + "</span>";
          }).join("") : '<span class="muted">' + esc(tt("coInvestorsNone")) + "</span>";

          var lastRound = c.last
            ? [c.last.stage ? lab("stages", c.last.stage) || c.last.stage : "", c.last.amount, c.last.date]
                .filter(Boolean).map(esc).join(" · ")
            : "";
          var regHtml = (c.reg || []).map(function (rg) {
            return '<span class="tag">' + esc([rg[0], rg[1], rg[3]].filter(Boolean).join(" ")) +
              (rg[2] ? " — " + esc(rg[2]) : "") + "</span>";
          }).join("");
          var exitHtml = c.exit
            ? esc([c.exit.type, c.exit.acquirer, c.exit.value, c.exit.year, c.exit.ticker]
                .filter(Boolean).join(" · "))
            : "";

          var meta = row("founded", c.founded ? esc(String(c.founded)) : "") +
            row("status", c.status ? esc(lab("companyStatus", c.status)) : "") +
            row("website", web) +
            row("coDev", c.dev && c.dev !== "unknown" ? esc(lab("devStages", c.dev)) : "") +
            row("coLead", c.lead ? esc(c.lead) : "") +
            row("modalities", slugList("modalities", c.modalities)) +
            row("indications", slugList("indications", c.indications)) +
            row("coReg", regHtml) +
            row("coRaised", c.raised ? esc(String(c.raised)) : "") +
            row("coVal", c.val ? esc(String(c.val)) + (c.unicorn ? " 🦄" : "") : "") +
            row("coLastRound", lastRound) +
            row("coInvestors", invHtml) +
            row("coExit", exitHtml) +
            row("confidence", '<span class="dot dot--' + esc(c.conf) + '"></span> ' + esc(t(CONF[c.conf] || {})));

          var blurb = c.what ? '<p class="dlg__thesis">' + esc(c.what) + "</p>"
            : (c.summary ? '<p class="dlg__thesis">' + esc(c.summary) + "</p>" : "");

          var sources = (c.sources || []).length
            ? '<div class="dlg__sources"><h3>' + esc(tt("sources")) + "</h3>" +
              (c.sources || []).map(function (s) {
                return '<div class="src"><a href="' + esc(s.url) + '" target="_blank" rel="noopener" class="src__link">' +
                  esc(s.title || s.url) + ' <span class="material-symbols-rounded" aria-hidden="true">open_in_new</span></a>' +
                  (s.quote ? '<blockquote class="src__quote">' + esc(s.quote) + "</blockquote>" : "") + "</div>";
              }).join("") + "</div>"
            : "";

          body.innerHTML = '<h2 id="dialogTitle" class="dlg__title">' + title + "</h2>" +
            (sub ? '<p class="dlg__sub">' + sub + "</p>" : "") +
            blurb + '<dl class="dlg__grid">' + meta + "</dl>" + sources;
          if (!dlg.open) dlg.showModal();
          if (location.hash.slice(1) !== slug) history.replaceState(null, "", "#" + slug);
        }

        function navBy(d) {
          var slug = location.hash.slice(1), i = -1;
          for (var k = 0; k < visible.length; k++) if (visible[k].id === slug) { i = k; break; }
          if (i === -1) return;
          openItem(visible[(i + d + visible.length) % visible.length].id);
        }

        function onChip(ev) {
          var chip = ev.target.closest && ev.target.closest(".fchip");
          if (!chip) return;
          var axis = chip.dataset.axis, val = chip.dataset.val;
          if (sel[axis][val]) delete sel[axis][val]; else sel[axis][val] = true;
          paint();
        }
        pageEl.addEventListener("click", onChip);

        var resetBtn = document.getElementById("resetBtn");
        if (resetBtn) resetBtn.addEventListener("click", function () {
          for (var a in sel) sel[a] = set();
          if (searchEl) searchEl.value = ""; q = "";
          paint();
        });

        var mobBtn = document.getElementById("mobFilterBtn");
        if (mobBtn) mobBtn.addEventListener("click", function () {
          var open = filtersEl.classList.toggle("dir__filters--open");
          mobBtn.setAttribute("aria-expanded", open ? "true" : "false");
        });

        var debounce;
        if (searchEl) searchEl.addEventListener("input", function () {
          var v = this.value.trim().toLowerCase();
          clearTimeout(debounce);
          debounce = setTimeout(function () { q = v; paint(); }, 120);
        });

        var csvBtn = document.getElementById("csvBtn");
        if (csvBtn) csvBtn.addEventListener("click", function () {
          downloadCsv("med-vc-companies.csv",
            ["id", "name", "category", "region", "country", "city", "founded", "status",
             "development_stage", "total_raised", "valuation", "investors",
             "investors_in_directory", "confidence", "website"],
            visible.map(function (c) {
              var iv = investorsOf(c);
              return [c.id, c.name.en, c.cat ? lab("sectors", c.cat) : "", regionLab(c.region),
                c.country || "", c.city || "", c.founded || "",
                c.status ? lab("companyStatus", c.status) : "",
                c.dev ? lab("devStages", c.dev) : "", c.raised || "", c.val || "",
                iv.map(function (i) { return i.name; }).join("; "),
                iv.filter(function (i) { return i.id; }).map(function (i) { return i.id; }).join("; "),
                c.conf, c.website || ""];
            }));
        });

        var dlg = L.dialog();
        function onKey(ev) {
          if (!dlg.open) return;
          if (ev.key === "ArrowRight") { ev.preventDefault(); navBy(1); }
          else if (ev.key === "ArrowLeft") { ev.preventDefault(); navBy(-1); }
        }
        document.addEventListener("keydown", onKey);
        function onClose() {
          var slug = location.hash.slice(1);
          if (slug && findItem(slug)) history.replaceState(null, "", location.pathname + location.search);
        }
        dlg.addEventListener("close", onClose);
        function syncHash() {
          var slug = location.hash.slice(1);
          if (slug && findItem(slug)) openItem(slug);
        }
        window.addEventListener("hashchange", syncHash);

        teardowns.push(function () {
          pageEl.removeEventListener("click", onChip);
          document.removeEventListener("keydown", onKey);
          dlg.removeEventListener("close", onClose);
          window.removeEventListener("hashchange", syncHash);
          clearTimeout(debounce);
        });

        paint();
        syncHash();
      }
    };

    /* =====================================================================
       render + language reactivity
       ===================================================================== */
    function render() {
      teardowns.forEach(function (fn) { try { fn(); } catch (e) {} });
      teardowns = [];
      var p = L.currentPage();
      if (!p) { pageEl.innerHTML = '<p class="empty">No page data.</p>'; return; }
      var fn = RENDERERS[p.layout] || RENDERERS.hub;
      pageEl.className = "page page--" + p.layout;
      pageEl.innerHTML = fn(p);
      var w = WIRE[p.layout];
      if (w) w(p);
    }

    L.onLang(render);
    render();
  }

  boot();
})();
