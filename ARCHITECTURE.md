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

```
med-vc/
├── schema/entity.schema.json     # 一個「投資機構」的 JSON Schema（欄位定義 + 型別）
├── data/
│   ├── taxonomy.json             # 受控詞彙：type / stage / sector / modality / indication / region…
│   ├── regions.json              # 12 地區 metadata（生醫聚落 / 語言 / 權威來源站）
│   ├── segments.json             # 研究切片計畫（模板 × 地區 + 錨點範例）
│   ├── <region>/
│   │   ├── _raw/<segment>.json   # ← agent 原始產出，一個切片一檔（永不衝突）
│   │   └── entities.json         # ← build.py 去重合併 + 驗 schema 後的結果
│   ├── all-entities.json         # 全球合併（build.py 產生）
│   └── stats.json                # 各維度統計（build.py 產生）
├── scripts/build.py              # 合併 / 去重 / 驗證 / 統計（uv run）
└── reports/validation.md         # schema 違規 + 資料品質報告（build.py 產生）
```

12 個地區：`taiwan · united-states · europe · greater-china · japan · south-korea · israel · canada · india · southeast-asia · australia-nz · rest-of-world`

---

## 3. 資料模型（entity）

完整定義見 [`schema/entity.schema.json`](schema/entity.schema.json)。維度概覽：

- **身份**：`name{en,local}` · `type` · `subtypes` · `founded_year` · `status` · `region` · `country` · `hq_city` · `offices` · `website` · `links`
- **資本**（VC/CVC/crossover/growth）：`capital.aum` · `capital.current_fund` · `capital.funds[]`
- **策略**：`strategy.stages` · `check_size` · `ownership_target_pct` · `geo_focus` · `sector_focus`（健康子領域）· `thesis`
- **生醫特有**：`lifesci.modalities`（小分子/抗體/細胞/基因治療/RNA…）· `lifesci.indications`（腫瘤/神經/罕病…）· `company_creation`（Flagship 式公司創建）· `invests_public_markets`（crossover）· `science_platform_notes`
- **加速器/育成專屬**：`program.{length_weeks, cohort_size, equity_taken_pct, investment, lab_space, demo_day, application_url, acceptance_rate, …}`
- **戰績**：`track_record.{portfolio_count, notable_investments[], exits[], co_investors[]}`（outcome 含 FDA-approved）
- **人 / 申請**：`people[]`（含 `background`：MD/PhD、藥廠出身等科學履歷）· `team_size` · `application.{how_to_apply, accepts_cold_inbound, contact}`
- **佐證 meta**：`sources[]{url,title,publisher,accessed,supports,quote}` · `confidence` · `verification_notes` · `last_updated` · `researched_by`

必填：`id · name · type · region · country · sources · confidence · last_updated`。其餘可選——查不到就省略，不要塞假值。

相對 `all-vc-info` 的醫療特化：

1. **新增 3 種機構類型**：`crossover-fund`（公私跨界，生技特有）、`venture-philanthropy`（疾病基金會創投）、`university-hospital-fund`（大學/醫院創投臂）。
2. **兩個新維度**：`modalities`（治療模式）與 `indications`（適應症領域）——生醫投資人實際用來分類基金的軸。
3. **sector 詞彙全面健康化**：therapeutics / medtech / diagnostics / digital-health / AI 製藥 / 合成生物 / 長壽 / 女性健康 / 心理健康…（20 個子領域）。

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

## 5. 去重與合併（Dedup）

`build.py` 讀所有 `_raw/*.json` → 攤平 → 以 `is_same_entity(a,b)` 兩兩判斷是否同一機構 → 合併（`sources` 取聯集、`confidence` 取高者、空欄位回填）。

預設規則：**同一 region 且（正規化英文名相同 或 官網網域相同）**。生醫基金名稱極常撞字（Health/Bio/Life 前後綴），所以名字正規化會把這些 token 一併剝掉（比對偏鬆），改用**官網網域**當高精度保險絲。`is_same_entity()` 在 `scripts/build.py` 標了 `CONTRIBUTION POINT`，可依需求微調（例如對 europe/greater-china 多國桶再要求 `country` 相同）。

---

## 6. 重建資料集

```bash
# 全程使用 uv（本專案偏好）；jsonschema 由 build.py 的 PEP 723 標頭自動解析
uv run scripts/build.py
```

產出：各 `data/<region>/entities.json`、`data/all-entities.json`、`data/stats.json`、`reports/validation.md`。

---

## 7. 免責

非官方整理，僅供研究參考。金額 / 股權 / 錄取率等數字以各機構官方公開資料為準，引用前請依 `sources` 自行查證。
