// Protected shell: navbar with live points + routed content.

import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, Outlet } from "react-router-dom";

import { api } from "../api/client";
import type { PointsResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export function ProtectedLayout() {
  const { user, loading, logout } = useAuth();

  const points = useQuery({
    queryKey: ["points"],
    queryFn: () => api<PointsResponse>("/me/points"),
    enabled: user !== null,
    refetchInterval: 30_000,
  });

  if (loading) {
    return <div className="page-center">Yükleniyor…</div>;
  }
  if (user === null) {
    return <Navigate to="/login" replace />;
  }
  return (
    <div className="shell">
      <header className="navbar">
        <Link to="/" className="brand">
          <span className="brand-dot">●</span> DGE <span className="brand-sub">/platform</span>
        </Link>
        <nav className="nav-links">
          <Link to="/">Katalog</Link>
        </nav>
        <div className="nav-right">
          <span className="points-chip" title="Toplam puanın">
            ⭐ {points.data?.total_points ?? 0}
          </span>
          <span className="username">{user.username}</span>
          <button className="btn-ghost" onClick={logout}>
            Çıkış
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
