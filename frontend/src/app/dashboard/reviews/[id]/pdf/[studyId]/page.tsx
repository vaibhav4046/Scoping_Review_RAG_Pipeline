"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Study, Extraction } from "@/lib/api";

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const level = value >= 0.8 ? "high" : value >= 0.5 ? "medium" : "low";
  return (
    <div className="confidence-bar">
      <div className="confidence-track">
        <div className={`confidence-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="confidence-label" style={{ color: `var(--confidence-${level})` }}>
        {pct}%
      </span>
    </div>
  );
}

export default function PDFViewerPage() {
  const params = useParams();
  const reviewId = params.id as string;
  const studyId = params.studyId as string;

  const [study, setStudy] = useState<Study | null>(null);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [loading, setLoading] = useState(true);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const s = await api.getStudy(reviewId, studyId);
        setStudy(s);

        // Try to load extraction
        const exts = await api.getExtractions(reviewId);
        const studyExt = exts.find((e) => e.study_id === studyId);
        if (studyExt) setExtraction(studyExt);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [reviewId, studyId]);

  const handleUpload = async () => {
    if (!pdfFile) return;
    setUploading(true);
    setUploadMsg("");
    try {
      await api.uploadPdf(reviewId, studyId, pdfFile);
      setUploadMsg("PDF uploaded successfully!");
      // Reload study
      const s = await api.getStudy(reviewId, studyId);
      setStudy(s);
    } catch (err: any) {
      setUploadMsg(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    );
  }

  if (!study) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">Study not found</div>
      </div>
    );
  }

  const picoFields = [
    { key: "population", label: "Population", cls: "p" },
    { key: "intervention", label: "Intervention", cls: "i" },
    { key: "comparator", label: "Comparator", cls: "c" },
    { key: "outcome", label: "Outcome", cls: "o" },
    { key: "study_design", label: "Study Design", cls: "p" },
    { key: "sample_size", label: "Sample Size", cls: "i" },
    { key: "duration", label: "Duration", cls: "c" },
    { key: "setting", label: "Setting", cls: "o" },
  ];

  return (
    <>
      {/* Header */}
      <div className="section-header mb-16">
        <div style={{ flex: 1 }}>
          <div className="flex items-center gap-8 mb-8">
            <a
              href={`/dashboard/reviews/${reviewId}`}
              style={{ color: "var(--accent-blue)", fontSize: 13 }}
            >
              ← Back to Review
            </a>
          </div>
          <h1 className="section-title" style={{ fontSize: 17 }}>
            {study.title}
          </h1>
          <div className="flex items-center gap-16 mt-8">
            {study.pmid && (
              <span className="text-xs text-muted">PMID: {study.pmid}</span>
            )}
            {study.doi && (
              <a
                href={`https://doi.org/${study.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs"
              >
                DOI: {study.doi}
              </a>
            )}
            {study.authors && (
              <span className="text-xs text-muted truncate" style={{ maxWidth: 300 }}>
                {study.authors}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-8">
          <span className={`badge badge-${study.screening_status}`}>
            {study.screening_status}
          </span>
          <span className={`badge badge-${study.pdf_available ? "completed" : "pending"}`}>
            {study.pdf_available ? "PDF Available" : "No PDF"}
          </span>
        </div>
      </div>

      {/* Split View: PDF + Extraction */}
      <div className="pdf-split-view">
        {/* Left: PDF / Abstract */}
        <div className="pdf-viewer-panel">
          <div className="pdf-viewer-header">
            <span>📄 Document View</span>
            {!study.pdf_available && (
              <div className="flex items-center gap-8">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                  style={{ fontSize: 12, color: "var(--text-secondary)" }}
                />
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleUpload}
                  disabled={!pdfFile || uploading}
                >
                  {uploading ? <span className="spinner" /> : "Upload PDF"}
                </button>
              </div>
            )}
          </div>
          <div className="pdf-viewer-body">
            {uploadMsg && (
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  background: uploadMsg.includes("success")
                    ? "var(--accent-emerald-glow)"
                    : "var(--accent-rose-glow)",
                  color: uploadMsg.includes("success")
                    ? "var(--accent-emerald)"
                    : "var(--accent-rose)",
                  fontSize: 13,
                  marginBottom: 16,
                }}
              >
                {uploadMsg}
              </div>
            )}

            {study.pdf_available ? (
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                <div style={{ fontSize: 48 }}>📎</div>
                <div
                  style={{
                    fontSize: 14,
                    color: "var(--text-secondary)",
                    textAlign: "center",
                  }}
                >
                  PDF is stored on the server.
                  <br />
                  <span className="text-xs text-muted">
                    Full text has been extracted and embedded for RAG retrieval.
                  </span>
                </div>
              </div>
            ) : study.abstract ? (
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    color: "var(--text-tertiary)",
                    marginBottom: 12,
                  }}
                >
                  Abstract
                </div>
                <p
                  style={{
                    fontSize: 14,
                    lineHeight: 1.7,
                    color: "var(--text-secondary)",
                  }}
                >
                  {study.abstract}
                </p>

                {study.mesh_terms && (
                  <>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        color: "var(--text-tertiary)",
                        marginTop: 24,
                        marginBottom: 8,
                      }}
                    >
                      MeSH Terms
                    </div>
                    <div className="flex gap-8" style={{ flexWrap: "wrap" }}>
                      {study.mesh_terms.split("; ").map((term) => (
                        <span key={term} className="badge badge-pending">
                          {term}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">📄</div>
                <div className="empty-state-title">No text available</div>
                <div className="empty-state-desc">
                  Upload a PDF to enable full-text analysis and PICO extraction.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Extraction Data */}
        <div className="pdf-extraction-panel">
          <div className="card" style={{ height: "100%" }}>
            <h3
              style={{
                fontSize: 14,
                fontWeight: 600,
                marginBottom: 16,
                color: "var(--text-primary)",
              }}
            >
              📊 Extracted Data
            </h3>

            {extraction ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {picoFields.map(({ key, label, cls }) => {
                  const val = (extraction as any)[key];
                  const conf = extraction.confidence_scores?.[key] ?? 0;
                  const quote = extraction.source_quotes?.[key];
                  const isNotReported = val === "Not Reported";

                  return (
                    <div
                      key={key}
                      style={{
                        padding: "12px 14px",
                        background: "var(--bg-glass)",
                        borderRadius: "var(--radius-sm)",
                        borderLeft: `3px solid ${
                          isNotReported
                            ? "var(--border-subtle)"
                            : cls === "p"
                            ? "var(--accent-blue)"
                            : cls === "i"
                            ? "var(--accent-emerald)"
                            : cls === "c"
                            ? "var(--accent-amber)"
                            : "var(--accent-violet)"
                        }`,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          marginBottom: 4,
                          color:
                            cls === "p"
                              ? "var(--accent-blue)"
                              : cls === "i"
                              ? "var(--accent-emerald)"
                              : cls === "c"
                              ? "var(--accent-amber)"
                              : "var(--accent-violet)",
                        }}
                      >
                        {label}
                      </div>
                      <div
                        style={{
                          fontSize: 13,
                          color: isNotReported
                            ? "var(--text-muted)"
                            : "var(--text-primary)",
                          fontStyle: isNotReported ? "italic" : "normal",
                          marginBottom: 6,
                        }}
                      >
                        {val}
                      </div>
                      <ConfidenceBar value={conf} />
                      {quote && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--text-tertiary)",
                            fontStyle: "italic",
                            marginTop: 6,
                            padding: "6px 8px",
                            background: "rgba(0,0,0,0.2)",
                            borderRadius: 4,
                          }}
                        >
                          &ldquo;{quote}&rdquo;
                        </div>
                      )}
                    </div>
                  );
                })}

                <div
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: 12,
                    marginTop: 4,
                  }}
                >
                  Model: {extraction.model_used} ({extraction.provider})
                  <br />
                  Extracted: {new Date(extraction.created_at).toLocaleString()}
                </div>
              </div>
            ) : (
              <div className="empty-state" style={{ padding: "40px 0" }}>
                <div className="empty-state-icon">📊</div>
                <div className="empty-state-title" style={{ fontSize: 14 }}>
                  No extraction yet
                </div>
                <div className="empty-state-desc" style={{ fontSize: 12 }}>
                  Run PICO extraction from the review page to populate this panel.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
