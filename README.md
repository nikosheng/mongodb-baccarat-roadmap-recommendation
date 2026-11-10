# Baccarat Vector Match Demo

百家樂路數預測 Demo — 基於 **MongoDB Atlas Vector Search** + **Voyage AI embedding**
的純語義向量匹配系統。核心設計理念、架構決策與取捨請參考本次對話討論紀錄;這裡只記錄
如何啟動與操作。

## 核心架構一句話

把路數(pattern)和場上即時局數窗口都翻譯成**固定格式的英文語義描述**
(`describe_window_in_nl`,見 `backend/app/services/window_text.py`),再用
**Voyage `voyage-4`** embedding 成 1024 維向量,存入 **MongoDB Atlas
Vector Search** 索引,實時用 `$vectorSearch` 做語義相似度排序 —— 全程沒有
任何 if-else 規則引擎做匹配判斷。

**下三路(大眼仔 / 小路 / 蟑螂路)是完全獨立的第二組 vector search**:從大路
衍生出三條路的符號(`backend/app/services/derived_roads.py`),翻譯成另一組
固定格式英文描述(`describe_derived_in_nl`),用同一顆 Voyage 模型 embed 後存入
**第二個獨立的 collection + Atlas Vector Search 索引**(`derived_patterns` /
`derived_pattern_vec_idx`),避免兩種語義空間互相污染 cosine 排名。

## 設計流程與原理(下三路功能從 0 到 1)

這一節完整記錄下三路功能的設計推演過程 —— 不只是「做了什麼」,而是「為什麼
這樣做」與「中間試過哪些方案、為什麼放棄」。想理解整個系統的設計哲學,從這裡
開始讀。

### 1. 問題拆解:下三路到底是什麼

百家樂的「下三路」(大眼仔 Big Eye Boy、小路 Small Road、蟑螂路 Cockroach Pig)
不是獨立的隨機事件,而是**大路的確定性函式**——給定同一段大路,三條下三路的
每一個紅/藍符號都是可以精確算出來的,沒有任何隨機性或模糊地帶。這個特性決定了
整個設計的起點:

- 大路本身已經是「蓋牌規則」(一局一局疊上去,到底後拖拽),下三路是在這個網格
  上做「跨度比較」(比較第 N 列跟第 N-k 列的長度/整齊度),k=1/2/3 分別對應
  大眼仔/小路/蟑螂路。
- 因為是確定性函式,**大路的畫法如果有誤差,下三路會整組錯誤**——這也是為什麼
  第一步必須先把大路的畫法訂正為賭場正統規則,而不是直接套用專案原本「簡化版」
  的畫法。

### 2. 大路畫法的訂正:為什麼「到底後拖拽」很重要

專案原本的 `BigRoad.tsx` 用一個簡化規則:同色結果畫到第 6 列後,下一個同色
結果直接跳到下一欄的「第 6 列」位置,但並未真正延續「同一條龍」的語義。賭場
正統規則是:

> 到達第 6 列(row = 5,0-indexed)之後,同色結果**不再往下**,而是**沿著
> 第 6 列向右拖曳**,每一個新同色結果佔用一個新的欄位(但仍然算在同一條
> 龍上),直到遇到不同結果才真正開新欄、新龍。

這個差異看起來很小,但對下三路是致命的:下三路的核心運算是「比較欄位高度
(該欄位總共放了幾顆珠)」,如果拖曳期間的欄位高度算錯(算成 6 顆而不是正確
的 1 顆),所有下三路的紅/藍判斷都會連帶出錯。因此實作的第一步(Phase 1)是
重寫 `layoutBigRoad`(前端 `lib/roads.ts`)與新增 `compute_big_road`(後端
`derived_roads.py`),並且**兩邊必須是同一套演算法**——這點用
`tests/fixtures/road_cases.json`(29 組涵蓋長龍/斷龍/和局/拖曳邊界的測資)
在 Python 與 TypeScript 兩邊分別跑過,逐欄逐列比對完全一致才算過關。

### 3. 下三路符號計算原理

給定大路的 B/P 珠(忽略和局)依序排列,對每一顆新珠在欄位 `col`、列數
`row`(皆 0-indexed)做以下判斷(`offset` = 1/2/3 對應大眼仔/小路/蟑螂路):

```
令 left1 = col - offset, left2 = col - offset - 1

若 left1 < 0:          # 歷史不夠長,還不能判斷
    尚無符號

否則若 row > 0:         # 這顆珠是「延續同一欄」的情況
    若 left1 欄在 row 這一列有珠:
        紅
    否則:
        藍

否則(row == 0,這顆珠「開了新欄」):
    若 left2 < 0:
        尚無符號
    否則:
        比較 left1 欄高度 跟 left2 欄高度
        相等 → 紅
        不相等 → 藍
```

注意:row > 0 時要檢查實際格位,不能用珠數推算列位置。拖尾欄可能只有一顆珠,
但它位於 row=5;row == 0 時才比較兩欄的珠數。

直覺理解:「紅」代表「跟歷史上同樣跨度的欄位比,結構是對稱/整齊的」,「藍」
代表「不對稱」。這也是為什麼大眼仔最先開始算(只需要 2 欄歷史)、小路次之
(3 欄)、蟑螂路最晚(4 欄)——跨度越遠,需要的歷史越長。

算出紅藍符號序列後,**用跟大路完全一樣的「向下延伸、到底後拖拽」規則**把這些
符號畫成自己的一條路(所以大眼仔/小路/蟑螂路的畫面也會有長龍、拖拽現象)。

### 4. Pattern 儲存設計:三個方案的取捨

下三路 pattern library 要怎麼存「情境」?討論過三個方案:

| 方案 | 做法 | 優點 | 缺點 |
|---|---|---|---|
| A(大路反推) | 存一段 B/P/T 大路序列,runtime 時系統自動算出下三路再 embed | 跟大路 pattern 的儲存方式一致,語義空間保證對齊 | 「三路齊紅」這種純符號概念,要刻意構造出一段恰好產生這個結果的大路序列,很不直覺 |
| B(直接存符號)✅ | 直接存三路的 R/B 字串 `canonicalRoads.{bigEye,small,cockroach}` | Admin 表單直接填三組色串,語義直觀;「三路齊紅」就是 `{R,R,R}`,所見即所得 | 需要保證 seed 與 runtime 走同一個 `describe_derived_in_nl`,否則兩邊語義空間會不對齊(已用程式碼結構保證) |
| C(混合) | 預設用大路反推,但允許 admin 覆寫符號 | 最彈性 | schema 和 UI 最複雜,且「反推值」與「覆寫值」不一致時難以除錯 |

最終選了 **方案 B**。原因:下三路的 5 大類問路情境(齊色/連龍/單跳/互補/反彈)
本質上全部是「符號本身的結構」,不是「符號是哪一段大路造成的」——大路的
context 對於這些 pattern 的語義完全不重要,所以直接存符號反而更貼近領域
語言,也更容易在 Admin UI 上編輯。

### 5. 「下三路語義空間太小」的質疑與驗證過程

提案階段曾經假設「下三路只有 R/B 兩種符號,embedding 語義空間可能比大路小,
所以 threshold 要調低一點」。這個假設**被要求重新驗證**,過程記錄如下(也是
整個設計流程中最關鍵的除錯迭代):

**第一次說法的錯誤**:「符號少 → embedding 空間小」這個因果鏈其實是直覺猜測,
沒有實測,而且把「embedding 的輸入(英文 NL 文字)」跟「底層符號系統(R/B)」
混為一談——embedding 針對的是文字,不是符號本身。

**實際驗證方法**:寫了 `backend/app/seed/calibrate_derived.py`,對 7 個
預設 pattern 真的呼叫 Voyage 做 pairwise cosine 相似度計算,而不是憑空猜測。

**v1(扁平逐路描述)的結果**:
```
min=0.9300 max=0.9996 mean=0.9635
```
所有 pattern 兩兩之間的 cosine 都在 0.93 以上,幾乎無法區分——證實了「可能
有問題」的直覺,但原因跟「符號少」無關,而是**模板太制式化**:每個 pattern
的描述都是「XX 路: 最新符號 Y; 目前 Z streak 長度 N; 整體 W」這種重複度極高
的句型,只有少數幾個字不同,voyage 的向量自然被這些大量重複的詞彙拉在一起。

**v2a(單一分類 headline)的結果**:嘗試用「SIGNAL CLASSIFICATION: ...(X
pattern)...」這種分類式開頭句,min 降到 0.80,但仍有 0.80~0.96 的碰撞——
原因是所有 archetype 共用同一個開頭句式("SIGNAL CLASSIFICATION:"),這個
共同前綴本身又製造了新的相似度底噪;另外還發現一個邏輯 bug:canonical
example 若剛好讓三路最新符號都相同(例如「連龍」的例子恰好三路都是紅),
會被誤判成「齊色」archetype,造成語意碰撞。

**v2b(仿造大路的多維度 bucket)的結果**:參考 `window_text.py` 對大路成功
的「每個維度都輸出一個 bucket 短語」做法,改成「5 個訊號維度,每個都明確寫
present/absent」。結果反而**更差**(min 升到 0.92)——因為大路的每個維度
(長度/強弱勢/當前狀態/最長連/交替程度...)永遠都會有一個「有意義的值」,
但下三路的 5 個 archetype 通常只有 1 個會是 present,其餘 4 個全部輸出幾乎
相同的 "absent" 樣板句,反而讓「樣板相似度」主宰了整段文字。

**v3(目前版本)的做法**:放棄分類式開頭句的共用結構,改成**每個 archetype
完全不同的敘事開頭詞彙**(例如 "Full house: ..." / "Dragon alert: ..." /
"Metronome rhythm: ..." / "Split vote: ..." / "Overdue bounce: ..."),移除
逐路的樣板化描述,改在句尾直接附上原始符號字串("Raw symbols — Big Eye
Boy: RRRRRR, ...")保留細節鑑別力。同時也修正了 v2a 發現的「canonical
example 誤觸發其他 archetype」的 bug(重新設計 7 個預設 pattern 的符號,
確保每個都乾淨地只命中自己的 archetype)。結果:

```
cross-archetype:  min=0.5679 max=0.7997 mean=0.6950   (排除 3 個「互補」變體彼此的配對)
```

跨 archetype 最高只有 0.80,相較 v1 的 0.93 起跳,是數量級的改善。

**最終校準方法**:因為下三路只有「3 路 × 2 色」的狀態空間,任何輸入在
pigeonhole 原理下必定落入 5 個 archetype 之一(不存在真正「無意義/混亂」的
輸入),所以原本設計的「bogus query 應該全部低分」這個測試概念本身是錯的——
隨便構造的「亂數」符號組合,最終都會巧合地落在某個合法 archetype 裡(例如
隨機 3 路最新符號湊出 2 紅 1 藍,就是合法的「互補」訊號)。發現這點後,
`calibrate_derived.py` 改成測「真實情境 recall」:針對每個 archetype 構造
一個 12 symbol、刻意避開誤觸發其他 archetype 的真實情境,驗證 top-1 是否
正確命中對應 pattern:

```
✓ scenario-for-三元及第   -> top1=三元及第   (0.8571) gap=0.1224
✓ scenario-for-下三路連龍  -> top1=下三路連龍  (0.8812) gap=0.1717
✓ scenario-for-下三路單跳  -> top1=下三路單跳  (0.8980) gap=0.2864
✓ scenario-for-三路互補    -> top1=三路互補    (0.9189) gap=0.0031 (互補變體間的小 gap 是預期行為)
✓ scenario-for-逢藍知返   -> top1=逢藍知返    (0.8921) gap=0.1932
```

5/5 全部正確,`DERIVED_PATTERN_MIN_SCORE` 最終取
`max(真實情境 recall 下限 0.8571 - 0.05, cross-archetype 上限 0.7997 + 0.02)
≈ 0.82`——巧合地跟大路原本的 `PATTERN_MIN_SCORE=0.82` 一樣,但這次是**用數據
算出來的**,不是沿用的巧合假設。

**結論(誠實的自我修正)**:一開始「語義空間小」的說法不精確;真正的風險是
「NL 模板太制式化導致 embedding 鑑別力不足」,解法不是調低 threshold(那只是
把症狀藏起來),而是重寫模板讓不同 archetype 之間有真正的詞彙差異。

### 6. Debug 整合設計原理

原本大路有獨立的 `/debug` 頁面,下三路加進來後,若比照辦理會變成「兩條獨立
的除錯動線」,使用者要分別去兩個地方核對同一個 round 的大路/下三路資訊。因此
改為**單一折疊式 `DebugInspector`**,固定掛在 Simulator 主頁下方:

- 折疊預設收合,不佔用首屏空間,快捷鍵 `d` 可直接展開/收合。
- 展開後用同一個 round selector 驅動「大路 Debug」「下三路 Debug」兩個分頁,
  兩邊永遠對應同一個 round,不會出現「大路在看第 10 局、下三路在看第 15 局」
  這種不同步的情況。
- 渲染邏輯從原本的 `DebugPage.tsx` 拆成 `BigRoadDebugView.tsx` /
  `DerivedDebugView.tsx` 兩個純展示元件,方便未來如果要做獨立視窗版本
  (例如投影用)可以直接複用。

### 7. 為什麼下三路是完全獨立的 collection,而非共用 + filter

技術上可以把下三路 pattern 存進同一個 `patterns` collection,用一個
`kind: "big" | "derived"` 欄位 + filter 做區分,省掉一個 collection 跟一個
索引。但沒有這樣做,原因:

- 兩邊的 NL 描述文字風格與語彙完全不同(大路談「長度/優勢方/連勝/交替」,
  下三路談「三路對齊/龍/節拍/互補/反彈」),混在同一個向量空間裡,即使用
  filter 限制搜尋範圍,寫入與讀取的心智模型也會混淆(例如校準腳本要抓「全部
  大路 pattern」時得額外記得加 filter)。
- 兩邊各自有獨立的版本控制(`NL_DESCRIBER_VERSION` vs
  `NL_DERIVED_DESCRIBER_VERSION`)與獨立閾值(`PATTERN_MIN_SCORE` vs
  `DERIVED_PATTERN_MIN_SCORE`),分開的 collection 讓這些版本/閾值的套用
  範圍更明確,不會改了一邊的版本意外影響到另一邊的查詢結果。
- 這本來就是使用者明確要求的架構(「創建另外一個 vector search」),保留
  獨立性也更符合這個 demo 專案本身想展示「向量搜尋如何劃分語義空間」的教學
  目的。

## 專案結構

```
backend/            FastAPI + Motor + Voyage + Azure OpenAI
  app/
    services/
      window_text.py        <- 語義橋(大路):describe_window_in_nl()(唯一真相來源)
      derived_roads.py       <- 大路→下三路衍生計算 + 語義橋:describe_derived_in_nl()
      embedder.py            <- Voyage embedding client(大路/下三路共用)
      match_engine.py         <- 大路 vector search 匹配邏輯
      derived_match_engine.py <- 下三路(第二組)vector search 匹配邏輯
      pattern_service.py      <- 大路 Pattern CRUD + embedding 生命週期
      derived_pattern_service.py <- 下三路 Pattern CRUD + embedding 生命週期
      nl_pattern.py            <- Azure OpenAI 自然語言解析(大路)
      nl_derived_pattern.py    <- Azure OpenAI 自然語言解析(下三路)
      broadcaster.py           <- WebSocket 連線管理
    routers/
      shoes.py                 <- 靴/局數/大路+下三路 roads/問路預留
      patterns.py               <- 大路 pattern CRUD
      derived_patterns.py       <- 下三路 pattern CRUD
      debug.py                  <- 大路 + 下三路 vector search 全透明化 endpoint
      ws.py                      <- WebSocket endpoint
    seed/
      default_patterns.py       <- 10 個預設大路路數定義
      default_derived_patterns.py <- 7 個預設下三路路數定義(5 大類問路情境)
      run_seed.py                 <- 一鍵 seed 腳本(大路 + 下三路)
      calibrate_derived.py        <- 下三路 vector search 校準工具(開發用,非 production 流程)
  tests/
    test_window_text.py       <- describe_window_in_nl 單元測試
    test_derived_roads.py      <- 大路/下三路計算 + describe_derived_in_nl 單元測試
    test_derived_match_engine.py <- 下三路 match engine 單元測試(mock DB/embedder)
    fixtures/road_cases.json    <- Python↔TypeScript 大路/下三路演算法對照 fixture

frontend/            React + Vite + TypeScript + Tailwind v4
  src/
    lib/roads.ts              <- 大路 + 下三路佈局演算法(前端版,與後端 derived_roads.py 保持一致)
    pages/
      SimulatorPage.tsx        <- 賭桌模擬器(大路 + 下三路 + 輸入 + 雙推薦排行榜 + Debug Inspector)
      AdminListPage.tsx         <- 大路 Pattern 後台列表
      PatternEditorPage.tsx     <- 大路表單模式 + 自然語言模式
      DerivedAdminListPage.tsx   <- 下三路 Pattern 後台列表
      DerivedPatternEditorPage.tsx <- 下三路表單模式 + 自然語言模式
    components/
      simulator/
        BigRoad.tsx             <- 大路 canvas(賭場正統 row=5 拖拽規則)
        BigEyeRoad.tsx / SmallRoad.tsx / CockroachRoad.tsx <- 下三路 canvas
        DerivedRoadsPanel.tsx    <- 下三路容器(折疊)
        MatchRanking.tsx / DerivedMatchRanking.tsx <- 大路/下三路推薦排行榜
        DebugInspector.tsx       <- 整合進 Simulator 主頁的折疊式 Debug 面板
      debug/
        BigRoadDebugView.tsx / DerivedDebugView.tsx <- Debug Inspector 的兩個分頁內容
    stores/useAppStore.ts       <- Zustand 全局狀態(含 latestDerivedMatch、debugExpanded)
    hooks/useWebSocket.ts        <- WebSocket 連線 hook(同時推送大路/下三路 match)
```

## 快速啟動(本地開發,不用 Docker)

專案根目錄提供 `Makefile`，可簡化常用操作：

```bash
make setup             # 首次設定：建立 .env (若不存在) 並安裝依賴
# 編輯 .env，填入 Atlas URI 和 Voyage API key，並設定 USE_MOCK_EMBEDDER=false
make check-env         # 驗證 Atlas/Voyage 設定
make seed              # 重新產生並寫入預設 patterns 的 Voyage embeddings(大路 10 個 + 下三路 7 個)
make calibrate-derived # (開發用)重新校準下三路 vector search 的 DERIVED_PATTERN_MIN_SCORE
make dev               # 同時啟動後端和前端
make stop              # 優雅停止前後端服務
make test              # 後端 pytest + 前端 production build
```

也可分開啟動服務：`make api` 和 `make web`。查看所有指令請執行 `make help`。
`make stop` 會停止 Docker Compose 前後端服務，並正常終止本專案在 8000/5173 port 上的本機服務程序。
`make seed` 會更新預設的大路 10 個 + 下三路 7 個 patterns，不會刪除自訂 patterns 或遊戲紀錄。

### 1. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`,填入:
- `MONGO_URI`:您的 Atlas Cloud M10+ 集群連線字串(支援 Vector Search)
- `VOYAGE_API_KEY`:Voyage AI API key
- `AZURE_OPENAI_*`:Azure OpenAI 的 endpoint / key / deployment / api version

> **沒有這些 key 也能跑**:把 `USE_MOCK_EMBEDDER=true` 和
> `USE_MOCK_LLM=true` 設成 true,系統會用確定性的假向量/假 LLM 解析器跑通
> 整條流程(含真正的 Mongo `$vectorSearch` 查詢),只是匹配結果不具語義
> 準確度,僅供驗證管線是否正常運作。

### 2. 啟動 MongoDB(若沒有 Atlas Cloud,可用本地 atlas-local)

```bash
docker run -d --name baccarat-mongo -p 27018:27017 mongodb/mongodb-atlas-local:latest
```
並設定 `.env` 的 `MONGO_URI=mongodb://localhost:27018/?directConnection=true`

### 3. 安裝並啟動後端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Seed 10 個預設 pattern(含建立 Atlas Vector Search 索引)
python -m app.seed.run_seed

# 跑單元測試
pytest tests/ -v

# 啟動
uvicorn app.main:app --reload --port 8000
```

### 4. 安裝並啟動前端

```bash
cd frontend
npm install
npm run dev
```

打開 http://localhost:5173

## 使用 Docker Compose

```bash
cp .env.example .env   # 填好 key,或設 USE_MOCK_* = true

# 方案 A:使用您自己的 Atlas Cloud 集群(.env 的 MONGO_URI 直接指向雲端)
docker compose up --build

# 方案 B:使用本地 mongodb-atlas-local(完全離線)
# .env 設定 MONGO_URI=mongodb://mongodb:27017/?directConnection=true
docker compose --profile local-mongo up --build

# 任一方案啟動後,執行一次 seed:
docker compose --profile tools run --rm seed
```

## Demo 腳本(5 分鐘)

| 步驟 | 動作 | 展示重點 |
|---|---|---|
| 1 | 開 `http://localhost:5173/`,系統自動開一靴 | 乾淨大路 + 下三路面板(局數不足時顯示提示) |
| 2 | 連點 6 次「莊 B」(或按鍵盤 `B`) | 大路畫出長紅柱,排行榜彈出「長莊連龍」 |
| 3 | 第 7 盤點「閒 P」 | 排行榜 top1 變「長莊斷龍」,score 接近 1.0(若用真 Voyage key,會是高 cosine 而非精確符號匹配) |
| 4 | 繼續輸入到第 12~15 局左右 | 下三路(大眼仔/小路/蟑螂路)開始出現符號,下方「下三路推薦排行榜」開始匹配 |
| 5 | 展開頁面下方「🔍 Debug Inspector」(或按 `d`) | 切兩個分頁看大路/下三路各自的 cosine 完整排名、語義描述文本、gap 分析 |
| 6 | 切到 `/admin/new`,選「自然語言模式」 | 輸入「連三莊之後連三閒,下盤多半出莊」,觀察分步進度文字,解析 + embedding 預覽 + 相似度檢查全流程 |
| 7 | 切到 `/admin/derived/new` | 下三路版本的 NL 解析 + 三路色串表單,流程相同但語義空間完全獨立 |
| 8 | 儲存新 pattern,回 `/` 繼續擲 | 新 pattern 立即對後續局數生效 |

## 關鍵設計決策快速參考

完整的推演過程與數據見上方「設計流程與原理」一節,這裡只列結論方便查閱:

- **Window 策略(大路)**:最小 4 盤起觸發匹配,最大 10 盤,長度可變(不需要 padding)
- **匹配閾值(大路)**:`PATTERN_MIN_SCORE=0.82`;低於閾值仍顯示 top1,但標記「信心低」
- **語義橋版本控制(大路)**:`NL_DESCRIBER_VERSION`,若修改 `describe_window_in_nl` 需要
  bump 版本並重新 embed 所有 patterns(避免新舊向量語義空間不一致)
- **Push 推送只走 WebSocket**:REST 回應雖然也帶 match 物件(方便 Postman 測試),
  前端 store 對 `(shoeId, roundNo)` 做去重,避免 REST + WS 雙重推送造成重複
- **下三路匹配閾值**:`DERIVED_PATTERN_MIN_SCORE=0.82`(數據校準得出,見上方第 5 節)
- **下三路語義橋版本控制**:`NL_DERIVED_DESCRIBER_VERSION`,目前為 `3.0.0`
- **大路畫法採賭場正統規則**:到達 row=5 後續同色結果向右拖拽並保持 row=5;下三路
  延續列時比較實際格位,開新欄時比較前置欄位的珠數

## API 端點速查

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/shoes` | 開一靴 |
| GET | `/api/shoes/{id}` | 取靴狀態 |
| POST | `/api/shoes/{id}/rounds` | 提交一局(觸發大路 + 下三路 match + WS push)|
| POST | `/api/shoes/{id}/randomize` | 隨機產生 N 局(符合真實機率)|
| GET | `/api/shoes/{id}/matches` | 大路歷史匹配紀錄 |
| GET | `/api/shoes/{id}/derived-matches` | 下三路歷史匹配紀錄 |
| GET | `/api/shoes/{id}/roads` | 取得大路 + 下三路完整網格(前端也會自行即時計算,此 endpoint 供除錯/校驗用)|
| GET | `/api/patterns` | 大路 Pattern 列表 |
| POST | `/api/patterns` | 新增大路 Pattern(表單)|
| POST | `/api/patterns/nl` | 大路自然語言解析(Azure OpenAI)|
| POST | `/api/patterns/embed-preview` | 大路 Embedding 預覽 |
| POST | `/api/patterns/similarity-check` | 大路語義去重檢查 |
| GET / POST / PUT / DELETE | `/api/derived-patterns` | 下三路 Pattern CRUD |
| POST | `/api/derived-patterns/nl` | 下三路自然語言解析(Azure OpenAI)|
| POST | `/api/derived-patterns/embed-preview` | 下三路 Embedding 預覽 |
| POST | `/api/derived-patterns/similarity-check` | 下三路語義去重檢查 |
| GET | `/api/debug/windows/{shoeId}/{roundNo}` | 大路全 pattern cosine 排名(debug 用)|
| GET | `/api/debug/derived/{shoeId}/{roundNo}` | 下三路全 pattern cosine 排名(debug 用)|
| WS | `/ws/table/{tableId}` | 即時推播(payload 內 `derivedMatch` 欄位帶下三路結果)|

## 尚未完成的延伸功能

- **問路(ask-road)**:模擬下一手開莊/開閒分別會讓三路變成什麼顏色的邏輯已經
  寫好(`derived_roads.ask_next`),但尚未接到任何 API/UI,留給下一階段。
