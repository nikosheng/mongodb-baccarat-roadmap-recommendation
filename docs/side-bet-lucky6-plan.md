# Side Bet 推薦設計計畫（Lucky 6 v1）

> 狀態：設計文件，尚未實作。  
> 範圍：真實百家樂發牌、牌面記錄、Lucky 6 歷史切片向量搜尋與前端展示。  
> 重要：文件中的 demo 數值是說明計算流程的假設值，不是已驗證的預測成果或投注優勢。

## 1. 目標與已定設計

新增一個獨立的 Side Bet 流程：以最近 N 手的牌局特徵建立 13 維手工數值向量，使用相同 N 專屬的 z-score 統計轉換後存入 MongoDB Atlas Vector Search。即時查詢時，以該 N 的轉換處理當前窗口，在同 N 的合成歷史切片中搜尋 Top 10 鄰居，顯示最相似切片分數，並以鄰居的下一手 Lucky 6 結果計算觀察命中率與 lift。

| 決策 | 設計 |
|---|---|
| v1 side bet | Lucky 6；同時記錄後續可用的 pair、natural 等底層牌局資料，但 v1 不推薦它們 |
| 發牌 | 8 副牌（416 張）、洗牌後按標準百家樂補牌規則發牌；B/P/T 由實際牌面計算，不再用獨立機率表 |
| 牌面 UI | 隨機模擬自動發真牌並顯示牌面；不做手動選牌 UI |
| 手動 B/P/T | 保留既有輸入方式；這些局沒有牌面，不能作為 Side Bet 特徵 |
| 歷史資料 | 發牌引擎產生 2,000 靴合成資料；預先為支援的 N=1/3/5/10 建切片，每種 N 使用同一批牌靴但各有自己的向量及統計，約 522,000 個切片（假設每靴 70 手且每個窗口需下一手標籤） |
| 向量 | 13 維手工特徵，先用語料庫 mean/std 做 z-score；之後以 cosine 建索引和查詢，不使用 Voyage embedding |
| 搜尋/統計 | 搜 Top 10（不同歷史靴）；Top 1 Atlas score 作相似度分數，Top 10 下一手結果作鄰域觀察率，和相同 N 的全語料庫基準率比較 |
| 預測時間點 | 至少累積 N 手連續且含牌面資料的完整手牌後，用目前設定 N 產生「下一手」Side Bet 資訊；不能把已知手牌結果當成預測 |

### N 的設定與資料支援策略

建議的 `.env` 設定：

```dotenv
SIDE_BET_WINDOW=10
SIDE_BET_SUPPORTED_WINDOWS=1,3,5,10
SIDE_BET_DATASET=demo
```

- `.env` 使用 `SIDE_BET_WINDOW=10` 選擇目前即時查詢的窗口長度；更改環境變數後需重啟 backend 才會生效。
- `SIDE_BET_SUPPORTED_WINDOWS=1,3,5,10` 表示語料已預先包含的窗口長度。正式預設仍為 10；1/3/5 主要供內部比較 N 的影響。
- N=1/3 等較短窗口雖可共用 13 維 schema，但比例、streak、間隔等特徵會變得離散或退化，不能預期和 N=10 有相同辨識力；每個 N 都要獨立評估，Marketing demo 預設先用 N=10。
- `SIDE_BET_DATASET=demo` 或 `monte_carlo` 選擇查詢資料集；marketing demo 使用固定 demo query 與 demo-only 歷史 slice，分析/正式內部觀察使用 Monte Carlo 語料。預設值應依部署環境明確指定，不依環境猜測。
- `.env.example` 文件（不含任何 secret）列出以上參數；正式 `.env` 只覆寫需要改動的值。後端 `config.py` 將 window 解析成整數、window 清單解析成整數陣列，並驗證 dataset 為允許值；啟動時驗證 N 在支援清單內，避免任意 N 查詢沒有對應語料。
- Monte Carlo Seed 為每個支援的 N 產生 13 維 raw feature vectors、N 專屬 mean/std 與下一手 Lucky 6 標籤。Mean/std 僅由該 N 的 Monte Carlo 訓練語料擬合；demo query 與 demo-only slices 也套用同一 N 的 Monte Carlo scaler，確保在相同座標系比較，但 demo 搜尋結果與 baseline 仍獨立隔離。N 或 feature/corpus version 不同代表座標基準可能不同，因此**不可拿 N=10 的 mean/std 去正規化 N=3**。也保留模擬原始牌局/牌面紀錄，讓未來加入新 N 時可從原始局重切窗口，不必重新模擬全部牌靴。
- 假設每靴 70 手且每個樣本需要 N 手上下文加下一手標籤，N=1/3/5/10 分別約有 69/67/65/60 個切片；共約 261 個/靴、522,000 個切片/2,000 靴。最終數量依 cut-card 與實際每靴手數計算，seed log 必須輸出實際數字。
- 所有 N 的向量維度仍為 13，放在同一 `side_bet_slices` collection 和同一 13 維 vector index；文件以 `windowLength`、`datasetType` 標記，index 對 `windowLength`、`datasetType` 和 `corpusVersion` 建 filter，查詢時只搜尋相同 N/資料集/版本的文件。Scaler 以 `windowLength + featureVersion + corpusVersion` 作 key，並由 Monte Carlo 訓練語料擬合；Lucky 6 baseline 以 `windowLength + datasetType + corpusVersion` 作 key。Demo query 與 demo slices 使用同一 N 的 Monte Carlo scaler，但只搜尋 demo slices、使用 demo baseline。
- 在支援清單內修改 `SIDE_BET_WINDOW`（例如 10 改 5）：**不需重 seed、不需重建 vector index**，但需重啟 backend；查詢會改用 N=5 的 stats 與歷史切片。
- 新增支援清單以外的 N（例如 7）：需為該 N 從保留的模擬牌靴/round 資料產生歷史切片、重新計算該 N 專屬 mean/std 與 baseline；同一批 13 維特徵定義不變時，只需加入 windowLength filter 可接受值，13 維 index 不變。若原始模擬 round/card 資料未保留，才必須重跑模擬 seed。
- 新增/移除 13 個 feature 本身則是不同維度 schema/version：要重新計算所有受影響 N 的 vectors/stats 並建立對應維度的新 index。不要和單純切換 N 混為一談。
- 啟動時驗證 `SIDE_BET_WINDOW` 在支援清單中；不支援時回報可用值，不可靜默退回其他 N 或拿錯 stats。

**N 的操作結論**：Marketing 在已支援的 1/3/5/10 間切換，只改 `.env` 並重啟 backend，不需重 seed。要讓 N=7 可用時，先用保留的原始牌局資料產生 N=7 的 slices/stats/baseline，再把 7 加入支援清單；同一 13 維 feature schema 下不必重建 index。

## 2. 現有系統缺口

目前 `Round` 只記錄 `shoeId`、`roundNo`、`result`、`createdAt`、`source`；randomize 以硬編碼機率抽出 B/P/T，不產生真實牌面。Lucky 6 需要莊家最終點數、莊家勝負及莊家牌張數，這些都不能從 B/P/T 單獨推回。因此需要先建立發牌層，Side Bet 才有可計算的輸入。

現有主路/下三路 Voyage embedding 與 Side Bet 的特徵空間保持分離：前兩者是文字語意向量；Side Bet 向量是可解釋、可直接核算的牌局統計特徵。

## 3. 發牌與牌局資料模型

### 3.1 Card 與發牌規則

新增 `backend/app/services/baccarat_dealer.py`：

- 生成 8 副牌：4 種花色 × A 到 K × 8 副，共 416 張。
- 點數：A=1、2–9 為牌面點數、10/J/Q/K=0；手牌總點數取個位數（mod 10）。
- 每手先發閒、莊各兩張。任一方前兩張合計為 8 或 9 時為 natural，雙方均不補牌。
- 非 natural 時，閒家 0–5 補牌，6–7 停牌。
- 莊家依標準補牌表決定是否補牌：

| 莊家兩張總點數 | 閒家未補牌 | 閒家第三張 0–1 | 2–3 | 4–5 | 6–7 | 8 | 9 |
|---|---|---|---|---|---|---|---|
| 0–2 | 補 | 補 | 補 | 補 | 補 | 補 | 補 |
| 3 | 補 | 補 | 補 | 補 | 補 | 補 | 停 |
| 4 | 補 | 停 | 補 | 補 | 補 | 停 | 停 |
| 5 | 補 | 停 | 停 | 補 | 補 | 停 | 停 |
| 6 | 停 | 停 | 停 | 停 | 補 | 停 | 停 |
| 7 | 停 | 停 | 停 | 停 | 停 | 停 | 停 |

- 比較雙方最終點數，得出 B/P/T。
- 牌堆狀態必須跨 API 請求持續保存，不能每手重新洗牌。以 8 副牌與 cut-card/牌堆終止狀態管理一靴；牌堆到切牌界線後完成當手並要求開始新靴，不在同一靴中途偷偷重洗。實際 cut-card 位置做成設定值或明確的 demo 規則。
- 每手最多 6 張牌（雙方各 3 張），dealer 要保證一手內所需牌數足夠。

### 3.2 Round 欄位

在 `backend/app/models/schemas.py` 新增 `Card` model，至少含 `rank`、`suit`。`Round` 增加可空欄位；手動 B/P/T 記錄的欄位維持 `None`：

- `bankerCards`, `playerCards`
- `bankerTotal`, `playerTotal`, `margin`
- `bankerCardCount`, `playerCardCount`, `totalCardCount`
- `bankerPair`, `playerPair`（前兩張 rank 相同）
- `bankerPerfectPair`, `playerPerfectPair`（前兩張 rank 與 suit 都相同）
- `naturalType`（none / banker natural / player natural / both natural，並保存 8/9 類型或可從 cards 重算）
- `lucky6Result`（none / banker_6_two_cards / banker_6_three_cards）

`margin` 定義固定為 `bankerTotal - playerTotal`，範圍 -9 到 +9；Tie 的 margin 是 0。特徵編碼只用此一致定義。

牌堆狀態屬於後端內部資料，不應隨 Shoe API 回傳給瀏覽器；序列化 Shoe 時需排除 dealer state。新增資料庫更新時要保證 roundNo 與 deck state 一致，避免重複發牌或同一張實體牌在一靴內被發出兩次。

### 3.3 Lucky 6 判定

Lucky 6 命中定義：**莊家贏，且莊家最終點數為 6**。

- 莊家兩張牌以 6 點勝：`bankerTotal == 6 and result == "B" and bankerCardCount == 2`，標記 `banker_6_two_cards`。
- 莊家補至三張後以 6 點勝：條件同上但 `bankerCardCount == 3`，標記 `banker_6_three_cards`。
- 莊家 6 點但和局或輸牌都不算命中。
- 報酬按使用者提供的規則顯示 1:12 / 1:20；實作前要在 UI 文案中釐清這是「淨賠率」還是「含本金總返還」，因 break-even 計算依此不同。若 1:12、1:20 表示淨賠率，單位下注的 break-even hit rate 分別為 `1/(12+1)` 與 `1/(20+1)`。

## 4. 13 維 Side Bet 特徵

`backend/app/services/side_bet_features.py` 提供單一、可重用的特徵抽取函式。Seed 與即時查詢必須呼叫同一版函式，不能各自實作一套。對選定的 N 手窗口產生下列 13 個 raw features；表格中的「窗口」均指當前 N。

### 13 維特徵的行銷解讀

這 13 維不是「13 個 Lucky 6 因果因子」，而是每段牌局的**共同描述座標**：把結果走勢、點數差、發牌深度與牌面組成一起編碼，供 Vector Search 找到整體型態相近的歷史窗口。Marketing 可以用它回答「系統比對時看了哪些面向」，再呈現相似歷史窗口後續 Lucky 6 的觀察結果；不能把某一維單獨描述成已證明會提高 Lucky 6 機率的原因。

| # | 特徵 | 怎麼算 | Marketing 可以怎麼理解 | 與 Lucky 6 的關係 |
|---:|---|---|---|---|
| 1 | `bankerWinRatio` | 窗口 B 手數 / 窗口總手數 | 最近 N 手中莊家勝出的比例，描述這段牌局的結果傾向。 | **情境**：Lucky 6 要求莊家勝，但過去莊勝比例不等於下一手莊勝機率。 |
| 2 | `playerWinRatio` | 窗口 P 手數 / 窗口總手數 | 閒家勝出的比例，補足結果傾向的另一面；與莊勝比例一起描述窗口由誰主導。 | **情境**：作為歷史結果構成，沒有單獨的 Lucky 6 因果含義。 |
| 3 | `tieRatio` | 窗口 T 手數 / 窗口總手數 | 和局出現頻率，讓窗口描述包含 B/P 以外的第三種結果。 | **情境**：避免把所有非莊勝都簡化成閒勝；不是 Lucky 6 的直接條件。 |
| 4 | `avgMargin` | 每手 `bankerTotal - playerTotal`，再取 N 手平均 | 描述最近牌局莊閒最終點數差的方向與平均幅度；正值偏莊、負值偏閒。 | **輔助情境**：平均差不表示莊家終局點數是 6，也不等同 Lucky 6 命中。 |
| 5 | `marginVolatility` | N 手 signed margin 的 population standard deviation | 描述點數差是否穩定：低值代表差距較集中，高值代表窗口內差距變化較大。 | **輔助情境**：描述窗口的波動外觀，並非 Lucky 6 規則本身。 |
| 6 | `ratio4Cards` | 總共發 4 張牌的手數 / 窗口手數 | 雙方都只拿兩張牌的比例，可作為「較少補牌」牌局結構的描述。 | **發牌結構**：描述整手深度；不能單獨得知莊家是否拿 2 張或是否以 6 點勝。 |
| 7 | `ratio5Cards` | 總共發 5 張牌的手數 / 窗口手數 | 只有其中一方補第三張的比例，表示窗口中出現單邊補牌的頻度。 | **發牌結構**：是 4 張與 6 張之間的中間狀態；莊/閒誰補牌仍需牌面欄位。 |
| 8 | `ratio6Cards` | 總共發 6 張牌的手數 / 窗口手數 | 雙方都補第三張的比例，可直觀描述「近期牌局是否常見雙邊補牌」。 | **較貼近發牌情境**：Lucky 6 三張版本需要莊家補牌，但 6 張總數不保證是莊家補牌，更不代表莊家以 6 點勝。 |
| 9 | `faceCardDensity` | 10/J/Q/K 的發出張數 / 窗口總發牌張數 | 描述最近實際發出的牌裡，點數為 0 的牌占多少；是牌面組成摘要。 | **牌面組成情境**：因牌靴是不放回發牌，已出牌會改變剩餘牌組成；但只看 N 手密度不足以推斷下一手結果，完整牌靴/剩餘牌組成才是更直接資訊。 |
| 10 | `roundsSinceLastTie` | 從窗口尾端往回數至最近一次 Tie；沒有則記 N | 用「距離上次和局幾手」描述近期節奏，方便與歷史窗口比較。 | **情境**：主要描述 Tie 間隔，與 Lucky 6 沒有直接規則關係。 |
| 11 | `roundsSinceLastPair` | 距離最近一方前兩張 rank 相同的 pair 之後幾手；沒有則記 N | 描述最近是否出現前兩張同點數牌，以及距離現在多久。 | **其他 side bet 情境**：較適合未來 Perfect Pair 分析；在 Lucky 6 v1 是輔助描述而非命中條件。 |
| 12 | `currentStreakSigned` | 尾端連莊長度為正、連閒長度為負；Tie 不改變主路連續狀態 | 以一個帶方向的數字簡潔描述目前連莊或連閒的長度。 | **路勢情境**：行銷容易理解，但連勝本身不會令下一手 Lucky 6 更容易發生；不可稱為因果訊號。 |
| 13 | `chopRatio` | 相鄰非 Tie 結果中 B/P 轉換次數 / 可比較相鄰對數 | 描述莊閒結果是否頻繁交替；高值較常切換，低值較常延續。 | **路勢情境**：幫助區分連續型與交替型窗口，不是 Lucky 6 的直接條件。 |

### 對 Marketing 的整體說法

簡明說法可以是：

> 「系統把最近 N 手整理成 13 個可解釋的牌局特徵，涵蓋莊閒結果、點數差、補牌深度、牌面組成與路勢，再到相同窗口長度的歷史牌靴中找整體結構相近的窗口，查看那些窗口的下一手 Lucky 6 結果。」

這段話說明的是**檢索邏輯**，不是已證實的獲利或命中優勢。內部推薦可將各維度當成可調整的相似度訊號；若新增或移除維度，應記錄版本、重新產生向量，並比較新舊版本找到的鄰居及其 Lucky 6 標籤，讓 Marketing 知道推薦依據有何變化。

另需理解：13 維不是完全獨立的 13 個訊號。`bankerWinRatio`、`playerWinRatio`、`tieRatio` 三者相加為 1；`ratio4Cards`、`ratio5Cards`、`ratio6Cards` 也相加為 1。它們是方便解讀的特徵組，不代表每維都有獨立權重或貢獻。z-score 只統一尺度，不會自動證明維度有預測力。

`ratio4Cards + ratio5Cards + ratio6Cards = 1`（有完整牌面時）。對缺牌面或不完整窗口不補造數值，而是回傳資料不足；不把手動 B/P/T 局混入特徵窗口。

## 5. z-score 與向量 Index

### 5.1 正規化流程

對第 `j` 維特徵：

```text
z_j = (raw_j - mean_j) / std_j
```

- `mean_j`、`std_j` 由合成 seed 語料的 raw vectors 計算，保存為該語料版本的固定參數。
- 所有 corpus vectors 與 live query vectors 使用同一組 mean/std。不可對每個窗口各自算 mean/std。
- `std_j == 0` 時使用明確的安全處理（例如該維 z 設為 0 並記錄），不能除以零。
- 保存向量前後都可保留 raw features 以供 Debug；索引只讀正規化後的 `vector: [float, ...]`。
- 每次重新產生語料時，mean/std 與向量必須同批更新並附 `featureVersion` / `corpusVersion`，避免新舊座標系混用。
- z-score 只統一單維尺度，不保證 13 維對相似度的權重「統計上最優」。例如 4/5/6 張牌比例相加固定為 1，三維彼此相關；連勝、莊閒比例也有關聯。實作評估需用按 shoe 分組的 held-out 資料比較鄰居品質，並檢查 feature ablation/權重，不能把 z-score 當成命中率提升的證明。

### 5.2 cosine，而非 raw dot product

採用 `similarity: "cosine"`。Raw dot product 會同時受方向與向量長度影響，可能把「整體偏離平均很大」誤當成「特徵型態最相似」。若先把向量做 unit-length normalization，dot product 排名才會與 cosine 一樣；沒有需要為此多加一步。

Atlas 對 cosine 的 `vectorSearchScore` 是 0–1 範圍的 score，不應直接解讀成「命中機率」或統計信賴度。先前測試例子符合 `Atlas score = (1 + raw cosine) / 2` 的換算；UI 文案使用「Atlas 相似度分數」並提供排序，不宣稱「96% 機率」或「96% 真實相似」。實際上線時仍應以目前 Atlas 版本文件與測試確認分數解讀。

### 5.3 Index 定義

MongoDB Atlas collection：`side_bet_slices`。索引定義（向量欄位名 `vector`，維度必須等於 13）：

```json
{
  "name": "side_bet_vec_idx",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "vector",
        "numDimensions": 13,
        "similarity": "cosine"
      },
      { "type": "filter", "path": "corpusVersion" },
      { "type": "filter", "path": "windowLength" },
      { "type": "filter", "path": "datasetType" }
    ]
  }
}
```

`corpusVersion` filter 用來避免跨資料版本搜尋，`windowLength` filter 用來避免不同 N 的窗口互相比較，`datasetType` 用來隔離 demo fixture 與 Monte Carlo 分析語料。文件至少包含 `shoeId`/slice id、`windowStartRoundNo`、`windowLength`、`datasetType`、`featureVersion`、`corpusVersion`、raw features、13 維 `vector`、下一手 Lucky 6 結果與兩張/三張分類標籤。Query 的 `$vectorSearch.filter` 同時限制 `windowLength`、`corpusVersion` 與 `datasetType`。

此前 Atlas 測試已在獨立空資料庫成功建立 13 維 cosine index、插入人工 z-score 向量並執行 `$vectorSearch`：預期相似候選排名第一；臨時 collection 已刪除。這證明 Atlas 接受手工向量格式，但不代表實際 2,000 靴語料的預測品質已驗證。

## 6. 合成語料與 seed

新增 `backend/app/seed/seed_side_bet_history.py` 與 `make seed-sidebets`：

1. 使用同一個 baccarat dealer 模擬 2,000 靴，每靴使用獨立洗牌牌堆和 cut-card 規則。固定並保存 RNG seed，使相同 corpus version 可重現；不同 corpus version 要使用新 seed 並完整記錄。產生的切片標記 `datasetType="monte_carlo"`。
2. 對支援清單中的每個 N，在累積到完整連續 N 手後，抽取「過去 N 手」特徵並標記「緊接的下一手」Lucky 6 結果。
3. 不跨靴組窗口；切牌/新靴時重新開始窗口。
4. 先收集 raw features，計算各維 mean/std；再將所有切片轉為 13 維 z-score vector。
5. 把 slices、stats、feature/corpus version 寫入各自 collection；以批次寫入，seed 需具備可重跑/替換舊版的明確策略，不能混用不同 scaler 的向量。
6. 計算全語料庫 Lucky 6 基準率，至少分別保存 `banker_6_two_cards` 與 `banker_6_three_cards` 的機率，並保存總數/樣本數。
7. 建立/等待 Atlas vector index queryable，seed 完成時輸出切片數、各類命中數、基準率、mean/std 與 index 狀態。
8. 另用固定 demo seed 建立 `datasetType="demo"` 的可重播 demo shoe/query slices；逐手走同一個 dealer 與 feature encoder，對每個 N 使用 Monte Carlo 訓練資料擬合的 scaler。Demo query、demo slices、demo baseline 自成一組，不參與 Monte Carlo 的命中率統計或 holdout。

合成資料可驗證工程管線和 UI，但它不是「歷史名局」或真實賭場歷史資料。合成牌局是使用標準規則產生的 Monte Carlo 樣本；使用它估算出的 lift 不能宣稱為真實可投注優勢。

### Marketing demo 的可重現性

- 將語料 seed 固定並保存；Marketing demo 使用固定的查詢牌靴序列/round fixture，以及已版本化的 demo slices，確保每次都能重播同一個輸入並得到穩定 Top 10 結果。要呈現 lift 數值時，必須明確說明它是 demo fixture 的示意結果；如需展示 Monte Carlo 統計，切換至 `SIDE_BET_DATASET=monte_carlo`，並顯示其實際命中數與樣本數。
- fixture 必須由相同 baccarat dealer 規則產生或逐手通過 dealer 驗證。可挑選一個便於展示檢索流程的 query case，但要標記 `datasetType="demo"`，在 query 時明確指定 demo dataset；它與 Monte Carlo corpus 的 baseline、lift 評估和 holdout 完全分離。
- Demo 可以穩定展示「特徵如何形成、如何找到相似窗口、歷史窗口下一手結果如何彙總」；不可保證永遠出現某個 Lucky 6 lift 數值，也不可把固定展示案例說成市場上真實可重複的投注提升。
- 每次 seed 輸出並保存 `seedId`、規則版本、feature/corpus version、datasetType、各 N 的窗口數和 Lucky 6 baseline，方便重現與稽核。

## 7. 即時 Side Bet 搜尋與 lift

新增 `backend/app/services/side_bet_engine.py`：

1. 在 round N 完成後，取最近 `SIDE_BET_WINDOW` 手且全部有牌面資料的窗口；若未滿 N 手、包含手動局、跨靴或資料缺漏，回傳 `insufficientData=true`。
2. 計算 raw features，使用對應 `windowLength` 與 corpus version 的固定 mean/std，產生 13 維 query vector。
3. `$vectorSearch` 查詢 `side_bet_slices`，`path="vector"`、`index="side_bet_vec_idx"`、`limit=10`，filter 為目前 `windowLength`、`corpusVersion` 和 `datasetType`；`numCandidates` 設為可配置且大於 limit。為避免重疊窗口造成同一歷史靴壟斷鄰居，搜尋時要 over-fetch，再按 `shoeId` 去重或限每靴最多一個鄰居；不足 10 個不同靴時回報實際 neighborCount，不假裝有 10 個獨立樣本。
4. Top 1 的 Atlas score 顯示為相似度分數；Top 10 依其下一手標籤計算鄰域觀察命中率。v1 分開計算兩張 6 點勝與三張 6 點勝，避免不同賠率的事件混成一個指標。
5. `lift = neighborhoodRate / corpusBaselineRate`。baseline 為 0、鄰居數不足或樣本數太小時，不輸出無限/誤導數字，改顯示「樣本不足」。結果同時帶上 `n`、命中數與原始比率。
6. 如果顯示投注報酬估算，另列出賠率規則與樣本數；若為淨賠率 `r:1`，單位下注的示意期望淨值為 `p*r - (1-p)`。不得把 Atlas score 當成 `p`。
7. 寫入 `side_bet_matches`，並讓 API 明確標示 `predictionForRoundNo = sourceRoundNo + 1`，避免把已開結果誤當預測。

Top 10 是小樣本，鄰域命中率波動會很大。UI 必須顯示 `hits / n` 與「合成資料/探索性統計」提示；未來若要做穩定估計，需擴大鄰域、相似度加權/校準、提供信賴區間，並用獨立 holdout 模擬集評估。

## 8. API、WebSocket 與資料結構

### 新增結果 schema

`SideBetMatchResult` 建議欄位：

- `shoeId`, `sourceRoundNo`, `predictionForRoundNo`, `triggeredAt`
- `windowLength`, `insufficientData`, `reason`
- `topSimilarityScore`, `neighborCount`
- `lucky6TwoCardHits`, `lucky6TwoCardRate`, `lucky6TwoCardBaseline`, `lucky6TwoCardLift`
- `lucky6ThreeCardHits`, `lucky6ThreeCardRate`, `lucky6ThreeCardBaseline`, `lucky6ThreeCardLift`
- `corpusVersion`, `featureVersion`

新增 `GET /api/shoes/{shoe_id}/side-bet-matches`。現有 round ingestion/randomize 完成後，如有足夠牌面資料，呼叫 side-bet engine，將資料合併進 WebSocket payload。手動 B/P/T 流程不補造牌面。

## 9. 前端計畫

- 擴充 `frontend/src/api/types.ts`：Card、round card metadata、SideBetMatchResult。
- `frontend/src/api/client.ts`：新增歷史 Side Bet 結果 API。
- 新增 `CardFaceDisplay.tsx`：顯示最新自動發牌 round 的莊/閒牌、補牌、點數與 B/P/T 結果；手動局顯示「沒有牌面資料」。
- 新增 `SideBetPanel.tsx`：顯示下一手目標局號、Top 1 Atlas score、Top 10 命中數/樣本數、兩張/三張 Lucky 6 的基準率/鄰域率/lift；資料不足時顯示明確原因。
- `SimulatorPage.tsx`：Side Bet panel 放於右欄現有下三路推薦之後；牌面顯示靠近 round input/history。
- 文案不使用「機率飆升」等無校準保證的確定性描述；顯示「合成相似窗口的觀察率」和樣本數。

## 10. 測試與驗收

### Backend 單元測試

- Baccarat dealer：牌值/mod-10、natural、閒家補牌、莊家補牌表所有分支、B/P/T、牌堆不重複與 cut-card 行為。
- Side bet labels：Lucky 6 僅莊贏且莊家最終 6 點；分清莊家兩張/三張；Tie 或莊輸不命中。
- 特徵編碼：13 維順序固定、card ratios 加總為 1、margin 定義、face-card density、tie/pair gap、streak/chop 邊界。
- z-score：seed 與 query 使用同一 stats、零標準差處理、維度與 index 一致。
- 搜尋統計：Top 10 次數、命中率、baseline/lift、零 baseline、樣本不足、side bet 結果標記為下一手。
- API：手動紀錄會回 `insufficientData`，不產生假的 card data。

### Atlas 整合測試

- 在可建立新 Vector Search index 的測試叢集/測試資料庫建立 13 維 cosine index。
- 插入具有已知相似排序的人工向量，確認 `$vectorSearch` 回傳排序和 metadata。
- 測試需清理臨時 collection；不可覆蓋既有 pattern index。

### Frontend / E2E

- `npm run build`、backend `pytest`。
- seed 合成語料後跑隨機牌局，確認 cards/totals/result 一致、Side Bet 對每個支援的 N 都在累積 N 手後產生下一手結果、切換 .env 的 N 後只取對應 windowLength 的 slices/stats，手動 B/P/T 穿插後資料不足直到重新累積 N 手完整牌面。
- 統計 2,000 靴的 B/P/T 分布、Lucky 6 分類命中率作為 dealer sanity check；不得用單次模擬宣稱精確吻合理論機率。
- 以整靴為單位切出 holdout shoes，避免同一靴相鄰重疊窗口同時出現在 corpus 與評估集；比較實際 Top-K 上的 Lucky 6 命中率、baseline、lift 和不確定區間。展示用 fixture 不得進入 holdout 或 production corpus。

## 11. 實作階段

1. **Phase 1 — 牌面模型與 dealer**：新增 Card/Round 欄位、8 副牌狀態、補牌規則、Lucky 6 標籤、randomize 改由真牌計算 B/P/T，並補足 dealer 單元測試。
2. **Phase 2 — 特徵與語料**：新增 13 維 encoder、N/dataset 專屬 mean/std 版本化、支援 N=1/3/5/10 的 2,000 靴 seed、固定 demo fixture seed、更新 `.env.example`/`config.py`、stats/slices collection、13D cosine index 及 filter。
3. **Phase 3 — 即時搜尋/API**：Top 10 `$vectorSearch`、Top 1 score、分兩張/三張統計 lift、資料不足處理、DB/API/WebSocket。
4. **Phase 4 — 前端**：牌面卡、Lucky 6 panel、types/client/SimulatorPage wiring。
5. **Phase 5 — 驗收**：pytest、frontend build、Atlas 整合測試與隔離 server E2E。

## 12. Demo case：N=10 時從窗口到 Lucky 6 鄰域統計

以下是**可手動核對計算邏輯的 demo fixture 案例**。牌局牌面以標準發牌規則構造；mean/std 與 Atlas 鄰居資料是示例，不是由已 seed 的 2,000 靴實際跑出的結果，也不表示真實預測能力。此 fixture 應標記為 demo-only，不納入正式 Monte Carlo baseline。

### 12.1 當前窗口與 feature extraction

當前靴最近 N=10 手結果假設為：

```text
Round:       1  2  3  4  5  6  7  8  9 10
Result:      B  P  B  B  B  B  P  B  B  B
Signed margin:+3 -6 +1 +4 +5 +2 -3 +8 +3 +2
Total cards:  4  5  6  4  6  6  5  4  5  6
```

這是一組按標準補牌規則逐手發出的合法牌面示例。完整牌面如下（總點數均取 mod 10）：

| Round | Banker cards → total | Player cards → total | Result | Margin | 總張數 |
|---:|---|---|:---:|---:|---:|
| 1 | 5♥, 4♣ → 9 | 6♠, 10♦ → 6 | B | +3 | 4 |
| 2 | Q♦, Q♣, K♦ → 0 | 6♠, J♠ → 6 | P | -6 | 5 |
| 3 | A♥, Q♦, 6♦ → 7 | 2♣, 8♥, 6♠ → 6 | B | +1 | 6 |
| 4 | 6♥, 2♥ → 8 | 4♠, J♠ → 4 | B | +4 | 4 |
| 5 | 9♠, 3♥, 3♠ → 5 | 8♥, 3♠, 9♦ → 0 | B | +5 | 6 |
| 6 | 3♥, J♦, 5♦ → 8 | K♣, 10♣, 6♦ → 6 | B | +2 | 6 |
| 7 | 7♥, 5♣, A♣ → 3 | J♠, 6♥ → 6 | P | -3 | 5 |
| 8 | 5♣, 3♥ → 8 | J♣, 10♠ → 0 | B | +8 | 4 |
| 9 | 10♥, 5♦ → 5 | 6♣, 6♦, K♣ → 2 | B | +3 | 5 |
| 10 | 5♠, 9♣, 2♣ → 6 | 3♣, 7♥, 4♠ → 4 | B | +2 | 6 |

其他由牌面可算出的特徵：51 張總發牌中有 15 張為 10/J/Q/K；窗口內沒有 Tie，`roundsSinceLastTie=10`；Round 9 閒家前兩張為 6♣/6♦，pair 之後只有 Round 10 一手，所以 `roundsSinceLastPair=1`；尾端連莊長度 3；相鄰非 Tie 結果 9 組中有 4 次轉換。

由此得到部分/全部 raw features：

| 特徵 | 計算 | Raw 值 |
|---|---|---:|
| bankerWinRatio | 8 / 10 | 0.80 |
| playerWinRatio | 2 / 10 | 0.20 |
| tieRatio | 0 / 10 | 0.00 |
| avgMargin | (3-6+1+4+5+2-3+8+3+2) / 10 | 1.90 |
| marginVolatility | 10 個 signed margin 的 population std | 約 3.75 |
| ratio4Cards | 3 / 10 | 0.30 |
| ratio5Cards | 3 / 10 | 0.30 |
| ratio6Cards | 4 / 10 | 0.40 |
| faceCardDensity | 15 / 51 | 約 0.2941 |
| roundsSinceLastTie | 窗口內無 Tie，截斷到 N | 10 |
| roundsSinceLastPair | 最近 pair 在 Round 9，之後 1 手 | 1 |
| currentStreakSigned | 尾端 B B B | +3 |
| chopRatio | 4 / 9 | 約 0.4444 |

牌張數檢查：3 手 × 4 張 + 3 手 × 5 張 + 4 手 × 6 張 = 51 張；牌數比例總和 `0.30 + 0.30 + 0.40 = 1.00`。

### 12.2 對 raw features 做 z-score

假設 seed 產生的 corpus stats 中，前四維（僅為便於展示的示意 stats）是：

| 特徵 | mean | std |
|---|---:|---:|
| bankerWinRatio | 0.459 | 0.158 |
| playerWinRatio | 0.446 | 0.157 |
| tieRatio | 0.095 | 0.093 |
| avgMargin | 0.000 | 2.800 |

逐維計算 `z = (raw - mean) / std`：

```text
bankerWinRatio: (0.80  - 0.459) / 0.158 =  2.158
playerWinRatio: (0.20  - 0.446) / 0.157 = -1.567
tieRatio:       (0.00  - 0.095) / 0.093 = -1.022
avgMargin:      (1.90  - 0.000) / 2.800 =  0.679
```

其他 9 維也用各自 corpus mean/std 同樣計算，最後形成有固定順序的 13 個 float，例如：

```json
{
  "featureVersion": "sidebet-v1",
  "vector": [2.158, -1.567, -1.022, 0.679, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
}
```

這段只用前四維的示範 z 值，並以 0 填充其餘維度來展示合法 13 維文件形狀；實際系統會按其餘 9 維各自的 mean/std 算出真實值，不會把它們固定填 0。Seed 歷史切片與 live query 必須使用同一組 mean/std 和相同維度順序。

### 12.3 `$vectorSearch` 找 Top 10

把 query vector 送到 `side_bet_slices.vector` 的 13 維 cosine index。假設 Top 10 返回的 Top 1 Atlas score 為 `0.91`：這是 **Atlas 相似度分數**，不是「91% Lucky 6 機率」、不是勝率，也不應直接說成「91%真實相似」。鄰居要按不同歷史 shoe 去重，Top 10 指最多 10 個不同 shoe 的切片。

Top 10 下一手結果假設為：

| 鄰居數 | 下一手 Lucky 6 類別 |
|---:|---|
| 2 | 莊家兩張 6 點勝 (`banker_6_two_cards`) |
| 1 | 莊家三張 6 點勝 (`banker_6_three_cards`) |
| 7 | 未中 Lucky 6 |

所以：

```text
兩張命中率 = 2 / 10 = 20%
三張命中率 = 1 / 10 = 10%
總命中率   = 3 / 10 = 30%
```

### 12.4 對 baseline 算 lift，並正確解讀

再假設整個合成 corpus 的 baseline（**僅為演示假設**）為：

```text
兩張 Lucky 6 baseline = 2%
三張 Lucky 6 baseline = 1%
```

則：

```text
兩張 lift = 20% / 2% = 10x
三張 lift = 10% / 1% = 10x
```

建議 UI 顯示：

```text
下一手（Round 11）Lucky 6 探索性統計
最相似歷史窗口：Atlas score 0.91
相似窗口樣本：10 個不同歷史靴（兩張命中 2/10；三張命中 1/10）
Corpus baseline：兩張 2%；三張 1%（以上均為示例值）
鄰域觀察 lift：兩張 10x；三張 10x
注意：n=10 樣本很少；合成歷史資料的 lift 不代表真實投注優勢。
```

**這個案例的判斷重點**：

1. 牌面先按 baccarat 規則決定 totals 與 B/P/T；不可以先抽 B/P/T 再任意拼牌。
2. Lucky 6 只看「莊贏且莊家最終 6 點」，並按莊家兩張/三張分開統計。
3. 10 手 raw features 先套 corpus 固定 mean/std，再查向量；不能把 raw 值或每窗口自算的 z 值直接混入索引。demo fixture 使用獨立資料集/標記，不能污染正式基準率。
4. Atlas score、Top 10 命中率、lift 是三個不同概念；Top 10 的 `2/10` 不代表真實機率就是 20%。

## 13. 尚待實作時確認的細節

- Lucky 6 賠率「1 賠 12 / 1 賠 20」的淨賠率或總返還慣例。
- cut-card 位置/到切牌後 UI 如何引導建立新靴。
- 是否把 `bankerPair` 等所有 v2 欄位都存入 Round，或由 cards 按需計算。
- 13 維 feature/corpus version 的重建與舊資料清理策略。
- Top 10 太小時顯示原始比例還是擴大鄰域；v1 預設仍按已選定的 Top 10 展示，但必須呈現 n/hits 與不確定性。
