"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type {
  ReviewWithStats,
  StudyBrief,
  TaskStatus,
  Screening,
  Extraction,
  Validation,
} from "@/lib/api";

const PIPELINE_STAGES = ["created", "searching", "screening", "extracting", "validating", "completed"];

function getStageIndex(status: string): number {
  const idx = PIPELINE_STAGES.indexOf(status);
  return idx >= 0 ? idx : 0;
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const level = value >= 0.8 ? "high" : value >= 0.5 ? "medium" : "low";
  return (
    <div className="confidence-bar">
      <div className="confidence-track">
        <div className={`confidence-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`confidence-label`} style={{ color: `var(--confidence-${level})` }}>
        {pct}%
      </span>
    </div>
  );
}

export default function ReviewDetailPage() {
  const params = useParams();
  const reviewId = params.id as string;

  const [review, setReview] = useState<ReviewWithStats | null>(null);
  const [studies, setStudies] = useState<StudyBrief[]>([]);
  const [screenings, setScreenings] = useState<Screening[]>([]);
  const [extractions, setExtractions] = useState<Extraction[]>([]);
  const [validations, setValidations] = useState<Validation[]>([]);
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  // Search form
  const [searchQuery, setSearchQuery] = useState("");
  const [maxResults, setMaxResults] = useState(100);
  const [actionLoading, setActionLoading] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [r, s, t] = await Promise.all([
        api.getReview(reviewId),
        api.getStudies(reviewId),
        api.getProgress(reviewId),
      ]);
      setReview(r);
      setStudies(s);
      setTasks(t);
      if (r.search_query) setSearchQuery(r.search_query);

      // Load screening/extraction/validation data
      if (r.stats.screened > 0) {
        api.getScreenings(reviewId).then(setScreenings).catch(console.error);
      }
      if (r.stats.extracted > 0) {
        api.getExtractions(reviewId).then(setExtractions).catch(console.error);
      }
      if (r.stats.validated > 0) {
        api.getValidations(reviewId).then(setValidations).catch(console.error);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [reviewId]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [refresh]);

  // Actions
  const handleSearch = async () => {
    setActionLoading("search");
    try {
      await api.triggerSearch(reviewId, searchQuery, maxResults);
      setTimeout(refresh, 1000);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading("");
    }
  };

  const handleScreen = async () => {
    setActionLoading("screening");
    try {
      await api.triggerScreening(reviewId);
      setTimeout(refresh, 1000);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading("");
    }
  };

  const handleExtract = async () => {
    setActionLoading("extraction");
    try {
      await api.triggerExtraction(reviewId);
      setTimeout(refresh, 1000);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading("");
    }
  };

  const handleValidate = async () => {
    setActionLoading("validation");
    try {
      await api.triggerValidation(reviewId);
      setTimeout(refresh, 1000);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading("");
    }
  };

  const handleExport = async (format: "csv" | "json") => {
    try {
      const data = await api.exportResults(reviewId, format);
      if (format === "csv") {
        const blob = new Blob([data as string], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${review?.title || "export"}.csv`;
        a.click();
      } else {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${review?.title || "export"}.json`;
        a.click();
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    );
  }

  if (!review) {
    return <div className="empty-state"><div className="empty-state-title">Review not found</div></div>;
  }

  const stageIdx = getStageIndex(review.status);
  const studyMap = Object.fromEntries(studies.map((s) => [s.id, s]));

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "studies", label: `Studies (${studies.length})` },
    { id: "screening", label: `Screening (${review.stats.screened})` },
    { id: "extraction", label: `Extraction (${review.stats.extracted})` },
    { id: "validation", label: `Validation (${review.stats.validated})` },
  ];

  return (
    <>
      {/* Title */}
      <div className="section-header mb-16">
        <div>
          <h1 className="section-title">{review.title}</h1>
          {review.description && (
            <p className="section-subtitle">{review.description}</p>
          )}
        </div>
        <div className="flex items-center gap-8">
          <button className="btn btn-secondary btn-sm" onClick={() => handleExport("csv")}>
            📥 Export CSV
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => handleExport("json")}>
            📥 JSON
          </button>
        </div>
      </div>

      {/* Pipeline Progress */}
      <div className="card mb-24">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-tertiary)" }}>
          PIPELINE PROGRESS
        </div>
        <div className="pipeline-steps">
          {["Search", "Screen", "Extract", "Validate", "Complete"].map((label, i) => {
            const stepStageIdx = i + 1;
            let stepClass = "";
            if (stageIdx > stepStageIdx) stepClass = "completed";
            else if (stageIdx === stepStageIdx) stepClass = "active";

            return (
              <div key={label} className={`pipeline-step ${stepClass}`}>
                <div className="pipeline-dot">
                  {stepClass === "completed" ? "✓" : i + 1}
                </div>
                <div className="pipeline-label">{label}</div>
              </div>
            );
          })}
        </div>

        {/* Running tasks */}
        {tasks.filter((t) => t.status === "running").map((t) => (
          <div key={t.task_id} style={{
            display: "flex", alignItems: "center", gap: 12, marginTop: 12,
            padding: "10px 14px", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)",
          }}>
            <div className="spinner" />
            <span className="text-sm">
              {t.task_type}: {t.completed_items}/{t.total_items} ({Math.round(t.progress * 100)}%)
            </span>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div className="stat-icon blue">📄</div>
          <div className="stat-info"><div className="stat-label">Total</div><div className="stat-value">{review.stats.total_studies}</div></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon emerald">✅</div>
          <div className="stat-info"><div className="stat-label">Included</div><div className="stat-value">{review.stats.included}</div></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon rose">❌</div>
          <div className="stat-info"><div className="stat-label">Excluded</div><div className="stat-value">{review.stats.excluded}</div></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon amber">❓</div>
          <div className="stat-info"><div className="stat-label">Uncertain</div><div className="stat-value">{review.stats.uncertain}</div></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon violet">📊</div>
          <div className="stat-info"><div className="stat-label">Extracted</div><div className="stat-value">{review.stats.extracted}</div></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue">🔍</div>
          <div className="stat-info"><div className="stat-label">Validated</div><div className="stat-value">{review.stats.validated}</div></div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 4, borderBottom: "1px solid var(--border-subtle)", marginBottom: 24,
      }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 16px",
              fontSize: 13,
              fontWeight: 500,
              color: activeTab === tab.id ? "var(--accent-blue)" : "var(--text-tertiary)",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === tab.id ? "2px solid var(--accent-blue)" : "2px solid transparent",
              cursor: "pointer",
              transition: "all 150ms",
              fontFamily: "inherit",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Search Panel */}
          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>🔎 PubMed Search</h3>
            <div className="input-group">
              <label className="input-label">Search Query</label>
              <input
                type="text"
                className="input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder='"machine learning" AND "healthcare"'
              />
            </div>
            <div className="input-group">
              <label className="input-label">Max Results</label>
              <input
                type="number"
                className="input"
                value={maxResults}
                onChange={(e) => setMaxResults(parseInt(e.target.value))}
                min={1}
                max={10000}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={!!actionLoading || !searchQuery}
            >
              {actionLoading === "search" ? <span className="spinner" /> : "Search PubMed"}
            </button>
          </div>

          {/* Actions Panel */}
          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>⚡ Pipeline Actions</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <button
                className="btn btn-secondary w-full"
                onClick={handleScreen}
                disabled={!!actionLoading || studies.length === 0}
              >
                {actionLoading === "screening" ? <span className="spinner" /> : "🧪 Run Screening"}
              </button>
              <button
                className="btn btn-secondary w-full"
                onClick={handleExtract}
                disabled={!!actionLoading || review.stats.included === 0}
              >
                {actionLoading === "extraction" ? <span className="spinner" /> : "📊 Run Extraction"}
              </button>
              <button
                className="btn btn-secondary w-full"
                onClick={handleValidate}
                disabled={!!actionLoading || review.stats.extracted === 0}
              >
                {actionLoading === "validation" ? <span className="spinner" /> : "🔍 Run Validation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === "studies" && (
        <div className="table-container">
          {studies.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📄</div>
              <div className="empty-state-title">No studies yet</div>
              <div className="empty-state-desc">Run a PubMed search to populate studies.</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>PMID</th>
                  <th>Title</th>
                  <th>Authors</th>
                  <th>Screening</th>
                  <th>Extraction</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {studies.map((study) => (
                  <tr key={study.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{study.pmid || "—"}</td>
                    <td style={{ maxWidth: 400 }}>
                      <div className="truncate" style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                        {study.title}
                      </div>
                    </td>
                    <td className="text-sm truncate" style={{ maxWidth: 200 }}>{study.authors || "—"}</td>
                    <td>
                      <span className={`badge badge-${study.screening_status}`}>
                        {study.screening_status}
                      </span>
                    </td>
                    <td>
                      <span className={`badge badge-${study.extraction_status === 'completed' ? 'completed' : 'pending'}`}>
                        {study.extraction_status}
                      </span>
                    </td>
                    <td>
                      <a
                        href={`/dashboard/reviews/${reviewId}/pdf/${study.id}`}
                        className="btn btn-secondary btn-sm"
                      >
                        View →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === "screening" && (
        <div className="table-container">
          {screenings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🧪</div>
              <div className="empty-state-title">No screening results yet</div>
              <div className="empty-state-desc">Run screening to evaluate studies.</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Study</th>
                  <th>Decision</th>
                  <th>Confidence</th>
                  <th>Rationale</th>
                  <th>Model</th>
                </tr>
              </thead>
              <tbody>
                {screenings.map((s) => (
                  <tr key={s.id}>
                    <td className="text-sm truncate" style={{ maxWidth: 200 }}>
                      {studyMap[s.study_id]?.title || s.study_id}
                    </td>
                    <td>
                      <span className={`badge badge-${s.decision}`}>{s.decision}</span>
                    </td>
                    <td style={{ minWidth: 120 }}>
                      <ConfidenceBar value={s.confidence} />
                    </td>
                    <td className="text-sm" style={{ maxWidth: 300 }}>
                      <div className="truncate">{s.rationale}</div>
                    </td>
                    <td className="text-xs text-muted">{s.model_used}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === "extraction" && (
        <>
          {extractions.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <div className="empty-state-icon">📊</div>
                <div className="empty-state-title">No extractions yet</div>
                <div className="empty-state-desc">Run PICO extraction on included studies.</div>
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gap: 24 }}>
              {extractions.map((ext) => {
                const study = studyMap[ext.study_id];
                return (
                  <div key={ext.id} className="card">
                    <div className="flex items-center justify-between mb-16">
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text-primary)" }}>
                          {study?.title || ext.study_id}
                        </div>
                        <div className="text-xs text-muted mt-8">
                          Model: {ext.model_used} | {new Date(ext.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>

                    <div className="pico-grid">
                      {[
                        { key: "population", label: "Population", cls: "p" },
                        { key: "intervention", label: "Intervention", cls: "i" },
                        { key: "comparator", label: "Comparator", cls: "c" },
                        { key: "outcome", label: "Outcome", cls: "o" },
                        { key: "study_design", label: "Study Design", cls: "p" },
                        { key: "sample_size", label: "Sample Size", cls: "i" },
                        { key: "duration", label: "Duration", cls: "c" },
                        { key: "setting", label: "Setting", cls: "o" },
                      ].map(({ key, label, cls }) => {
                        const val = (ext as any)[key];
                        const conf = ext.confidence_scores?.[key] ?? 0;
                        const quote = ext.source_quotes?.[key];
                        return (
                          <div key={key} className="pico-card">
                            <div className={`pico-card-label ${cls}`}>{label}</div>
                            <div className={`pico-card-value ${val === "Not Reported" ? "not-reported" : ""}`}>
                              {val}
                            </div>
                            <ConfidenceBar value={conf} />
                            {quote && (
                              <div className="pico-card-quote">&ldquo;{quote}&rdquo;</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {activeTab === "validation" && (
        <div className="table-container">
          {validations.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <div className="empty-state-title">No validations yet</div>
              <div className="empty-state-desc">Run cross-LLM validation on extractions.</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Extraction</th>
                  <th>Agreement</th>
                  <th>Validator</th>
                  <th>Human Review</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {validations.map((v) => (
                  <tr key={v.id}>
                    <td className="text-sm">{v.extraction_id.slice(0, 8)}...</td>
                    <td style={{ minWidth: 120 }}>
                      <ConfidenceBar value={v.agreement_score} />
                    </td>
                    <td className="text-xs text-muted">{v.validator_model}</td>
                    <td>
                      {v.needs_human_review ? (
                        <span className="badge badge-uncertain">Needs Review</span>
                      ) : (
                        <span className="badge badge-include">OK</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge-${v.final_decision === 'accepted' ? 'include' : 'uncertain'}`}>
                        {v.final_decision}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
