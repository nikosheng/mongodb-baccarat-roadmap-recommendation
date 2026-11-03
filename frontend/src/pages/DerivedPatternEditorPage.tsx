import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DerivedPattern } from "../api/types";
import { EmbeddingPreview } from "../components/admin/EmbeddingPreview";
import { SimilarityCheck } from "../components/admin/SimilarityCheck";

const CATEGORIES = ["齊色", "連龍", "單跳", "互補", "反彈", "custom"];

type NlStep = "idle" | "parsing" | "parsed" | "embedding" | "checking" | "done" | "error";

const NL_STEP_LABEL: Record<NlStep, string> = {
  idle: "",
  parsing: "Step 1 解析自然語言中...",
  parsed: "Step 2 已生成 Pattern 結構",
  embedding: "Step 3 正在產生 embedding...",
  checking: "Step 4 檢查語義相似度...",
  done: "Done ✓",
  error: "解析失敗",
};

export function DerivedPatternEditorPage({ mode }: { mode: "create" | "edit" }) {
  const { id } = useParams();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<"form" | "nl">("form");

  const [name, setName] = useState("");
  const [category, setCategory] = useState("custom");
  const [nlDescription, setNlDescription] = useState("");
  const [bigEye, setBigEye] = useState("");
  const [small, setSmall] = useState("");
  const [cockroach, setCockroach] = useState("");
  const [predictedNext, setPredictedNext] = useState<"B" | "P">("B");
  const [baseConfidence, setBaseConfidence] = useState(0.55);
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [nlText, setNlText] = useState("");
  const [nlStep, setNlStep] = useState<NlStep>("idle");
  const [nlRationale, setNlRationale] = useState("");

  useEffect(() => {
    if (mode === "edit" && id) {
      api.derivedPatterns.get(id).then((p: DerivedPattern) => {
        setName(p.name);
        setCategory(p.category);
        setNlDescription(p.nlDescription);
        setBigEye(p.canonicalRoads.bigEye);
        setSmall(p.canonicalRoads.small);
        setCockroach(p.canonicalRoads.cockroach);
        setPredictedNext(p.predictedNext);
        setBaseConfidence(p.baseConfidence);
        setEnabled(p.enabled);
      });
    }
  }, [mode, id]);

  async function handleParseNl() {
    setNlStep("parsing");
    setError(null);
    try {
      const result = await api.derivedPatterns.parseNL(nlText);
      setNlStep("parsed");
      setName(result.name);
      setCategory(result.category);
      setBigEye(result.canonicalRoads.bigEye);
      setSmall(result.canonicalRoads.small);
      setCockroach(result.canonicalRoads.cockroach);
      setPredictedNext(result.predictedNext);
      setBaseConfidence(result.baseConfidence);
      setNlDescription(nlText);
      setNlRationale(result.rationale);

      setNlStep("embedding");
      await api.derivedPatterns.embedPreview(result.canonicalRoads);
      setNlStep("checking");
      await api.derivedPatterns.similarityCheck(result.canonicalRoads);
      setNlStep("done");
    } catch (e) {
      setNlStep("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    const canonicalRoads = {
      bigEye: bigEye.toUpperCase(),
      small: small.toUpperCase(),
      cockroach: cockroach.toUpperCase(),
    };
    try {
      if (mode === "create") {
        await api.derivedPatterns.create({
          name,
          category,
          nlDescription,
          canonicalRoads,
          predictedNext,
          baseConfidence,
          enabled,
        });
      } else if (id) {
        await api.derivedPatterns.update(id, {
          name,
          category,
          nlDescription,
          canonicalRoads,
          predictedNext,
          baseConfidence,
          enabled,
        });
      }
      navigate("/admin/derived");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const roadsFilled = bigEye || small || cockroach;

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">
        {mode === "create" ? "新增下三路 Pattern" : "編輯下三路 Pattern"}
      </h1>

      {mode === "create" && (
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("form")}
            className={`px-4 py-2 rounded-md text-sm ${
              activeTab === "form" ? "bg-accent-gold text-bg-deep" : "bg-bg-card text-text-muted"
            }`}
          >
            表單模式
          </button>
          <button
            onClick={() => setActiveTab("nl")}
            className={`px-4 py-2 rounded-md text-sm ${
              activeTab === "nl" ? "bg-accent-gold text-bg-deep" : "bg-bg-card text-text-muted"
            }`}
          >
            自然語言模式
          </button>
        </div>
      )}

      {activeTab === "nl" && mode === "create" && (
        <div className="rounded-lg border border-border-dim bg-bg-card p-4 space-y-3">
          <label className="text-sm text-text-muted">用自然語言描述下三路路數</label>
          <textarea
            value={nlText}
            onChange={(e) => setNlText(e.target.value)}
            rows={3}
            placeholder="例如:大眼仔小路蟑螂路同時開紅,代表三元及第強訊號"
            className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
          />
          <button
            onClick={handleParseNl}
            disabled={!nlText || nlStep === "parsing"}
            className="px-4 py-2 rounded-md bg-player text-white text-sm font-semibold disabled:opacity-40"
          >
            🤖 用 Azure OpenAI 解析
          </button>
          {nlStep !== "idle" && (
            <div className="text-sm text-text-muted flex items-center gap-2">
              {nlStep !== "done" && nlStep !== "error" && (
                <span className="inline-block w-3 h-3 border-2 border-t-transparent border-accent-gold rounded-full animate-spin" />
              )}
              {NL_STEP_LABEL[nlStep]}
            </div>
          )}
          {nlStep === "done" && (
            <div className="rounded-md bg-bg-deep p-3 text-sm space-y-1">
              <div>建議名稱: <strong>{name}</strong></div>
              <div>分類: {category}</div>
              <div>
                Canonical: 大眼
                <span className="font-mono-seq">{bigEye}</span> 小路
                <span className="font-mono-seq">{small}</span> 蟑螂
                <span className="font-mono-seq">{cockroach}</span>
              </div>
              <div>預測下盤: {predictedNext}</div>
              <div>基礎信心: {(baseConfidence * 100).toFixed(0)}%</div>
              <div className="text-text-muted">{nlRationale}</div>
            </div>
          )}
        </div>
      )}

      {(activeTab === "form" || mode === "edit" || nlStep === "done") && (
        <div className="rounded-lg border border-border-dim bg-bg-card p-4 space-y-3">
          <div>
            <label className="text-sm text-text-muted block mb-1">名稱</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
            />
          </div>
          <div>
            <label className="text-sm text-text-muted block mb-1">分類</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm text-text-muted block mb-1">自然語言描述</label>
            <input
              value={nlDescription}
              onChange={(e) => setNlDescription(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-sm text-text-muted block mb-1">大眼仔 (R/B)</label>
              <input
                value={bigEye}
                onChange={(e) => setBigEye(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm font-mono-seq"
                placeholder="RRR"
                maxLength={12}
              />
            </div>
            <div>
              <label className="text-sm text-text-muted block mb-1">小路 (R/B)</label>
              <input
                value={small}
                onChange={(e) => setSmall(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm font-mono-seq"
                placeholder="RR"
                maxLength={12}
              />
            </div>
            <div>
              <label className="text-sm text-text-muted block mb-1">蟑螂路 (R/B)</label>
              <input
                value={cockroach}
                onChange={(e) => setCockroach(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm font-mono-seq"
                placeholder="R"
                maxLength={12}
              />
            </div>
          </div>
          <div>
            <label className="text-sm text-text-muted block mb-1">預測下盤</label>
            <div className="flex gap-2">
              {(["B", "P"] as const).map((o) => (
                <button
                  key={o}
                  onClick={() => setPredictedNext(o)}
                  className={`px-3 py-1.5 rounded-md text-sm ${
                    predictedNext === o ? "bg-accent-gold text-bg-deep" : "bg-bg-deep text-text-muted"
                  }`}
                >
                  {o}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm text-text-muted block mb-1">
              基礎信心: {(baseConfidence * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={baseConfidence}
              onChange={(e) => setBaseConfidence(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            啟用
          </label>

          <EmbeddingPreview kind="derived" canonicalRoads={{ bigEye, small, cockroach }} />
          <SimilarityCheck kind="derived" canonicalRoads={{ bigEye, small, cockroach }} excludePatternId={id} />

          {error && <div className="text-sm text-banker">{error}</div>}

          <div className="flex gap-2 pt-2">
            <button
              onClick={() => navigate("/admin/derived")}
              className="px-4 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name || !roadsFilled}
              className="px-4 py-2 rounded-md bg-accent-gold text-bg-deep font-semibold text-sm disabled:opacity-40"
            >
              {saving ? "儲存中..." : "儲存"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
