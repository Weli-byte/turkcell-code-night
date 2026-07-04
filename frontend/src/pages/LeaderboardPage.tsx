// Live leaderboard with the viewer's own row highlighted.

import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { LeaderboardEntry } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const MEDALS: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };
const BADGE_ICONS: Record<string, string> = {
  BRONZE: "🥉",
  SILVER: "🥈",
  GOLD: "🥇",
};

export function LeaderboardPage() {
  const { user } = useAuth();
  const leaderboard = useQuery({
    queryKey: ["leaderboard"],
    queryFn: () => api<LeaderboardEntry[]>("/leaderboard"),
    refetchInterval: 15_000,
  });

  if (leaderboard.isLoading) {
    return <div className="page-center">Sıralama yükleniyor…</div>;
  }
  const rows = leaderboard.data ?? [];
  const myRank = rows.find((row) => row.user_id === user?.id);

  return (
    <div className="leaderboard-page">
      <div className="lb-header">
        <h1 className="section-title">Liderlik Tablosu</h1>
        <span className="lb-live">● CANLI</span>
      </div>
      {myRank !== undefined && (
        <p className="section-desc">
          Şu an <strong>#{myRank.rank}</strong> sıradasın —{" "}
          {myRank.total_points} puan.
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">Henüz puan kazanan yok. İlk sen ol!</p>
      ) : (
        <table className="lb-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Kullanıcı</th>
              <th>Rozetler</th>
              <th className="num">Puan</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.user_id}
                className={row.user_id === user?.id ? "lb-me" : undefined}
              >
                <td className="lb-rank">
                  {MEDALS[row.rank] ?? `#${row.rank}`}
                </td>
                <td>
                  {row.username}
                  {row.user_id === user?.id && (
                    <span className="me-tag">sen</span>
                  )}
                  {row.is_bot && <span className="bot-tag">🤖 bot</span>}
                </td>
                <td>
                  {row.badges.map((badge) => (
                    <span key={badge} title={badge} className="lb-badge">
                      {BADGE_ICONS[badge] ?? "🏅"}
                    </span>
                  ))}
                </td>
                <td className="num lb-points">{row.total_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
