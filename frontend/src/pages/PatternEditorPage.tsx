import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Outcome, Pattern } from "../api/types";
import { EmbeddingPreview } from "../components/admin/EmbeddingPreview";
import { SimilarityCheck } from "../components/admin/SimilarityCheck";

const CATEGORIES = ["streak", "chop", "mixed", "tie", "ratio", "custom"];

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

export function PatternEditorPage({ mode }: { mode: "create" | "edit" }) {
  const { id } = useParams();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<"form" | "nl">("form");

  const [name, setName] = useState("");
  const [category, setCategory] = useState("custom");
  const [nlDescription, setNlDescription] = useState("");
  const [canonicalSequence, setCanonicalSequence] = useState("");
  const [predictedNext, setPredictedNext] = useState<Outcome>("B");
  const [baseConfidence, setBaseConfidence] = useState(0.55);
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [nlText, setNlText] = useState("");
  const [nlStep, setNlStep] = useState<NlStep>("idle");
  const [nlRationale, setNlRationale] = useState("");

  useEffect(() => {
    if (mode === "edit" && id) {
      api.patterns.get(id).then((p: Pattern) => {
        setName(p.name);
        setCategory(p.category);
        setNlDescription(p.nlDescription);
        setCanonicalSequence(p.canonicalSequence);
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
      const result = await api.patterns.parseNL(nlText);
      setNlStep("parsed");
      setName(result.name);
      setCategory(result.category);
      setCanonicalSequence(result.canonicalSequence);
      setPredictedNext(result.predictedNext);
      setBaseConfidence(result.baseConfidence);
      setNlDescription(nlText);
      setNlRationale(result.rationale);

      setNlStep("embedding");
      await api.patterns.embedPreview(result.canonicalSequence);
      setNlStep("checking");
      await api.patterns.similarityCheck(result.canonicalSequence);
      setNlStep("done");
    } catch (e) {
      setNlStep("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        await api.patterns.create({
          name,
          category,
          nlDescription,
          canonicalSequence: canonicalSequence.toUpperCase(),
          predictedNext,
          baseConfidence,
          enabled,
        });
      } else if (id) {
        await api.patterns.update(id, {
          name,
          category,
          nlDescription,
          canonicalSequence: canonicalSequence.toUpperCase(),
          predictedNext,
          baseConfidence,
          enabled,
        });
      }
      navigate("/admin");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">
        {mode === "create" ? "新增 Pattern" : "編輯 Pattern"}
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
          <label className="text-sm text-text-muted">用自然語言描述路數</label>
          <textarea
            value={nlText}
            onChange={(e) => setNlText(e.target.value)}
            rows={3}
            placeholder="例如:連三莊之後連三閒,下盤多半出莊"
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
              <div>Canonical: <span className="font-mono-seq">{canonicalSequence}</span></div>
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
          <div>
            <label className="text-sm text-text-muted block mb-1">Canonical 序列 (B/P/T)</label>
            <input
              value={canonicalSequence}
              onChange={(e) => setCanonicalSequence(e.target.value.toUpperCase())}
              className="w-full px-3 py-2 rounded-md bg-bg-deep border border-border-dim text-sm font-mono-seq"
              placeholder="BBBBBBP"
            />
          </div>
          <div>
            <label className="text-sm text-text-muted block mb-1">預測下盤</label>
            <div className="flex gap-2">
              {(["B", "P", "T"] as Outcome[]).map((o) => (
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

          <EmbeddingPreview kind="big" canonicalSequence={canonicalSequence} />
          <SimilarityCheck kind="big" canonicalSequence={canonicalSequence} excludePatternId={id} />

          {error && <div className="text-sm text-banker">{error}</div>}

          <div className="flex gap-2 pt-2">
            <button
              onClick={() => navigate("/admin")}
              className="px-4 py-2 rounded-md bg-bg-deep border border-border-dim text-sm"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name || !canonicalSequence}
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
