"""The 10 default demo patterns. Each one's canonicalSequence is run through
describe_window_in_nl (the same function used at runtime) to produce the
text that gets embedded — this guarantees seed-time and runtime vectors
live in the same semantic space."""

DEFAULT_PATTERNS = [
    {
        "name": "長莊連龍",
        "category": "streak",
        "nlDescription": "連續 6 盤以上莊,下盤續莊",
        "canonicalSequence": "BBBBBB",
        "predictedNext": "B",
        "baseConfidence": 0.55,
    },
    {
        "name": "長閒連龍",
        "category": "streak",
        "nlDescription": "連續 6 盤以上閒,下盤續閒",
        "canonicalSequence": "PPPPPP",
        "predictedNext": "P",
        "baseConfidence": 0.55,
    },
    {
        "name": "長莊斷龍",
        "category": "streak",
        "nlDescription": "連 6 盤以上莊後突然出閒,下盤續閒",
        "canonicalSequence": "BBBBBBP",
        "predictedNext": "P",
        "baseConfidence": 0.60,
    },
    {
        "name": "長閒斷龍",
        "category": "streak",
        "nlDescription": "連 6 盤以上閒後突然出莊,下盤續莊",
        "canonicalSequence": "PPPPPPB",
        "predictedNext": "B",
        "baseConfidence": 0.60,
    },
    {
        "name": "單跳",
        "category": "chop",
        "nlDescription": "莊閒交替出現 4 次以上,下盤延續交替出莊",
        "canonicalSequence": "BPBPBPBP",
        "predictedNext": "B",
        "baseConfidence": 0.52,
    },
    {
        "name": "雙雙跳",
        "category": "chop",
        "nlDescription": "兩莊兩閒重複出現,下盤延續",
        "canonicalSequence": "BBPPBBPP",
        "predictedNext": "B",
        "baseConfidence": 0.54,
    },
    {
        "name": "拍拍黐",
        "category": "chop",
        "nlDescription": "兩莊兩閒重複後再接兩莊,下盤出閒",
        "canonicalSequence": "BBPPBB",
        "predictedNext": "P",
        "baseConfidence": 0.53,
    },
    {
        "name": "一房兩廳",
        "category": "mixed",
        "nlDescription": "一莊兩閒循環,下盤出莊",
        "canonicalSequence": "BPPBPPBPP",
        "predictedNext": "B",
        "baseConfidence": 0.54,
    },
    {
        "name": "和局夾擊",
        "category": "tie",
        "nlDescription": "短期內出現兩次以上和局",
        "canonicalSequence": "BPTBPTB",
        "predictedNext": "P",
        "baseConfidence": 0.45,
    },
    {
        "name": "莊優勢盤",
        "category": "ratio",
        "nlDescription": "近期局數中莊佔比明顯偏高",
        "canonicalSequence": "BBBBBBBBBBPPPPP",
        "predictedNext": "B",
        "baseConfidence": 0.52,
    },
]
