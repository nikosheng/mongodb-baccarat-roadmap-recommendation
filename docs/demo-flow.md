# 演示流程：語義向量匹配的靈活性與實時性

本文檔記錄完整的三階段演示，展示 MongoDB Vector Search 如何透過語義匹配（而非規則引擎）來辨識百家樂路數，並演示「動態新增路數 Pattern 無需重啟服務即可生效」的特性。

---

## 演示序幕

打開前端 http://localhost:5173，後端 API 服務已啟動。系統預設已預加載 **10 個主路 Pattern 和 7 個下三路 Pattern**。

每當玩家輸入新局數，系統會：
1. 計算最近最多 10 局的局數序列
2. 呼叫 `describe_window_in_nl()` 轉成固定格式英文描述
3. 用 Voyage 生成 query 向量
4. 在主路 `patterns` collection 搜尋 Top 5 相似 Pattern
5. 同時計算三路衍生符號，在獨立的 `derived_patterns` collection 搜尋

**搜尋分數閾值：`PATTERN_MIN_SCORE = 0.82`**（超過這個分數不標記低信心；下三路亦同）

---

## 範例 1：既有路數辨識 — 單跳（`BPBPBPBP`）

### 執行步驟

1. 點擊「新靴」開始
2. 逐一按下列順序輸入 8 局：**B P B P B P B P**

   可直接按鍵盤快捷鍵（B=莊，P=閒），或點擊按鈕

3. 觀察右側「大路 Match 推薦排行榜」

### 預期結果

**主路側**
- **Top 1：單跳** (score ≈ 0.952)
- 高信心標籤，下一手預測為莊（B）

**下三路側**
- 三路符號：大眼仔 RRRRRR、小路 RRRRR、蟑螂路 RRRR
- 前 3 局後下三路尚無符號，約 8 局開始出現
- **匹配：三元及第** (score ≈ 0.865)
  - 原因：「單跳」導致大路每一欄高度都相同（各 1 顆），因此三路都開紅
  - 核心原理：下三路衡量的是「跨欄位的結構對稱性」，不是「主路外觀是什麼」

### 展示重點

✓ 系統成功識別既有路數  
✓ 主路與下三路語義空間獨立：同一牌局可有完全不同的主路/下三路型態  
✓ 下三路用語義相似度（非符號完全相等）做搜尋

---

## 範例 2：既有路數辨識 — 雙雙跳（`BBPPBBPP`）

### 執行步驟

1. 點擊「新靴」開始
2. 輸入 8 局：**B B P P B B P P**
3. 觀察排行榜變化

### 預期結果

**主路側**
- **Top 1：雙雙跳** (score ≈ 0.948)
- 下一手預測為莊（B）

**下三路側**
- 三路符號：大眼仔 RRRRR、小路 RRR、蟑螂路 R
- **匹配：三元及第** (score ≈ 0.874)
  - 原因同範例 1：每欄都是 2 顆，高度相等 → 三路都紅

### 展示重點

✓ 不同的主路型態可映射到相同的下三路訊號  
✓ 系統用「結構相似度」而非「字面相似度」匹配

---

## 範例 3：新增路數的動態擴充 — 莊龍回頭

這是這次演示的核心亮點。展示「後台新增 Pattern → 不改程式 → 已有遊戲紀錄無需重算 → 新牌局立即生效」。

### 背景說明

「莊龍回頭」是一種**尚未被預設庫涵蓋的路數情境**：
- 莊連 4 局 → 被閒中斷 1 局 → 莊再連 4 局
- 核心訊號：打斷後**已恢復**同方向龍，而非單純「龍被打斷」

目前預設庫只有「長莊斷龍」（莊連 6+ → 閒突現），沒有「恢復回頭」的專門 Pattern。

### 階段 A：新增前基線測試

#### 執行步驟

1. 開新靴
2. 輸入 9 局：**B B B B P B B B B**
3. **記錄**右側排行榜

#### 預期結果（新增前）

```
Top1: 長莊斷龍 (0.9242)
Top2: 長閒斷龍 (0.921)
Top3: 長莊連龍 (0.9172)
...
```

#### 現象解讀

- 系統找到「長莊斷龍」作為最接近的 Pattern
- 但這個 Pattern 描述的是「長龍**剛被打斷**」，不是「已恢復」
- 分數在 0.92+ 不會標記低信心（閾值 0.82），但直觀上不夠精準

**這是我們要改進的地方。**

### 階段 B：後台新增「莊龍回頭」Pattern

#### 執行步驟

1. 開瀏覽器新分頁，打開 http://localhost:5173/admin/new
2. 選擇「表單模式」標籤
3. 填寫以下內容：

| 欄位 | 值 |
|---|---|
| 名稱 | `莊龍回頭` |
| 分類 | `custom` |
| 代表序列 | `BBBBPBBBB` |
| 說明 | 莊連四局後被一局閒短暫打斷，隨後再次出現四連莊，呈現原方向恢復的雙段莊龍結構。 |
| 下一局預測 | `B`（莊） |
| 基礎信心值 | `0.55` |
| 啟用 | ✓ 是 |

4. 點擊「儲存」

#### 執行流程（系統自動）

```
表單提交
  ↓
describe_window_in_nl('BBBBPBBBB')
  ↓
產生語義描述文字（見下方「後台自動產生的描述」）
  ↓
Voyage 向量化（document 模式）
  ↓
寫入 patterns collection
  ↓
Atlas Vector Search 索引收錄（通常 3~5 秒）
  ↓
完成
```

#### 後台自動產生的描述

系統會依程式邏輯自動產生以下描述，然後作為 embedding 的輸入：

```
Baccarat sequence: Banker Banker Banker Banker Player Banker Banker Banker Banker

Window summary:
- Length: full window
- Dominant side: Banker heavily dominates
- Current state: ongoing Banker streak of 4
- Longest run: medium run of four
- Alternation: occasional alternation
- Tie activity: no Tie in this window
- Recent reversal: Banker resumed shortly after a brief Player interruption
- Overall rhythm: mixed rhythm with short runs
- Last three results: Banker Banker Banker
```

**關鍵是「Recent reversal」這一欄自動判斷為「Banker resumed shortly after...」** — 這個措辭跟既有 Pattern 都不同，形成獨特的語義簽名，讓向量搜尋能區分「回頭」與「斷龍」。

#### 驗證插入成功

觀察畫面提示或回到 http://localhost:5173/admin 列表，應該看到「莊龍回頭」出現在 Pattern 清單中，成為第 11 個 Pattern。

### 階段 C：新增後效果驗證 — 重播原序列

#### 執行步驟

1. 回到模擬器頁面（或開新分頁 http://localhost:5173）
2. 開新靴
3. **重複輸入相同的 9 局序列：B B B B P B B B B**
4. 觀察排行榜變化

#### 預期結果（新增後）

```
Top1: 莊龍回頭 (0.9395)  ← 排名大幅提升
Top2: 長莊斷龍 (0.9242)  ← 被擠到第二
Top3: 長閒斷龍 (0.921)
...
```

#### 差異對照

| 指標 | 新增前 | 新增後 | 變化 |
|---|---|---|---|
| Top1 Pattern | 長莊斷龍 | 莊龍回頭 | ✓ 切換 |
| Top1 分數 | 0.9242 | 0.9395 | ↑ +0.0153 |
| 排名變化 | 無 | 新 Pattern 躍升為首 | ✓ 立即生效 |

**演示重點**：「不改一行程式碼、不重啟服務、同一段牌局在新增 Pattern 前後有完全不同的辨識結果。」

### 階段 D：語義泛化驗證 — 測試相近變體

展示「新增 Pattern 後，不完全相同但結構相近的牌局也能被匹配」。

#### 執行步驟 1：變體 A（恢復段變短）

1. 新靴
2. 輸入 8 局：**B B B B P B B B**（比原序列少一個 B）
3. 觀察排行榜

#### 預期結果

```
Top1: 莊龍回頭 (0.9352)
```

#### 執行步驟 2：變體 B（前段變長）

1. 新靴
2. 輸入 10 局：**B B B B B P B B B B**（前段多一個 B）
3. 觀察排行榜

#### 預期結果

```
Top1: 莊龍回頭 (0.9351)
```

#### 演示重點

✓ 新增後的 Pattern 能「泛化」匹配相近情境  
✓ 不是「只有完全相同的序列才能匹配」  
✓ 不是「規則引擎的完全符號匹配」，而是「語義層面的結構識別」

---

## 演示總結表

| 階段 | 序列 | 主路 Top1 | 分數 | 下三路 | 核心展示 |
|---|---|---|---|---|---|
| 範例 1 | `BPBPBPBP` | 單跳 | 0.952 | 三元及第 | 既有 Pattern 正常辨識 |
| 範例 2 | `BBPPBBPP` | 雙雙跳 | 0.948 | 三元及第 | 不同主路可同一下三路 |
| 範例 3A（前） | `BBBBPBBBB` | 長莊斷龍 | 0.9242 | （不展示） | 新增前基線 |
| 範例 3B（後） | `BBBBPBBBB` | 莊龍回頭 | 0.9395 | （不展示） | 新增後立即生效 |
| 變體 A | `BBBBPBBB` | 莊龍回頭 | 0.9352 | 逢藍知返 | 語義泛化 |
| 變體 B | `BBBBBPBBBB` | 莊龍回頭 | 0.9351 | 逢藍知返 | 語義泛化 |

---

## 技術原理簡介（背景說明）

### 為什麼「莊龍回頭」能被精確辨識？

當系統處理 `BBBBPBBBB` 時：

1. **計算窗口特徵**（自動）
   - 長度：9 局（full window）
   - 莊優勢：9/9（heavily dominates）
   - 目前狀態：4 連莊
   - 最長連段：4
   - 反轉偵測：✓ 檢測到「莊連 4 後被短暫中斷，隨後又回來」

2. **產生英文描述**（自動）
   - 每個特徵填入固定模板
   - 特別是「Recent reversal」這一欄會寫成 **"Banker resumed shortly after a brief Player interruption"**

3. **向量化**（Voyage）
   - 上述描述轉成 1024 維向量
   - 「莊龍回頭」Pattern 也是同樣流程產生的向量

4. **語義相似度比較**（Atlas $vectorSearch）
   - cosine 相似度 ≈ 0.94（超過 0.82 閾值）
   - 遠高於「長莊斷龍」的 0.92

### 為什麼這個設計比「規則引擎」更靈活？

**規則引擎方式**：
```
if (連莊 >= 4 AND 被閒中斷 AND 再連莊 >= 4) then 莊龍回頭
```
缺點：每加一種新路數，要改程式、重新編譯、重啟服務。

**語義向量方式**：
```
輸入牌局序列
  ↓
自動產生描述（永遠用同一個 describe_window_in_nl()）
  ↓
向量搜尋（不涉及邏輯判斷）
  ↓
找最相似的已知 Pattern
```
優點：後台添加新 Pattern 後，下一次牌局立即能用新 Pattern 搜尋。因為搜尋本質上是「這段描述文字最像哪個已知描述」，而非「是否滿足 if-then 條件」。

---

## 演示技巧與常見問題

### Q1：為什麼要先展示範例 1、2？

A：建立「基線」。讓觀眾看到系統在既有 Pattern 上運作正常，避免後面新增時被質疑「會不會本來就能匹配？」

### Q2：「莊龍回頭」分數 0.94 看起來很高，怎麼證明它比「長莊斷龍」的 0.92 有意義？

A：  
1. 展示數值本身（0.9395 vs 0.9242，差 0.015）
2. 拉開相近變體測試（`BBBBPBBB` 仍是 0.935 vs 0.928），差距更清晰
3. 強調「精度」而非「閾值超越」：新增前無法區分「剛斷」與「已回頭」，新增後能區分

### Q3：下三路怎麼展示？

A：
- 範例 1、2 重點在主路的既有辨識能力，下三路作為「附加效果」
- 變體 A、B 的下三路會跳到「逢藍知返」（因為 `BBBBPBBB` / `BBBBBPBBBB` 的衍生路結構不同），可帶出「同一牌序的主路下三路不必同步」的設計

### Q4：如果網路慢、Atlas 同步延遲怎麼辦？

A：
- 後台新增 Pattern 後，頁面會提示保存成功
- 但 Atlas 索引同步需要時間（通常 3~5 秒，有時更長）
- **建議**：在演示台詞裡預留「系統正在同步索引」的過程說明，顯得更專業
- 如果要確保同步完成，可以重新整理前端頁面（Ctrl+R）

### Q5：可以同時新增多個 Pattern 嗎？

A：可以，但為了演示效果清晰，建議一次只新增一個，各自驗證效果後再加下一個。

---

## 延伸想法

### 進階展示 1：下三路新增

如果時間充足，可複製同樣流程到下三路：

1. 後台 `/admin/derived/new`
2. 填入三路符號（例如 `bigEye=BBBB, small=RRR, cockroach=(none)`）
3. 系統自動辨識為「逢藍知返」型態
4. 儲存
5. 播放能生成同樣下三路符號的牌局，驗證新 Pattern 命中

### 進階展示 2：Embedding Preview

在後台新增 Pattern 時，點擊「embedding 預覽」按鈕，可看到：
- 向量前 16 個維度（sample）
- 向量 norm（歸一化檢查）
- 自動產生的英文描述（完整文本）

這能讓觀眾直觀看到「文字 → 向量」的中間過程。

### 進階展示 3：相似度檢查

新增 Pattern 時點「相似度檢查」，系統會用新 Pattern 的向量在既有庫裡搜尋，找出最相似的 Top 5 既有 Pattern。

「莊龍回頭」新增時應顯示：
```
1. 長莊斷龍 (0.8506)
2. 長閒斷龍 (0.8498)
3. 和局夾擊 (0.8467)
```

這能說明「新 Pattern 確實填補了現有 Pattern 間的空隙」。

---

## 演示檢查清單

啟動演示前，確認以下項目：

- [ ] 後端 API 啟動（`make api` 或 `uvicorn app.main:app --reload --port 8000`）
- [ ] 前端開發伺服器啟動（`npm run dev`）
- [ ] 瀏覽器打開 http://localhost:5173
- [ ] `.env` 已設定真實 Atlas URI 和 Voyage API Key（`USE_MOCK_EMBEDDER=false`）
- [ ] 資料庫連線正常（首次載入會有延遲，等 vector index 建立）
- [ ] 預設 10 個主路 Pattern 已 seed（可於後台 `/admin` 確認）
- [ ] 預設 7 個下三路 Pattern 已 seed（可於後台 `/admin/derived` 確認）
- [ ] 網路穩定，避免 Voyage API 超時

---

## 參考資料

- 完整設計與校準過程：見 README.md 的「設計流程與原理」一節
- Embedding 實作細節：`backend/app/services/window_text.py` 與 `backend/app/services/derived_roads.py`
- Pattern 儲存與搜尋：`backend/app/services/pattern_service.py` 與 `backend/app/services/match_engine.py`
- 下三路 Pattern：`backend/app/services/derived_pattern_service.py` 與 `backend/app/services/derived_match_engine.py`
