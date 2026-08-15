# med-vc

> 全球**醫療/生醫創投名錄資料庫** — 把美國、歐洲、大中華、日本、台灣、南韓、以色列、加拿大、
> 印度、東南亞、澳紐與其他地區的生醫 VC、藥廠/醫材/保險 CVC、crossover 基金、生醫加速器/育成、
> 大學/醫院基金、疾病基金會創投、政府計畫、公司創建工作室、天使網絡、家族辦公室
> 全面整理成**結構化、可篩選、每筆帶來源佐證**的資料集。
>
> An open, global directory of medical / biomedical / healthcare venture investors — life-science
> VCs, pharma & medtech & payer CVCs, crossover funds, bio accelerators & incubators,
> university/hospital funds, disease-foundation venture philanthropy, government programs,
> venture studios, angel networks and family offices — fully structured, filterable,
> and **sourced per entry**.
>
> 姊妹專案：[`all-vc-info`](https://all-vc-info.peteraim.com/)（跨產業版）。本專案為醫療/生醫特化版。

---

## 🌐 線上互動圖鑑

**<https://med-vc.peteraim.com/>**

兩個互通的名錄：**投資機構**與**被投公司**。
多軸篩選（地區 × 類型 × 健康子領域 × 治療模式 × 適應症 × 階段 × 背後金主）· 全文搜尋 ·
中英雙語切換 · 深淺色模式 · 點卡片看完整詳情與**來源 quote 佐證** · 分析圖表儀表板 · CSV 匯出。
純靜態 HTML/CSS/JS（Material Design 3、零 build），由 `docs/` 經 GitHub Pages 部署。

> 網站資料層由 `uv run scripts/build_site.py` 從 `data/all-entities.json` + `data/all-companies.json` + `data/links.json` 產生。

---

## 收錄範圍

| 維度 | 內容 |
| --- | --- |
| **12 地區** | 台灣 · 美國 · 歐洲 · 大中華 · 日本 · 南韓 · 以色列 · 加拿大 · 印度 · 東南亞 · 澳紐 · 其他 |
| **15 類機構** | 生醫 VC · CVC · crossover 基金 · growth equity · Micro-VC · 創業工作室 · 加速器 · 育成/lab space · 大學/醫院基金 · 疾病基金會創投 · 政府計畫 · 天使網絡 · 天使 syndicate · 家族辦公室 · 股權群募 |
| **20 健康子領域** | 新藥 · 醫材 · 診斷 · 工具 · 數位健康 · 醫療服務 · AI 製藥 · 基因體 · 合成生物 · 細胞基因治療 · 長壽 · 女性健康 · 心理健康 … |
| **生醫特有維度** | modality（小分子/抗體/細胞/基因/RNA…）× indication（腫瘤/神經/罕病…）× 公司創建模式 × 公私跨界 |
| **16 類背後金主** | 大型科技公司 · 前沿 AI 實驗室 · 藥廠 · 醫材大廠 · 保險/支付方 · 診斷工具廠 · 綜合企業 · 金融機構 · 電信 · 零售消費 · 大學 · 醫院體系 · 政府/主權 · 基金會 · 家族辦公室 · 其他 |
| **每筆面向** | 身份 / 資本 / **背後金主** / 投資策略 / 生醫焦點 / 加速器專屬 / 戰績 / 團隊 / 申請方式 / 來源佐證 |

每筆資料都附 `sources[]`（真實 URL + 佐證 `quote`）與 `confidence` 信心評級。

### 公司名錄與雙向連結

本專案有**兩半**：`entity`（投資機構，誰出錢）與 `company`（被投公司，錢進了哪裡），
schema 分離但**共用同一套 taxonomy**——公司的 `category` 用的就是機構的 `sector_focus` 詞彙，
`modalities` / `indications` 也完全相同。因此「篩選 digital-health 的機構」與「篩選 digital-health 的公司」
是同一個動作，兩邊可以無縫互跳。

連結不是手寫的，是 `build_companies.py` 在 build 階段**解析名稱**產生的，而且雙向都認：

| 方向 | 來源 | 意義 |
| --- | --- | --- |
| 公司 → 機構 | `funding.investors[].name` | 公司說誰投了它 |
| 機構 → 公司 | `track_record.notable_investments[].company` | 機構說它投了誰 |

兩邊都主張的邊標記 `via: "both"`。這也解釋了公司半邊為何能快速長出來：
投資機構那半在還沒研究任何一家公司之前，就已經帶著 1,600+ 筆投資紀錄、1,400+ 個不重複公司名。

解析器**寧缺勿錯**：只在唯一命中時建立連結。`"OrbiMed"` 同時是美/以/印/中四筆機構的名稱，
所以會用公司所在地區消歧（美國公司 → `us-orbimed`、以色列公司 → `il-orbimed`）；
真的無法消歧就留空，寫進 `reports/links.json` 當下一輪的待辦。

CJK 名稱有兩個特別處理：正規化過程會保留假名與諺文（少了這步，`"한미약품"` 會變成空字串），
而**中文繁簡一律折疊成簡體**——方向不能反，因為繁→簡是多對一、確定性的，簡→繁要猜
（`台杉投資` 反向會變成 `臺杉投資`）。

這份報表有兩個副作用，兩個都有用：
- **未解析的名稱是投資機構半邊的缺口偵測器**——公司點名了某家投資人而名錄裡沒有，那多半是名錄漏了。
- **撞名是重複紀錄偵測器**——同名同地區幾乎都是同一家被建了兩次（繁簡折疊上線後尤其明顯），
  同名不同地區才是合法的區域分支。

### 背後金主（`backing.backers[]`）

回答「**這家基金背後是誰的錢**」——把 Alphabet、Microsoft、NVIDIA、OpenAI、Novartis、Temasek 這類母公司／基石 LP
從機構名稱與描述裡抽成結構化欄位，可直接篩選。每列帶：

| 欄位 | 說明 |
| --- | --- |
| `name` | 金主機構名 |
| `kind` | 金主類型（見上表 16 類，受控詞彙） |
| `relationship` | 出資關係：全資創投部門 / 母公司資產負債表 / **發起管理方（資金來自外部 LP）** / 基石 LP / 主要 LP / 合資 / 分拆 / 關聯計畫 |
| `evidence` | `verified`（有來源直述）或 `inferred`（由名稱或描述推得） |

推論層由 `uv run scripts/backfill_backing.py` 產生，輸出到 `data/backing.json`
（**獨立 overlay，不寫進 `_raw/`**），再由 `build.py` 在 merge 階段套回每筆資料。
`_raw/` 內由研究者寫入的 `backing` 一律優先於推論結果。

推論分三層，後一層只在前面都沒抓到時才跑：

1. **名稱比對** — 機構名／別名含知名企業字典中的組織（`Sony Innovation Fund` → Sony）。
   企業創投幾乎都以母公司命名，精確度很高。
2. **句式比對** — 描述中出現關係句式（`venture arm of X`、`backed by X`、`anchored by X`），
   且 X 在字典內才採用；論點裡單純提到 Google 不算數。
3. **非字典母公司** — 母公司真實存在但不是知名企業（Kasikornbank、Sinar Mas Land、Zydus Lifesciences）。
   此層直接取描述中的組織名，不比對字典；之所以安全，是因為它**只在該筆自己的 tag 已經指明金主類型時才啟用**
   （`payer-cvc` → 保險支付方、`provider-cvc` → 醫院體系…），所以誤抓最多寫錯名字，不會生出錯誤的分類。
   描述沒寫的話，退回從基金名稱推導母公司。

> 這層刻意保守：仍有約 100 家 CVC 沒有金主紀錄，它們列在 `reports/qa.json` 的
> `cvc-without-backer` 當研究待辦，而不是用猜的填滿。

---

## 怎麼用這份資料

- 投資機構在 `data/<region>/entities.json`，全球合併在 `data/all-entities.json`。
- 公司在 `data/companies/_raw/*.json`，合併後在 `data/all-companies.json`，連結圖在 `data/links.json`。
- 欄位定義見 [`schema/entity.schema.json`](schema/entity.schema.json) 與 [`schema/company.schema.json`](schema/company.schema.json)，受控詞彙見 [`data/taxonomy.json`](data/taxonomy.json)。
- 整體架構、蒐集方法論、切片計畫、去重規則、名稱解析器見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

```bash
# 重建合併資料 + 驗證 + 統計（全程 uv）
uv run scripts/build.py
cat data/stats.json          # 各維度數量
cat reports/validation.md    # schema 違規 / 資料品質

# 重跑背後金主推論 overlay，然後再 build 一次讓它套進資料
uv run scripts/backfill_backing.py            # 寫 data/backing.json
uv run scripts/backfill_backing.py --dry-run  # 只看會抓到什麼，不寫檔
uv run scripts/build.py

# 公司半邊 + 兩半之間的連結圖
uv run scripts/build_companies.py
cat data/company-stats.json  # 公司統計 + 連結覆蓋率
cat reports/links.json       # 未解析的名稱 = 下一輪待辦

# 資料完整性 QA（兩半共用：重複 / 來源 / 詞彙 / 薄檔 / 幻覺字樣 / 金主詞彙 / 兩半同名）
uv run scripts/qa_check.py
cat reports/qa.json          # 完整問題清單

# 重建網站資料層
uv run scripts/build_site.py
```

> 順序有意義：`backfill_backing.py` 讀的是 **build 後**的 `data/all-entities.json`（要有正式 id），
> 而它的產物又要**再 build 一次**才會併回每筆資料；`build_companies.py` 的名稱解析器同樣要拿
> **最新的** `all-entities.json` 當索引，所以排在 `build.py` 之後、`build_site.py` 之前。
> `data/<region>/entities.json`、`data/all-entities.json`、`data/all-companies.json`、
> `data/links.json` 全都是衍生產物，直接手改會在下次 build 被覆蓋。

---

## 資料狀態 — ✅ 第一輪完成 + 已查核

**1,543 筆機構 · 12 區 · 188 切片全數完成 · 0 schema 違規**（信心度:high 795 / medium 698 / low 50）。
共 **4,647 條來源**（96% 帶原文 quote），每筆機構 100% 至少一個來源 URL。

| 地區 | 筆數 | 地區 | 筆數 |
| --- | ---: | --- | ---: |
| 🇺🇸 美國 united-states | 429 | 🇰🇷 南韓 south-korea | 78 |
| 🇪🇺 歐洲 europe | 267 | 🇮🇳 印度 india | 77 |
| 🇨🇳 大中華 greater-china | 156 | 🇮🇱 以色列 israel | 74 |
| 🇯🇵 日本 japan | 103 | 🇦🇺 澳紐 australia-nz | 69 |
| 🇸🇬 東南亞 southeast-asia | 92 | 🇹🇼 台灣 taiwan | 60 |
| 🇨🇦 加拿大 canada | 80 | 🌍 其他 rest-of-world | 58 |

**依類型**:VC 499 · CVC 254 · 政府計畫 135 · 育成 119 · 大學/醫院基金 105 · growth-equity 88 ·
加速器 79 · crossover 基金 49 · 疾病基金會創投 47 · 家族辦公室 46 · 創業工作室 43 · 天使網絡 36 ·
Micro-VC 33 · 天使 syndicate 9 · 股權群募 1

**熱門健康子領域**:新藥 976 · 醫材 664 · 數位健康 605 · 診斷 475 · 綜合健康 322 · 醫療服務 312 ·
生科工具 226 · 醫療 IT 135 · AI 製藥 119 · 細胞基因治療 95

> 蒐集用大量 opus/sonnet agent 分切片平行查證(每切片一個 agent、各寫自己的 `_raw/` 檔、`build.py` 去重合併)。
> 因跨越多次額度視窗(session/weekly)與 API 過載,分批續跑完成,agent 產出只進不退。

### 資料品質檢查(兩層)

因蒐集過程中斷多次,完成後做了兩層 QA:

- **Layer 1 — 結構完整性**(`uv run scripts/qa_check.py`):JSON 完整、schema、來源 URL 覆蓋、跨區重複、
  受控詞彙、薄檔偵測。結果 **0 critical**(修掉 11 組重音字/同 id 未合併的重複 + 6 個放錯欄位的 slug)。
- **Layer 2 — 事實查核**(12 個 sonnet agent 抽樣 120 筆對照即時網路):**0 筆捏造機構、無系統性覆寫退化**;
  16 筆(13%)有可修正的細節誤差(成立年份/狀態/基金規模/總部等),已全部修正並在 `verification_notes` 標註;
  1 筆(Merck PMatX 電子業孵化器)非生醫,已移除。

---

## 免責

非官方整理，僅供研究參考。金額 / 股權 / 錄取率等數字以各機構官方公開資料為準，引用前請依各筆 `sources` 自行查證。
資料來源版權歸原出處；本 repo 的程式碼採 MIT。
