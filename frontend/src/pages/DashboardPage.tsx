// User dashboard: profile, badges, challenge progress and point history.

import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Badge, ChallengeProgress, PointsResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ExplainBox } from "../components/ExplainBox";

const BADGE_ICONS: Record<string, string> = {
  BRONZE: "🥉",
  SILVER: "🥈",
  GOLD: "🥇",
};

function formatDate(iso: string): string {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ChallengeCard({ challenge }: { challenge: ChallengeProgress }) {
  return (
    <div className={challenge.won_today ? "challenge-card won" : "challenge-card"}>
      <div className="challenge-head">
        <span className="challenge-name">
          {challenge.won_today && "✅ "}
          {challenge.name}
        </span>
        <span className="challenge-points">+{challenge.reward_points}p</span>
      </div>
      <code className="challenge-condition">{challenge.condition}</code>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${challenge.progress_percent}%` }}
        />
      </div>
      <div className="challenge-foot">
        <span>
          {challenge.progress_current} / {challenge.progress_target}
        </span>
        <span>%{challenge.progress_percent}</span>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const points = useQuery({
    queryKey: ["points"],
    queryFn: () => api<PointsResponse>("/me/points"),
  });
  const badges = useQuery({
    queryKey: ["badges"],
    queryFn: () => api<Badge[]>("/me/badges"),
  });
  const challenges = useQuery({
    queryKey: ["challenges"],
    queryFn: () => api<ChallengeProgress[]>("/me/challenges"),
    refetchInterval: 30_000,
  });

  const history = [...(points.data?.entries ?? [])].reverse();

  return (
    <div className="dashboard">
      <div className="dash-top">
        <section className="profile-card">
          <div className="avatar">{user?.username.charAt(0).toUpperCase()}</div>
          <h1 className="profile-name">{user?.username}</h1>
          <div className="profile-points">
            <span className="big-number">{points.data?.total_points ?? 0}</span>
            <span className="big-label">toplam puan</span>
          </div>
          <div className="profile-badges">
            {(badges.data ?? []).length === 0 && (
              <span className="muted">
                Henüz rozet yok — 500 puanda Bronze seni bekliyor.
              </span>
            )}
            {(badges.data ?? []).map((badge) => (
              <span key={badge.badge_type} className="badge-chip">
                {BADGE_ICONS[badge.badge_type] ?? "🏅"} {badge.badge_type}
                <span className="badge-date">{badge.awarded_at}</span>
              </span>
            ))}
          </div>
        </section>

        <section className="challenges-panel">
          <h2 className="section-title">Bugünün Challenge'ları</h2>
          <p className="section-desc">
            İlerleme canlı hesaplanır; eşiği aştığın anda ödül düşer (günde
            bir ödül — öncelik motoru en değerlisini seçer).
          </p>
          <div className="challenge-grid">
            {(challenges.data ?? []).map((challenge) => (
              <ChallengeCard
                key={challenge.challenge_id}
                challenge={challenge}
              />
            ))}
          </div>
        </section>
      </div>

      <ExplainBox />

      <section>
        <h2 className="section-title">Puan Geçmişi</h2>
        {history.length === 0 ? (
          <p className="muted">
            Henüz puan hareketi yok — katalogdan bir video aç.
          </p>
        ) : (
          <table className="ledger-table">
            <thead>
              <tr>
                <th>Tarih</th>
                <th>Kaynak</th>
                <th>Referans</th>
                <th className="num">Puan</th>
              </tr>
            </thead>
            <tbody>
              {history.map((entry) => (
                <tr key={entry.ledger_id}>
                  <td>{formatDate(entry.created_at)}</td>
                  <td>{entry.source}</td>
                  <td>
                    <code>{entry.source_ref}</code>
                  </td>
                  <td className="num points-plus">+{entry.points_delta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
