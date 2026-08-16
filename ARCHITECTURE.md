# 資料架構與蒐集方法論 / Data Architecture & Methodology

> `med-vc` 是一份**全球醫療/生醫創投名錄資料庫**。主角是「投資機構本身」（不是被投公司），
> 收錄範圍限定**醫療、生技、健康**領域的投資者：生醫 VC、藥廠/醫材/保險 CVC、crossover 基金、
> 生醫加速器/育成、大學/醫院基金、疾病基金會創投、政府計畫、公司創建工作室、天使、家族辦公室。
> 橫跨 12 個地區、15 種機構類型，每筆資料都帶**來源與佐證**（`sources[]` + `quote`）與**信心評級**。
>
> 方法論承襲姊妹專案 [`all-vc-info`](../all-vc-info/)，並針對生醫領域特化。

---

## 1. 設計原則

| 原則 | 做法 |
| --- | --- |
| **醫療 nexus 必要** | 每筆機構都要有可查證的醫療/生醫連結：機構本身是健康專注，或（綜合型機構）有專責健康團隊/基金/≥3 筆健康 portfolio。 |
| **逐機構溯源** | 每個 entity 至少 1 個真實 `sources` URL；每個數字（基金規模 / check size / AUM…）都要有 `quote` 佐證，查不到就省略，**不猜**。 |
| **誠實標示信心** | `confidence`: `high`（官方/一手）/ `medium`（可靠二手）/ `low`（單一弱來源或推估）。 |
| **原文金額不硬換匯** | 金額用 `{ raw, usd, currency }`，`raw` 保留原幣別字串（如 `NT$50億`、`¥100億`），避免 agent 亂換匯造假。 |
| **平行寫入零衝突** | 每個 agent 只寫自己的 `_raw/<segment>.json`，完全隔離 → 事後用 `build.py` 去重合併。 |
| **受控詞彙** | `type / stage / sector / modality / indication / region / status / confidence` 一律用 `data/taxonomy.json` 的 slug，保證可篩選。 |

---

## 2. 目錄結構

本專案有**兩半**：投資機構（entity）與被投公司（company）。兩者 schema 分離、pipeline 分離，
靠一張在 build 階段解析出來的連結表互指。

```
med-vc/
├── schema/entity.schema.json     # 一個「投資機構」的 JSON Schema（欄位定義 + 型別）
├── schema/company.schema.json    # 一家「醫療新創/公司」的 JSON Schema
├── data/
│   ├── taxonomy.json             # 受控詞彙：type / stage / sector / modality / indication / region…
│   ├── regions.json              # 12 地區 metadata（生醫聚落 / 語言 / 權威來源站）
│   ├── segments.json             # 研究切片計畫（模板 × 地區 + 錨點範例）
│   ├── link_aliases.json         # 連結解析器的人工別名表（只放自動化不該自己決定的案例）
│   ├── <region>/                 # ── 投資機構半邊 ──
│   │   ├── _raw/<segment>.json   # ← agent 原始產出，一個切片一檔（永不衝突）
│   │   └── entities.json         # ← build.py 去重合併 + 驗 schema 後的結果
│   ├── backing.json              # ← 背後金主 enrichment overlay（id → backers[]）
│   ├── all-entities.json         # 全球合併（build.py 產生）
│   ├── stats.json                # 各維度統計（build.py 產生）
│   ├── companies/_raw/*.json     # ── 公司半邊 ── agent 原始產出，一個切片一檔
│   ├── all-companies.json        # 公司合併（build_companies.py 產生）
│   ├── links.json                # 兩半之間的連結圖（build_companies.py 產生）
│   └── company-stats.json        # 公司統計（build_companies.py 產生）
├── scripts/build.py              # 合併 / 去重 / 套 overlay / 驗證 / 統計（uv run）
├── scripts/backfill_backing.py   # 由名稱與描述推論母公司 / 金主，產生 backing.json
├── scripts/build_companies.py    # 公司合併 + 名稱解析 + 產生連結圖
├── scripts/build_site.py         # 產生 docs/data/data.js 網站資料層
├── scripts/qa_check.py           # 兩半共用的資料健康報告
├── reports/validation.md         # schema 違規 + 資料品質報告（build.py 產生）
└── reports/links.json            # 未解析的名稱 = 下一輪的待辦（build_companies.py 產生）
```

**衍生產物警告**：`<region>/entities.json`、`all-entities.json`、`stats.json`、
`all-companies.json`、`links.json`、`company-stats.json`、`docs/data/data.js`
全都由 build 腳本從 `_raw/` 重新產生。手動編輯這些檔案會在下次 build 時**被無聲覆蓋**。
要改資料就改 `_raw/`；要加跨筆的衍生欄位就走 `backing.json` 這種 overlay 模式。

12 個地區：`taiwan · united-states · europe · greater-china · japan · south-korea · israel · canada · india · southeast-asia · australia-nz · rest-of-world`

---

## 3. 資料模型（entity）

完整定義見 [`schema/entity.schema.json`](schema/entity.schema.json)。維度概覽：

- **身份**：`name{en,local}` · `type` · `subtypes` · `founded_year` · `status` · `region` · `country` · `hq_city` · `offices` · `website` · `links`
- **資本**（VC/CVC/crossover/growth）：`capital.aum` · `capital.current_fund` · `capital.funds[]`
- **策略**：`strategy.stages` · `check_size` · `ownership_target_pct` · `geo_focus` · `sector_focus`（健康子領域）· `thesis`
- **生醫特有**：`lifesci.modalities`（小分子/抗體/細胞/基因治療/RNA…）· `lifesci.indications`（腫瘤/神經/罕病…）· `company_creation`（Flagship 式公司創建）· `invests_public_markets`（crossover）· `science_platform_notes`
- **加速器/育成專屬**：`program.{length_weeks, cohort_size, equity_taken_pct, investment, lab_space, demo_day, application_url, acceptance_rate, …}`
- **背後金主**：`backing.backers[]{name, kind, relationship, note, evidence}` —— 回答「這是誰的錢」。`kind` 16 類受控詞彙（big-tech / ai-lab / pharma / medtech / payer-insurer / government / university / foundation…），`relationship` 7 種出資關係（wholly-owned-cvc / balance-sheet-fund / anchor-lp / major-lp / joint-venture / spinout / affiliated-program），`evidence` 區分 `verified`（來源直述）與 `inferred`（由名稱或描述推得）
- **戰績**：`track_record.{portfolio_count, notable_investments[], exits[], co_investors[]}`（outcome 含 FDA-approved）
- **人 / 申請**：`people[]`（含 `background`：MD/PhD、藥廠出身等科學履歷）· `team_size` · `application.{how_to_apply, accepts_cold_inbound, contact}`
- **佐證 meta**：`sources[]{url,title,publisher,accessed,supports,quote}` · `confidence` · `verification_notes` · `last_updated` · `researched_by`

必填：`id · name · type · region · country · sources · confidence · last_updated`。其餘可選——查不到就省略，不要塞假值。

相對 `all-vc-info` 的醫療特化：

1. **新增 3 種機構類型**：`crossover-fund`（公私跨界，生技特有）、`venture-philanthropy`（疾病基金會創投）、`university-hospital-fund`（大學/醫院創投臂）。
2. **兩個新維度**：`modalities`（治療模式）與 `indications`（適應症領域）——生醫投資人實際用來分類基金的軸。
3. **sector 詞彙全面健康化**：therapeutics / medtech / diagnostics / digital-health / AI 製藥 / 合成生物 / 長壽 / 女性健康 / 心理健康…（20 個子領域）。
4. **`backing` 出資來源維度**：醫療創投的資金結構特別複雜——藥廠 CVC、保險公司創投、醫院體系基金、大學技轉基金、疾病基金會、主權基金、以及近年大舉進場的科技巨頭與 AI 實驗室，全都在同一個池子裡競逐。把「錢是誰的」拉成一等公民欄位，才能區分全資企業創投與只是拿了策略 LP 支票的獨立合夥事業。

### `backing` 的兩層來源

| 層 | 產生方式 | `evidence` | 落地位置 |
| --- | --- | --- | --- |
| 推論層 | `backfill_backing.py` 以專有名詞字典比對機構名稱／別名，並從描述中抽取「venture arm of X」「backed by X」「anchored by X」等關係句式 | `inferred` | `data/backing.json` overlay |
| 研究層 | agent 查證後直接寫進 `_raw/`，附來源 URL 與 quote | `verified` | `_raw/<segment>.json` |

`build.py` 在 merge 階段套用 overlay，且**研究層永遠優先**：同一個金主名稱若兩層都有，`_raw/` 的版本勝出。
推論層刻意保守——只認少數關係句式，並過濾掉「SAP 共同創辦人 Dietmar Hopp 的投資公司」這類把人名誤判成公司出資的情形。

---

## 4. 平行蒐集方法論（fan-out）

切片計畫的機器可讀版在 [`data/segments.json`](data/segments.json)（含每切片的錨點範例與排除規則）。

- **大市場模板（20 切片）**：`united-states`、`europe`、`greater-china` — 機構類型 × 健康子領域交叉，另加地區限定 extras：
  - 美國 +10：AI-TechBio / 合成生物 / 神經心理 / 長壽 / 女性健康專注基金 + 5 個聚落補遺掃描（Boston、SF Bay、San Diego、NYC、Midwest-South）
  - 歐洲 +7：UK-愛爾蘭 / DACH / 法比荷盧 / 北歐 / 南歐 / 中東歐國別深挖 + 泛歐機構
  - 大中華 +3：人民幣/國資基金 / 香港 / 地方產業集群基金
- **中市場模板（13 切片）**：`japan · south-korea · taiwan · israel · canada · india · southeast-asia · australia-nz`
- **其他地區（4 切片）**：LatAm / MENA-海灣 / 非洲 / 全球健康-impact

合計 **188 個切片 = 188 個研究 agent**（第一輪）。

每個 agent 的任務：用 `WebSearch`/`WebFetch` 做**真實查證**（英文 + 當地語言）、產出符合 schema 的 entity 陣列、寫入自己的 `_raw/<segment>.json`、回傳精簡摘要。錨點（anchors）只是搜尋起點，agent 必須沿協會名錄、co-investor、募資新聞擴散到窮盡。

---

## 4.5 公司半邊與連結圖

### 資料模型（company）

完整定義見 [`schema/company.schema.json`](schema/company.schema.json)。與 entity 刻意**共用同一套 taxonomy**：
`category` / `sectors` 用的是 entity 的 `sector_focus` 詞彙、`modalities` 與 `indications` 也完全相同。
這不是省事，是為了讓「篩選 digital-health 的投資機構」和「篩選 digital-health 的公司」是同一個動作——
另立一套分類就得維護映射表，而映射表一定會漂移。

- **身份**：`name{en,local}` · `aka`（改名前的舊名，連結解析器會用到）· `category` · `sectors` · `status`（private/public/acquired/merged/shut-down）· `founded_year` · `region` · `country` · `hq_city` · `website`
- **在做什麼**：`profile.what`（一句話，具體可查證）· `development_stage`（藥物走臨床期別，器材/軟體走 pilot→commercial）· `lead_asset` · `regulatory[]`（真的拿到的核准，不含申請中）
- **募資**：`funding.total_raised` · `valuation` · `unicorn` · `last_round` · `rounds[]` · **`investors[]`** · `exit`
- **佐證 meta**：與 entity 同構

一家公司若同時經營本業又設有創投臂（例如藥廠），會被記兩筆：本業在 company、創投臂在 entity。
`qa_check.py` 的 `co-name-in-both-halves` 會把兩邊同名的情形挑出來人工確認。

### 連結是解析出來的，不是手寫的

邊有兩個來源，`build_companies.py` 把它們合併：

| 方向 | 來源欄位 | 意義 |
| --- | --- | --- |
| 公司 → 機構 | `funding.investors[].name` | 這家公司說誰投了它 |
| 機構 → 公司 | `track_record.notable_investments[].company` | 這家機構說它投了誰 |

兩邊都主張的邊標 `via: "both"`，比單邊主張的可信。**這是本專案能快速長出公司半邊的原因**：
投資機構半邊在還沒研究任何一家公司之前，就已經帶著 1,645 筆投資紀錄、1,461 個不重複公司名；
研究 agent 的工作因此是「補公司本身的資料」，而不是「從零挖掘誰投了誰」。

`funding.investors[].entity_id` 是**衍生欄位**，研究者一律寫 `null`。手寫的 id 會活得比讓它失效的那次改名還久。

### 名稱解析：寧缺勿錯

`Resolver`（`scripts/build_companies.py`）依序嘗試：人工別名表 → 正規化全名精確比對 → 「核心名」比對。
每一步都**只在唯一命中時**成立。理由是錯誤的連結比缺少的連結更糟：缺少的看得出來，錯誤的會被當成事實。

三個具體設計：

1. **核心名會拒絕回答**。`core("Google Ventures")` = `"google"`，但 `core("Health Capital")` = `None`——
   名字剝掉通用尾綴後只剩 `health` 這種泛詞的機構，不該和其他十幾家一起塌縮成同一個 key。
2. **地區當消歧鍵**。`"OrbiMed"` 同時是美/以/印/中四筆的名稱，但那**真的是四支不同的基金**：
   美國公司的 OrbiMed 解析到 `us-orbimed`，以色列公司的解析到 `il-orbimed`。反方向（機構 → 公司）
   刻意**不**用這招——投資人的所在地說明不了它投的公司在哪，而兩家不同公司同名的機率遠高於同一家機構有多個地區分身。
3. **CJK 必須活著通過正規化**。`norm()` 走 NFKC → NFD → 去結合符 → **NFC** → 繁簡折疊 → 再過濾字元。
   少了 NFC 那步，NFD 會把韓文音節拆成 Jamo、把日文濁點拆離，然後被字元過濾清掉——
   `"한미약품"` 會變成空字串、`"ソニーグループ"` 會變成 `"ソニークルーフ"`，整個亞洲區的連結全部失效。

4. **繁簡一律折疊成簡體**。方向不是隨便選的：**繁→簡是多對一、確定性的，簡→繁是一對多、要猜的**。
   實測 round-trip 就看得出來——`台杉投資` 折成簡體是 `台杉投资`（正確），但反向會變成 `臺杉投資`；
   `启明创投` 反向會變成 `啓明創投`。往一個方向折是精確的，往另一個方向折是在發明異體字。
   含**假名或諺文**的字串完全跳過折疊（那兩種字符可靠地標示了日文/韓文）。純漢字的日文名
   （如 `塩野義製薬`）從字符上無法與中文區分，確實會被折成 `塩野义制薬` 這種亂碼——
   這無害，因為這個值只是雜湊鍵、永遠不會顯示，而且比對的兩邊套用同一個折疊，所以仍然對得上；
   顯示一律用原始的 `name` 欄位。

未解析的名稱不會被丟掉，會寫進 `reports/links.json`，並區分「機構不在名錄裡」與「撞名撞了 N 筆」——
這兩種需要的處理方式不同。這份報表就是下一輪的待辦清單。

### 撞名報表順便當成重複偵測器

同一個正規化後的名稱對到兩筆不同紀錄，通常不是巧合，而是同一個機構被建了兩次。
解析器已經會拒絕在這種情況下建立連結，但**默默拒絕等於把資料 bug 藏起來**，所以一律列進
`reports/links.json` 的 `investor_name_collisions`，並用一個啟發式先做分流：

| 情況 | 判定 | 意義 |
| --- | --- | --- |
| 同網域 **且** 同國家 | `likely-duplicate` | 同一個組織被建了兩次 |
| 同一地區內有兩筆 | `likely-duplicate` | 資料重複，要修 |
| 不同國家 **或** 不同網域 | `regional-vehicles` | 合法。Boehringer Ingelheim Venture Fund 歐/美各有團隊 |
| 其餘 | `undetermined` | 證據不足以判斷，不猜 |

**`region` 不能單獨當作判準**，這是踩過的坑：早期版本只看地區，把「同名不同地區」一律判為合法的區域分支。
但 Gates Foundation Strategic Investment Fund 被兩輪 agent 分別歸到 `rest-of-world` 和 `united-states`——
同國家、同城市、同網域，就是同一個組織被建了兩次。地區是**歸檔決定**，不是關於組織身分的證據；
真正能區分的是官網網域與國家。改用這組判準後，原本被放行的 46 組裡有 17 組其實是重複。

繁簡折疊上線後這份報表特別有產出：原本因為一邊寫繁體、一邊寫簡體而看起來毫不相干的兩筆，
折疊後才撞在一起。

---

## 5. 去重與合併（Dedup）

`build.py` 讀所有 `_raw/*.json` → 攤平 → 以 `is_same_entity(a,b)` 兩兩判斷是否同一機構 → 合併（`sources` 取聯集、`confidence` 取高者、空欄位回填）。

預設規則：**同一 region 且（正規化英文名相同 或 官網網域相同）**。生醫基金名稱極常撞字（Health/Bio/Life 前後綴），所以名字正規化會把這些 token 一併剝掉（比對偏鬆），改用**官網網域**當高精度保險絲。`is_same_entity()` 在 `scripts/build.py` 標了 `CONTRIBUTION POINT`，可依需求微調（例如對 europe/greater-china 多國桶再要求 `country` 相同）。

---

## 6. 重建資料集

```bash
# 全程使用 uv（本專案偏好）；jsonschema 由各腳本的 PEP 723 標頭自動解析
uv run scripts/build.py            # 投資機構半邊
uv run scripts/backfill_backing.py # 重跑背後金主推論 overlay
uv run scripts/build.py            # 再 build 一次讓 overlay 套進資料
uv run scripts/build_companies.py  # 公司半邊 + 連結圖（需要 all-entities.json 已是最新）
uv run scripts/qa_check.py         # 兩半的健康報告
uv run scripts/build_site.py       # 網站資料層
```

**順序有意義**：`build_companies.py` 的名稱解析器要拿最新的 `all-entities.json` 當索引，
所以一定跑在 `build.py` 之後；`build_site.py` 要吃兩半的產物，所以跑在最後。
`build_site.py` 允許公司資料不存在（用空集合），這樣公司 pipeline 出錯不會把整個網站拖下水。

產出：各 `data/<region>/entities.json`、`data/all-entities.json`、`data/stats.json`、
`data/all-companies.json`、`data/links.json`、`data/company-stats.json`、
`reports/validation.md`、`reports/links.json`。

---

## 6.5 網站頁面與統計數字的來源

頁面清單是資料，不是散在各處的 HTML：`scripts/build_site.py` 的 `SITE_PAGES` 定義
`slug` / `layout` / `icon` / 雙語標題，`shell.js` 據此畫導覽列，`app.js` 用 `layout`
挑 renderer。每個 `docs/<slug>.html` 只是一層殼——`<body data-page="…">` 加三個
`<script>`，其他全由 shell + app 注入。**加一頁 = SITE_PAGES 加一筆 + 複製一份殼 +
`RENDERERS` / `WIRE` 各加一個 key**，導覽列與首頁入口卡會自動長出來。

| layout | 頁面 | 做什麼 |
| --- | --- | --- |
| `hub` | `/` | 全站數字 + 入口卡（從 `SITE_PAGES` 自動生成） |
| `directory` | `/directory` | 機構名錄 |
| `companies` | `/companies` | 公司名錄（跟 `directory` 同一套互動模型） |
| `analysis` | `/analysis` | 機構分析 |
| `companyAnalysis` | `/company-analysis` | 新創分析 |
| `methodology` | `/methodology` | 方法論長文 |

**兩個分析頁的數字來源不同，這是刻意的。** 機構分析讀 `stats.json`（build 階段算好）；
新創分析除了連結圖那四個數字之外，**全部在瀏覽器端從 `MED_VC.companies` 現算**。
理由是這半邊要的是交叉表與排行榜（領域 × 地區、投資人最多的公司），沒有哪一張預先算好的
表裝得下；而且既然公司陣列本來就整包送到前端了，現算不用多付一毛 payload。

代價是同一個數字有兩套實作。所以它們必須對得起來——`linked_companies` / `edges` /
`linked_investors` 三個數字，Python 端與瀏覽器端各自獨立算出 **717 / 1,497 / 646**，
完全一致。改任何一邊的解析邏輯時，這組數字就是回歸測試。

連結圖的「兩邊都證實」與「被點名但尚未建檔」只能來自 `company-stats.json`：
待辦清單根本沒有出現在前端 payload 裡，前端無從重算。頁面上直接寫明了這件事。

---

## 7. 免責

非官方整理，僅供研究參考。金額 / 股權 / 錄取率等數字以各機構官方公開資料為準，引用前請依 `sources` 自行查證。
