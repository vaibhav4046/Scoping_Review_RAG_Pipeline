"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { ReviewWithStats } from "@/lib/api";

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check if already logged in
    if (api.getToken()) {
      window.location.href = "/dashboard";
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        await api.login(email, password);
      } else {
        await api.register(email, password, fullName);
        await api.login(email, password);
      }
      window.location.href = "/dashboard";
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">SR</div>
          <h2>Scoping Review AI</h2>
          <p>Automated Literature Analysis Platform</p>
        </div>

        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="input-group">
              <label className="input-label">Full Name</label>
              <input
                type="text"
                className="input"
                placeholder="Dr. Jane Smith"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
          )}

          <div className="input-group">
            <label className="input-label">Email</label>
            <input
              type="email"
              className="input"
              placeholder="you@institution.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="input-group">
            <label className="input-label">Password</label>
            <input
              type="password"
              className="input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <div style={{ color: "var(--accent-rose)", fontSize: "13px", marginBottom: "16px" }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary w-full btn-lg"
            disabled={loading}
          >
            {loading ? (
              <span className="spinner" />
            ) : isLogin ? (
              "Sign In"
            ) : (
              "Create Account"
            )}
          </button>
        </form>

        <div className="auth-footer">
          {isLogin ? (
            <>
              Don&apos;t have an account?{" "}
              <a href="#" onClick={() => setIsLogin(false)}>
                Register
              </a>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <a href="#" onClick={() => setIsLogin(true)}>
                Sign In
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
