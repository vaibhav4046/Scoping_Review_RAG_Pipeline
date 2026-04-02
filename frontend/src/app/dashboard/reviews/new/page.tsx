"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function NewReviewPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    search_query: "",
    inclusion_criteria: "",
    exclusion_criteria: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError("Title is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const review = await api.createReview(form);
      router.push(`/dashboard/reviews/${review.id}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="section-header mb-24">
        <div>
          <h1 className="section-title">New Review</h1>
          <p className="section-subtitle">Create a new scoping review project</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 700 }}>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label">Review Title *</label>
            <input
              type="text"
              className="input"
              placeholder="e.g., AI in Healthcare: A Scoping Review"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label">Description</label>
            <textarea
              className="input"
              placeholder="Brief description of the review objectives..."
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
            />
          </div>

          <div className="input-group">
            <label className="input-label">PubMed Search Query</label>
            <input
              type="text"
              className="input"
              placeholder='e.g., "machine learning" AND "clinical trials"'
              value={form.search_query}
              onChange={(e) => setForm({ ...form, search_query: e.target.value })}
            />
            <span className="text-xs text-muted mt-8" style={{ display: "block" }}>
              Use PubMed query syntax. You can also set this later.
            </span>
          </div>

          <div className="input-group">
            <label className="input-label">Inclusion Criteria</label>
            <textarea
              className="input"
              placeholder="Define what makes a study eligible for inclusion..."
              value={form.inclusion_criteria}
              onChange={(e) => setForm({ ...form, inclusion_criteria: e.target.value })}
              rows={4}
            />
          </div>

          <div className="input-group">
            <label className="input-label">Exclusion Criteria</label>
            <textarea
              className="input"
              placeholder="Define what would exclude a study..."
              value={form.exclusion_criteria}
              onChange={(e) => setForm({ ...form, exclusion_criteria: e.target.value })}
              rows={4}
            />
          </div>

          {error && (
            <div style={{ color: "var(--accent-rose)", fontSize: 13, marginBottom: 16 }}>
              {error}
            </div>
          )}

          <div className="flex items-center gap-12">
            <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
              {loading ? <span className="spinner" /> : "Create Review"}
            </button>
            <a href="/dashboard/reviews" className="btn btn-secondary btn-lg">
              Cancel
            </a>
          </div>
        </form>
      </div>
    </>
  );
}
