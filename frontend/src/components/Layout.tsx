// Protected shell: navbar with live points + routed content.

import { useQuery } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet } from "react-router-dom";

import { api } from "../api/client";
import type { PointsResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useNotificationStream } from "../hooks/useNotificationStream";
import { NotificationBell } from "./NotificationBell";

export function ProtectedLayout() {
  const { user, loading, logout } = useAuth();

  const points = useQuery({
    queryKey: ["points"],
    queryFn: () => api<PointsResponse>("/me/points"),
    enabled: user !== null,
    refetchInterval: 30_000,
  });
  useNotificationStream(user !== null);

  if (loading) {
    return <div className="page-center">Yükleniyor…</div>;
  }
  if (user === null) {
    return <Navigate to="/login" replace />;
  }
  return (
    <div className="shell">
      <header className="navbar">
        <NavLink to="/" className="brand">
          <span className="brand-dot">●</span> DGE{" "}
          <span className="brand-sub">/platform</span>
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/" end>
            Katalog
          </NavLink>
          <NavLink to="/dashboard">Panelim</NavLink>
          <NavLink to="/leaderboard">Liderlik</NavLink>
        </nav>
        <div className="nav-right">
          <span className="points-chip" title="Toplam puanın">
            ⭐ {points.data?.total_points ?? 0}
          </span>
          <NotificationBell />
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
