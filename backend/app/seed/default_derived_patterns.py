"""Default demo patterns for the second (下三路) vector search. Each entry's
canonicalRoads (R/B tail symbols for Big Eye Boy / Small Road / Cockroach
Pig) is run through describe_derived_in_nl (the same function used at
runtime) to produce the text that gets embedded — this guarantees seed-time
and runtime vectors live in the same semantic space.

Based on the 5 "問路" archetypes:
  1. 三元及第 / 滿堂紅 (齊色) — all three roads unanimous red
  2. 下三路連龍 / 色龍 (連龍) — one road has a long single-color streak
  3. 下三路單跳 (單跳) — alternating red/blue on a road
  4. 三路互補 (互補) — stable two-red-one-blue / two-blue-one-red mix
     (3 variants to cover which road is the odd one out)
  5. 逢藍知返 (反彈) — a road has an extended blue streak, signalling a
     rebound to red
"""

DEFAULT_DERIVED_PATTERNS = [
    {
        "name": "三元及第",
        "category": "齊色",
        "nlDescription": "大眼仔小路蟑螂路同時開紅,三路齊紅代表大路在多個跨度上都呈現對稱,是最強訊號",
        "canonicalRoads": {"bigEye": "R", "small": "R", "cockroach": "R"},
        "predictedNext": "B",
        "baseConfidence": 0.60,
    },
    {
        "name": "下三路連龍",
        "category": "連龍",
        "nlDescription": "大眼仔獨自拉出長紅龍,但小路與蟑螂路呈現混雜狀態(非同時齊紅),即使大路雜亂,大眼仔這一路的內部深層結構仍處於穩定規律中",
        "canonicalRoads": {"bigEye": "RRRRRR", "small": "RBB", "cockroach": "BRB"},
        "predictedNext": "B",
        "baseConfidence": 0.58,
    },
    {
        "name": "下三路單跳",
        "category": "單跳",
        "nlDescription": "大眼仔呈現紅藍交替單跳,代表大路正在規律與不規律之間精準擺盪",
        "canonicalRoads": {"bigEye": "RBRBRB", "small": "RBR", "cockroach": "RB"},
        "predictedNext": "P",
        "baseConfidence": 0.52,
    },
    {
        "name": "三路互補-蟑螂藍",
        "category": "互補",
        "nlDescription": "大眼仔小路開紅,蟑螂路開藍,兩紅一藍的固定組合代表大路某維度被打破但整體慣性仍在",
        "canonicalRoads": {"bigEye": "R", "small": "R", "cockroach": "B"},
        "predictedNext": "B",
        "baseConfidence": 0.54,
    },
    {
        "name": "三路互補-小路藍",
        "category": "互補",
        "nlDescription": "大眼仔蟑螂路開紅,小路開藍,兩紅一藍的固定組合代表大路某維度被打破但整體慣性仍在",
        "canonicalRoads": {"bigEye": "R", "small": "B", "cockroach": "R"},
        "predictedNext": "B",
        "baseConfidence": 0.54,
    },
    {
        "name": "三路互補-大眼藍",
        "category": "互補",
        "nlDescription": "小路蟑螂路開紅,大眼仔開藍,兩紅一藍的固定組合代表大路某維度被打破但整體慣性仍在",
        "canonicalRoads": {"bigEye": "B", "small": "R", "cockroach": "R"},
        "predictedNext": "B",
        "baseConfidence": 0.54,
    },
    {
        "name": "逢藍知返",
        "category": "反彈",
        "nlDescription": "大眼仔連續開出三個以上藍色(非三路同時齊藍),數學機率上混亂到極限必定重新回歸對稱,下一手買紅抓反彈",
        "canonicalRoads": {"bigEye": "BBB", "small": "RBR", "cockroach": "BRB"},
        "predictedNext": "B",
        "baseConfidence": 0.50,
    },
]
