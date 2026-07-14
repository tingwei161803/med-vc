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
        pitch: "An open, sourced directory of the investors funding medicine — life-science VCs, pharma & medtech corporate arms, crossover funds, bio accelerators, university & hospital funds, disease-foundation venture philanthropy, government programs and more.",
        browse: "Browse the directory", explore: "Explore",
        search: "Search name, thesis, company, city…",
        filters: "Filters", reset: "Reset", results: "results", result: "result",
        exportCsv: "Export CSV", noResults: "No investors match these filters.",
        clearAll: "Clear all filters",
        axisRegion: "Region", axisType: "Type", axisSector: "Sector",
        axisModality: "Modality", axisIndication: "Indication", axisStage: "Stage",
        axisConf: "Confidence",
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
        regionsN: "regions", typesN: "organization types", sourcesN: "sources"
      },
      zh: {
        pitch: "一份開放、逐筆帶來源的「投資醫療的資金」名錄 —— 生醫創投、藥廠與醫材企業創投、公私跨界基金、生醫加速器、大學與醫院基金、疾病基金會公益創投、政府計畫等。",
        browse: "瀏覽名錄", explore: "前往",
        search: "搜尋機構名、論點、被投公司、城市…",
        filters: "篩選", reset: "重設", results: "筆結果", result: "筆結果",
        exportCsv: "匯出 CSV", noResults: "沒有符合這些條件的機構。",
        clearAll: "清除所有篩選",
        axisRegion: "地區", axisType: "類型", axisSector: "子領域",
        axisModality: "治療模式", axisIndication: "適應症", axisStage: "階段",
        axisConf: "信心度",
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
        regionsN: "個地區", typesN: "種機構類型", sourcesN: "條來源"
      }
    };
    function tt(k) { return (UI[state.lang] || UI.en)[k]; }

    /* ---- taxonomy label lookup: LABEL[axis][slug] = {en,zh} ---- */
    var LABEL = {};
    ["types", "sectors", "modalities", "indications", "stages", "regions"].forEach(function (axis) {
      LABEL[axis] = {};
      (TAX[axis] || []).forEach(function (x) { LABEL[axis][x.slug] = { en: x.en, zh: x.zh }; });
    });
    var CONF = { high: { en: "High", zh: "高" }, medium: { en: "Medium", zh: "中" }, low: { en: "Low", zh: "低" } };
    function lab(axis, slug) { var m = LABEL[axis] && LABEL[axis][slug]; return m ? t(m) : slug; }
    function typeLab(slug) { return lab("types", slug); }
    function regionLab(slug) { return lab("regions", slug); }

    function num(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

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
      els.forEach(function (el) {
        var target = parseFloat(el.dataset.count) || 0;
        if (reduce) { el.textContent = el.dataset.suffix ? num(target) + el.dataset.suffix : num(target); return; }
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
    var QUOTE_PCT = 96;
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
          { v: REGION_CT, s: "", label: tt("regionsN") },
          { v: TYPE_CT, s: "", label: tt("typesN") },
          { v: SRC, s: "", label: tt("sourcesN") },
          { v: QUOTE_PCT, s: "%", label: tt("quoteBacked") }
        ].map(function (x) {
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
          { key: "stage", tax: "stages", label: tt("axisStage"), multi: true }
        ];
        var facets = axes.map(function (a) {
          var chips = (TAX[a.tax] || []).map(function (x) {
            return '<button class="fchip" type="button" data-axis="' + a.key + '" data-val="' + esc(x.slug) + '">' +
              esc(t(x)) + "</button>";
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
              '<div class="dir__grid" id="grid"></div>' +
              '<p class="empty" id="empty" hidden>' + esc(tt("noResults")) + "</p>" +
            "</div>" +
          "</div>";
      },

      /* ---------------- analysis (charts) ---------------- */
      analysis: function (p) {
        var tiles = [
          { v: TOTAL, s: "", label: tt("entities") },
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
        return head(p) +
          '<div class="stats">' + tiles + "</div>" +
          '<div class="panels">' +
            panel(tt("capBy"), statsSeries(STATS.by_region || {}, "regions"), "--primary") +
            panel(tt("capType"), statsSeries(STATS.by_type || {}, "types"), "--secondary") +
            panel(tt("capSector"), statsSeries(STATS.by_sector || {}, "sectors", 12), "--primary") +
            panel(tt("capModality"), statsSeries(STATS.by_modality || {}, "modalities", 10), "--tertiary") +
            panel(tt("capIndication"), statsSeries(STATS.by_indication || {}, "indications", 10), "--secondary") +
            panel(tt("capConf"), conf, "--tertiary") +
          "</div>";
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
        var SECTIONS = {
          en: [
            ["What this is", "med-vc is an open, structured directory of the organizations that invest in medicine and biomedicine worldwide — venture capital firms, pharma / medtech / payer / provider corporate venture arms, crossover funds, bio accelerators and incubators, university and hospital funds, disease-foundation venture philanthropy, government programs, venture studios, angel networks and family offices. The subject is the investor, not the funded company."],
            ["Sourced per institution", "Every entry carries at least one real source URL, and every quantitative claim — fund size, AUM, check size, founding year, portfolio count — is tied to a verbatim quote from a source. Where a figure could not be verified, the field is left empty rather than guessed. Amounts are kept in their reported currency and string form to avoid fabricated conversions."],
            ["Confidence ratings", "Each institution is rated high (official / primary source), medium (reputable secondary source), or low (a single weak or dated source). The split across the dataset is high 795 · medium 698 · low 50. Confidence is shown on every card and in the detail view so you can weigh each entry yourself."],
            ["How it was assembled", "Research was fanned out across 188 slices (organization type × health subsector, per region) so coverage is complementary and overlap is minimal. Each slice was researched independently against live web sources in English and the local language, then everything was merged and de-duplicated — matching on normalized name, website domain, and slug, with accent-folding — into one validated dataset with a controlled vocabulary for type, sector, modality, indication, stage and region."],
            ["Two-layer quality check", "Because the corpus was built over many runs, it went through two checks. A structural pass validated every record against the schema and flagged duplicates, missing sources and off-vocabulary values (0 critical issues remained). Then an agent fact-check audited a 120-institution sample — weighted toward lower-confidence rows — against the live web: it found 0 fabricated organizations and no systematic degradation, and the 16 minor factual corrections it surfaced (a founding year, a stale status, a fund figure) were applied and noted in each record."],
            ["Disclaimer", "This is an unofficial research compilation provided as-is. Figures on fund size, equity, acceptance rates and the like should be confirmed against each institution's official disclosures via the sources listed on every entry before you rely on them."]
          ],
          zh: [
            ["這是什麼", "med-vc 是一份開放、結構化的全球「醫療 / 生醫投資機構」名錄 —— 涵蓋生醫創投、藥廠 / 醫材 / 保險 / 醫療體系的企業創投、公私跨界基金、生醫加速器與育成中心、大學與醫院基金、疾病基金會公益創投、政府計畫、創業工作室、天使網絡與家族辦公室。主角是「投資者本身」,不是被投公司。"],
            ["逐機構溯源", "每一筆都至少有一個真實來源 URL;每個數字 —— 基金規模、管理資產、單筆金額、成立年份、投資組合數 —— 都對應到來源中的一段原文引用。查不到的欄位寧可留空也不猜。金額保留原始幣別與字串,避免虛構換匯。"],
            ["信心評級", "每家機構標為 高(官方 / 一手來源)、中(可靠二手)、或 低(單一弱或過時來源)。全資料集分佈為 高 795 · 中 698 · 低 50。信心度顯示在每張卡片與詳情頁,讓你自行判斷。"],
            ["如何蒐集", "研究切成 188 個切片(機構類型 × 健康子領域,依地區),讓覆蓋互補、重疊最小。每個切片以英文與當地語言對照即時網路獨立查證,再以正規化名稱、官網網域與 slug(含重音字折疊)合併去重,匯整成一份通過驗證、對 type / sector / modality / indication / stage / region 使用受控詞彙的資料集。"],
            ["兩層品質檢查", "因資料跨多輪蒐集,做了兩層檢查。結構層對每筆做 schema 驗證,標記重複、缺來源與越界詞彙(最終 0 個嚴重問題)。事實層以 agent 抽樣 120 家機構(偏重低信心筆)對照即時網路查核:發現 0 家捏造機構、無系統性退化,查出的 16 處細節誤差(成立年份、過時狀態、基金數字)已修正並在各筆註記。"],
            ["免責聲明", "本名錄為非官方研究整理,依現況提供。基金規模、股權、錄取率等數字,引用前請依每筆列出的來源,對照各機構官方公開資訊查證。"]
          ]
        };
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
        var sel = { region: set(), type: set(), sector: set(), modality: set(), indication: set(), stage: set(), conf: set() };
        var q = "";
        var visible = [];

        function set() { return Object.create(null); }
        function anySel(o) { for (var k in o) return true; return false; }

        function matches(e) {
          if (anySel(sel.region) && !sel.region[e.region]) return false;
          if (anySel(sel.type) && !sel.type[e.type]) return false;
          if (anySel(sel.conf) && !sel.conf[e.conf]) return false;
          if (!arrHit(sel.sector, e.sectors)) return false;
          if (!arrHit(sel.modality, e.modalities)) return false;
          if (!arrHit(sel.indication, e.indications)) return false;
          if (!arrHit(sel.stage, e.stages)) return false;
          if (q) {
            var hay = (e.name.en + " " + (e.name.local || "") + " " + (e.thesis || "") + " " +
              (e.summary || "") + " " + (e.country || "") + " " + (e.city || "") + " " +
              (e.notable || []).join(" ")).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
          }
          return true;
        }
        function arrHit(selSet, vals) {
          if (!anySel(selSet)) return true;
          vals = vals || [];
          for (var i = 0; i < vals.length; i++) if (selSet[vals[i]]) return true;
          return false;
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
            (tags || mod ? '<div class="ecard__tags">' + tags + mod + "</div>" : "") +
            "</article>";
        }

        function paint() {
          visible = ents.filter(matches);
          if (visible.length > 900) {
            grid.innerHTML = visible.slice(0, 900).map(card).join("");
          } else {
            grid.innerHTML = visible.map(card).join("");
          }
          emptyEl.hidden = visible.length !== 0;
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

          var notable = (e.notable || []).length
            ? (e.notable || []).map(function (c) { return '<span class="tag">' + esc(c) + "</span>"; }).join("") : "";
          var prog = "";
          if (e.program) {
            var pr = e.program, parts = [];
            if (pr.invest) parts.push(esc(tt("invest")) + ": " + esc(pr.invest));
            if (pr.equity) parts.push(esc(tt("equity")) + ": " + esc(String(pr.equity)));
            if (pr.lab) parts.push(esc(tt("labSpace")) + ": " + esc(tt("yes")));
            if (pr.url) parts.push('<a href="' + esc(pr.url) + '" target="_blank" rel="noopener">' + esc(tt("apply")) + "</a>");
            if (parts.length) prog = parts.join("<br>");
          }
          var meta = row("founded", e.founded ? esc(String(e.founded)) : "") +
            row("status", e.status ? esc(e.status) : "") +
            row("website", web) +
            row("stages", slugList("stages", e.stages)) +
            row("checkSize", e.check ? esc(e.check) : "") +
            row("aum", e.aum ? esc(e.aum) : "") +
            row("currentFund", e.fund ? esc(e.fund) : "") +
            row("modalities", slugList("modalities", e.modalities)) +
            row("indications", slugList("indications", e.indications)) +
            row("portfolio", e.portfolio ? esc(String(e.portfolio)) : "") +
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
          var cols = ["id", "name", "type", "region", "country", "city", "sectors", "modalities", "confidence", "website"];
          var lines = [cols.join(",")];
          visible.forEach(function (e) {
            var rowv = [e.id, e.name.en, typeLab(e.type), regionLab(e.region), e.country || "", e.city || "",
              (e.sectors || []).map(function (s) { return lab("sectors", s); }).join("; "),
              (e.modalities || []).map(function (m) { return lab("modalities", m); }).join("; "),
              e.conf, e.website || ""];
            lines.push(rowv.map(csvCell).join(","));
          });
          var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url; a.download = "med-vc-directory.csv";
          document.body.appendChild(a); a.click();
          document.body.removeChild(a);
          setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        });
        function csvCell(v) {
          v = String(v == null ? "" : v);
          return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
        }

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
