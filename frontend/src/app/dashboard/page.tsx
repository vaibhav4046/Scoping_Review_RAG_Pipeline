"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Review } from "@/lib/api";

export default function DashboardPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getReviews().then(setReviews).catch(console.error).finally(() => setLoading(false));
  }, []);

  const totalStudies = reviews.reduce((sum, r) => sum + r.total_studies, 0);
  const completedReviews = reviews.filter((r) => r.status === "completed").length;
  const inProgressReviews = reviews.filter((r) => !["created", "completed"].includes(r.status)).length;

  return (
    <>
      <div className="section-header mb-24">
        <div>
          <h1 className="section-title">Dashboard</h1>
          <p className="section-subtitle">Overview of your scoping review projects</p>
        </div>
        <a href="/dashboard/reviews/new" className="btn btn-primary">
          ✚ New Review
        </a>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-blue)' } as React.CSSProperties}>
          <div className="stat-icon blue">📚</div>
          <div className="stat-info">
            <div className="stat-label">Total Reviews</div>
            <div className="stat-value">{reviews.length}</div>
          </div>
        </div>

        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-emerald)' } as React.CSSProperties}>
          <div className="stat-icon emerald">✅</div>
          <div className="stat-info">
            <div className="stat-label">Completed</div>
            <div className="stat-value">{completedReviews}</div>
          </div>
        </div>

        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-amber)' } as React.CSSProperties}>
          <div className="stat-icon amber">⚡</div>
          <div className="stat-info">
            <div className="stat-label">In Progress</div>
            <div className="stat-value">{inProgressReviews}</div>
          </div>
        </div>

        <div className="stat-card" style={{ '--stat-accent': 'var(--accent-violet)' } as React.CSSProperties}>
          <div className="stat-icon violet">📄</div>
          <div className="stat-info">
            <div className="stat-label">Total Studies</div>
            <div className="stat-value">{totalStudies}</div>
          </div>
        </div>
      </div>

      {/* Recent Reviews */}
      <div className="section-header mb-16">
        <h2 style={{ fontSize: "16px", fontWeight: 600 }}>Recent Reviews</h2>
        <a href="/dashboard/reviews" className="btn btn-secondary btn-sm">
          View All →
        </a>
      </div>

      {loading ? (
        <div className="card" style={{ padding: "60px", textAlign: "center" }}>
          <div className="spinner" style={{ margin: "0 auto", width: 32, height: 32 }} />
        </div>
      ) : reviews.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🔬</div>
            <div className="empty-state-title">No reviews yet</div>
            <div className="empty-state-desc">
              Create your first scoping review to start analyzing literature with AI assistance.
            </div>
            <a href="/dashboard/reviews/new" className="btn btn-primary">
              Create First Review
            </a>
          </div>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Studies</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reviews.slice(0, 5).map((review) => (
                <tr key={review.id}>
                  <td>
                    <a href={`/dashboard/reviews/${review.id}`} style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                      {review.title}
                    </a>
                    {review.description && (
                      <div className="text-xs text-muted truncate" style={{ maxWidth: 400, marginTop: 2 }}>
                        {review.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className={`badge badge-${review.status === 'completed' ? 'completed' : review.status === 'created' ? 'pending' : 'include'}`}>
                      {review.status}
                    </span>
                  </td>
                  <td>{review.total_studies}</td>
                  <td className="text-muted text-sm">
                    {new Date(review.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <a href={`/dashboard/reviews/${review.id}`} className="btn btn-secondary btn-sm">
                      Open →
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
