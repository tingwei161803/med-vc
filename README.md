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

多軸篩選（地區 × 類型 × 健康子領域 × 治療模式 × 適應症 × 階段）· 全文搜尋（機構名／論點／被投公司／城市）·
中英雙語切換 · 深淺色模式 · 點卡片看完整詳情與**來源 quote 佐證** · 分析圖表儀表板 · CSV 匯出。
純靜態 HTML/CSS/JS（Material Design 3、零 build），由 `docs/` 經 GitHub Pages 部署。

> 網站資料層由 `uv run scripts/build_site.py` 從 `data/all-entities.json` 產生。

---

## 收錄範圍

| 維度 | 內容 |
| --- | --- |
| **12 地區** | 台灣 · 美國 · 歐洲 · 大中華 · 日本 · 南韓 · 以色列 · 加拿大 · 印度 · 東南亞 · 澳紐 · 其他 |
| **15 類機構** | 生醫 VC · CVC · crossover 基金 · growth equity · Micro-VC · 創業工作室 · 加速器 · 育成/lab space · 大學/醫院基金 · 疾病基金會創投 · 政府計畫 · 天使網絡 · 天使 syndicate · 家族辦公室 · 股權群募 |
| **20 健康子領域** | 新藥 · 醫材 · 診斷 · 工具 · 數位健康 · 醫療服務 · AI 製藥 · 基因體 · 合成生物 · 細胞基因治療 · 長壽 · 女性健康 · 心理健康 … |
| **生醫特有維度** | modality（小分子/抗體/細胞/基因/RNA…）× indication（腫瘤/神經/罕病…）× 公司創建模式 × 公私跨界 |
| **每筆面向** | 身份 / 資本 / 投資策略 / 生醫焦點 / 加速器專屬 / 戰績 / 團隊 / 申請方式 / 來源佐證 |

每筆資料都附 `sources[]`（真實 URL + 佐證 `quote`）與 `confidence` 信心評級。

---

## 怎麼用這份資料

- 結構化資料在 `data/<region>/entities.json`，全球合併在 `data/all-entities.json`。
- 欄位定義見 [`schema/entity.schema.json`](schema/entity.schema.json)，受控詞彙見 [`data/taxonomy.json`](data/taxonomy.json)。
- 整體架構、蒐集方法論、切片計畫、去重規則見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

```bash
# 重建合併資料 + 驗證 + 統計（全程 uv）
uv run scripts/build.py
cat data/stats.json          # 各維度數量
cat reports/validation.md    # schema 違規 / 資料品質

# 資料完整性 QA（Layer-1 結構檢查：重複 / 來源 / 詞彙 / 薄檔 / 幻覺字樣）
uv run scripts/qa_check.py
cat reports/qa.json          # 完整問題清單
```

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
