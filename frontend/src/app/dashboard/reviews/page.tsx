"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Review } from "@/lib/api";

export default function ReviewsListPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getReviews().then(setReviews).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this review?")) return;
    try {
      await api.deleteReview(id);
      setReviews(reviews.filter((r) => r.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <>
      <div className="section-header mb-24">
        <div>
          <h1 className="section-title">Reviews</h1>
          <p className="section-subtitle">Manage your scoping review projects</p>
        </div>
        <a href="/dashboard/reviews/new" className="btn btn-primary">
          ✚ New Review
        </a>
      </div>

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
          <div className="spinner" style={{ width: 32, height: 32 }} />
        </div>
      ) : reviews.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">No reviews yet</div>
            <div className="empty-state-desc">
              Create your first scoping review project to begin.
            </div>
            <a href="/dashboard/reviews/new" className="btn btn-primary">
              Create Review
            </a>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          {reviews.map((review) => (
            <div key={review.id} className="card" style={{ cursor: "pointer" }}>
              <div className="flex items-center justify-between">
                <div style={{ flex: 1 }}>
                  <a
                    href={`/dashboard/reviews/${review.id}`}
                    style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 16, textDecoration: "none" }}
                  >
                    {review.title}
                  </a>
                  {review.description && (
                    <p className="text-sm text-muted mt-8" style={{ maxWidth: 600 }}>
                      {review.description}
                    </p>
                  )}
                  <div className="flex items-center gap-16 mt-8">
                    <span className={`badge badge-${review.status === 'completed' ? 'completed' : review.status === 'created' ? 'pending' : 'include'}`}>
                      {review.status}
                    </span>
                    <span className="text-xs text-muted">
                      {review.total_studies} studies
                    </span>
                    <span className="text-xs text-muted">
                      Created {new Date(review.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  <a href={`/dashboard/reviews/${review.id}`} className="btn btn-secondary btn-sm">
                    Open
                  </a>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(review.id);
                    }}
                    style={{ color: "var(--accent-rose)" }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
