"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Review, ReviewWithStats, ReviewStats } from "@/lib/api";

// Sidebar component
function Sidebar({ activePath }: { activePath: string }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">SR</div>
        <div>
          <h1>Scoping Review</h1>
          <span>AI Analysis Platform</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-title">Overview</div>
          <a href="/dashboard" className={`sidebar-link ${activePath === '/dashboard' ? 'active' : ''}`}>
            <span className="sidebar-link-icon">📊</span>
            Dashboard
          </a>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Manage</div>
          <a href="/dashboard/reviews" className={`sidebar-link ${activePath.includes('/reviews') ? 'active' : ''}`}>
            <span className="sidebar-link-icon">📋</span>
            Reviews
          </a>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Account</div>
          <a
            href="#"
            className="sidebar-link"
            onClick={(e) => {
              e.preventDefault();
              api.clearToken();
              window.location.href = "/";
            }}
          >
            <span className="sidebar-link-icon">🚪</span>
            Sign Out
          </a>
        </div>
      </nav>
    </aside>
  );
}

// Header component
function Header({ title, user }: { title: string; user: any }) {
  return (
    <header className="header">
      <h2 className="header-title">{title}</h2>
      <div className="header-actions">
        <div className="header-user">
          <div className="header-avatar">
            {user?.full_name?.[0] || user?.email?.[0] || "U"}
          </div>
          <span>{user?.full_name || user?.email || "User"}</span>
        </div>
      </div>
    </header>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      window.location.href = "/";
      return;
    }

    api
      .getMe()
      .then(setUser)
      .catch(() => {
        api.clearToken();
        window.location.href = "/";
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}>
        <div className="spinner" style={{ width: 40, height: 40 }} />
      </div>
    );
  }

  return (
    <div className="app-layout">
      <Sidebar activePath={typeof window !== "undefined" ? window.location.pathname : "/dashboard"} />
      <Header title="Scoping Review AI" user={user} />
      <main className="main-content">
        <div className="page-container">
          {children}
        </div>
      </main>
    </div>
  );
}
