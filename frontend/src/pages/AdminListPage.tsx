import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Pattern } from "../api/types";
import { OutcomeBadge } from "../components/common/Badge";

export function AdminListPage() {
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await api.patterns.list();
      setPatterns(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleEnabled(p: Pattern) {
    await api.patterns.update(p._id, { enabled: !p.enabled });
    load();
  }

  async function remove(p: Pattern) {
    if (!confirm(`確定刪除 "${p.name}"?`)) return;
    await api.patterns.delete(p._id);
    load();
  }

  const filtered = patterns.filter((p) => p.name.includes(search) || p.category.includes(search));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Pattern Library ({patterns.length})</h1>
        <Link
          to="/admin/new"
          className="px-4 py-2 rounded-md bg-accent-gold text-bg-deep font-semibold text-sm hover:brightness-110"
        >
          + 新增 Pattern
        </Link>
      </div>

      <input
        placeholder="搜尋..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-3 py-2 rounded-md bg-bg-card border border-border-dim text-sm"
      />

      {loading ? (
        <div className="text-text-muted">載入中...</div>
      ) : (
        <div className="rounded-lg border border-border-dim overflow-hidden">
          {filtered.map((p) => (
            <div
              key={p._id}
              className="flex items-center justify-between p-3 border-b border-border-dim last:border-b-0 bg-bg-card"
            >
              <div className="flex items-center gap-3">
                <button
                  onClick={() => toggleEnabled(p)}
                  className={`w-3 h-3 rounded-full ${p.enabled ? "bg-green-500" : "bg-gray-600"}`}
                  title={p.enabled ? "啟用中" : "已停用"}
                />
                <div>
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-text-muted">{p.category}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="font-mono-seq text-text-muted">{p.canonicalSequence}</span>
                <span>→</span>
                <OutcomeBadge outcome={p.predictedNext} size="sm" />
                <span className="text-text-muted">{(p.baseConfidence * 100).toFixed(0)}%</span>
                <Link
                  to={`/admin/${p._id}`}
                  className="px-2 py-1 rounded bg-border-dim hover:bg-player text-xs"
                >
                  編輯
                </Link>
                <button
                  onClick={() => remove(p)}
                  className="px-2 py-1 rounded bg-border-dim hover:bg-banker text-xs"
                >
                  刪除
                </button>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="p-4 text-text-muted text-sm">沒有符合的 pattern</div>
          )}
        </div>
      )}
    </div>
  );
}
