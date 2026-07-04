// Admin panel: challenge CRUD, users, run history, simulator status.

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type {
  AdminUser,
  BatchRunSummary,
  ChallengeAdmin,
  RunRecord,
  SimulatorStatus,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToasts } from "../components/Toasts";

type Tab = "challenges" | "users" | "runs" | "simulator";

const EMPTY_FORM: ChallengeAdmin = {
  challenge_id: "",
  name: "",
  challenge_type: "DAILY",
  condition: "",
  reward_points: 100,
  priority: 10,
  is_active: true,
};

function ChallengeForm({
  initial,
  onDone,
}: {
  initial: ChallengeAdmin | null;
  onDone: () => void;
}) {
  const isEdit = initial !== null;
  const [form, setForm] = useState<ChallengeAdmin>(initial ?? EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { push } = useToasts();

  const save = useMutation({
    mutationFn: () =>
      isEdit
        ? api<ChallengeAdmin>(`/admin/challenges/${form.challenge_id}`, {
            method: "PUT",
            body: {
              name: form.name,
              challenge_type: form.challenge_type,
              condition: form.condition,
              reward_points: form.reward_points,
              priority: form.priority,
              is_active: form.is_active,
            },
          })
        : api<ChallengeAdmin>("/admin/challenges", {
            method: "POST",
            body: form,
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-challenges"] });
      push("info", isEdit ? "Challenge güncellendi." : "Challenge oluşturuldu.");
      onDone();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Kaydetme başarısız.");
    },
  });

  function set<K extends keyof ChallengeAdmin>(
    key: K,
    value: ChallengeAdmin[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <form className="admin-form" onSubmit={onSubmit}>
      <h3 className="admin-form-title">
        {isEdit ? `Düzenle: ${form.challenge_id}` : "Yeni Challenge"}
      </h3>
      <div className="admin-form-grid">
        {!isEdit && (
          <label>
            Challenge ID
            <input
              value={form.challenge_id}
              onChange={(e) => set("challenge_id", e.target.value)}
              placeholder="CH-100"
              required
            />
          </label>
        )}
        <label>
          İsim
          <input
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            required
          />
        </label>
        <label>
          Tür
          <select
            value={form.challenge_type}
            onChange={(e) => set("challenge_type", e.target.value)}
          >
            <option value="DAILY">DAILY</option>
            <option value="WEEKLY">WEEKLY</option>
            <option value="STREAK">STREAK</option>
          </select>
        </label>
        <label>
          Koşul (alan operatör tamsayı)
          <input
            value={form.condition}
            onChange={(e) => set("condition", e.target.value)}
            placeholder="watch_minutes_today >= 60"
            required
          />
        </label>
        <label>
          Ödül puanı
          <input
            type="number"
            min={1}
            value={form.reward_points}
            onChange={(e) => set("reward_points", Number(e.target.value))}
            required
          />
        </label>
        <label>
          Öncelik (küçük = öncelikli)
          <input
            type="number"
            min={1}
            value={form.priority}
            onChange={(e) => set("priority", Number(e.target.value))}
            required
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => set("is_active", e.target.checked)}
          />
          Aktif
        </label>
      </div>
      {error !== null && <div className="form-error">{error}</div>}
      <div className="admin-form-actions">
        <button className="btn-primary" disabled={save.isPending}>
          {save.isPending ? "Kaydediliyor…" : "Kaydet"}
        </button>
        <button type="button" className="btn-ghost" onClick={onDone}>
          Vazgeç
        </button>
      </div>
    </form>
  );
}

function ChallengesTab() {
  const [editing, setEditing] = useState<ChallengeAdmin | null>(null);
  const [creating, setCreating] = useState(false);
  const challenges = useQuery({
    queryKey: ["admin-challenges"],
    queryFn: () => api<ChallengeAdmin[]>("/admin/challenges"),
  });

  return (
    <div>
      {!creating && editing === null && (
        <button className="btn-primary" onClick={() => setCreating(true)}>
          + Yeni Challenge
        </button>
      )}
      {(creating || editing !== null) && (
        <ChallengeForm
          initial={editing}
          onDone={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      )}
      <table className="lb-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>İsim</th>
            <th>Koşul</th>
            <th className="num">Puan</th>
            <th className="num">Öncelik</th>
            <th>Durum</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(challenges.data ?? []).map((challenge) => (
            <tr key={challenge.challenge_id}>
              <td>{challenge.challenge_id}</td>
              <td>{challenge.name}</td>
              <td>
                <code className="challenge-condition">
                  {challenge.condition}
                </code>
              </td>
              <td className="num points-plus">+{challenge.reward_points}</td>
              <td className="num">{challenge.priority}</td>
              <td>
                {challenge.is_active ? (
                  <span className="status-on">aktif</span>
                ) : (
                  <span className="status-off">pasif</span>
                )}
              </td>
              <td>
                <button
                  className="btn-ghost"
                  onClick={() => setEditing(challenge)}
                >
                  Düzenle
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UsersTab() {
  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api<AdminUser[]>("/admin/users"),
  });

  return (
    <table className="lb-table">
      <thead>
        <tr>
          <th>Kullanıcı</th>
          <th>Rol</th>
          <th>Kayıt</th>
          <th className="num">Puan</th>
        </tr>
      </thead>
      <tbody>
        {(users.data ?? []).map((user) => (
          <tr key={user.id}>
            <td>
              {user.username}
              {user.is_bot && <span className="bot-tag">🤖 bot</span>}
            </td>
            <td>{user.is_admin ? "👑 admin" : "üye"}</td>
            <td>{new Date(`${user.created_at}Z`).toLocaleDateString("tr-TR")}</td>
            <td className="num lb-points">{user.total_points}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RunsTab() {
  const queryClient = useQueryClient();
  const { push } = useToasts();
  const runs = useQuery({
    queryKey: ["admin-runs"],
    queryFn: () => api<RunRecord[]>("/admin/runs"),
  });
  const trigger = useMutation({
    mutationFn: () =>
      api<BatchRunSummary>("/admin/batch-run", { method: "POST", body: {} }),
    onSuccess: (summary) => {
      push(
        "info",
        `Batch tamam: ${summary.users_processed} kullanıcı, ` +
          `${summary.new_rewards} yeni ödül, ${summary.new_badges} yeni rozet.`,
      );
      void queryClient.invalidateQueries({ queryKey: ["admin-runs"] });
    },
    onError: () => push("info", "Batch çalıştırılamadı."),
  });

  return (
    <div>
      <button
        className="btn-primary"
        onClick={() => trigger.mutate()}
        disabled={trigger.isPending}
      >
        {trigger.isPending ? "Çalışıyor…" : "▶ Batch'i şimdi çalıştır"}
      </button>
      <table className="lb-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Tarih</th>
            <th>Tip</th>
            <th>Durum</th>
            <th>Özet</th>
          </tr>
        </thead>
        <tbody>
          {(runs.data ?? []).map((run) => (
            <tr key={run.id}>
              <td>{run.id}</td>
              <td>{run.run_date}</td>
              <td>{run.run_type}</td>
              <td>
                <span
                  className={
                    run.status === "success" ? "status-on" : "status-off"
                  }
                >
                  {run.status}
                </span>
              </td>
              <td>
                <code className="challenge-condition">
                  {run.summary_json ?? "-"}
                </code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SimulatorTab() {
  const queryClient = useQueryClient();
  const { push } = useToasts();
  const [botCount, setBotCount] = useState(6);
  const [tickSeconds, setTickSeconds] = useState(5);

  const status = useQuery({
    queryKey: ["admin-simulator"],
    queryFn: () => api<SimulatorStatus>("/admin/simulator"),
    refetchInterval: 3_000,
  });

  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["admin-simulator"] });

  const start = useMutation({
    mutationFn: () =>
      api<SimulatorStatus>("/admin/simulator/start", {
        method: "POST",
        body: { bot_count: botCount, tick_seconds: tickSeconds },
      }),
    onSuccess: (data) => {
      push("info", `Simülatör başladı: ${data.bot_count} bot.`);
      refresh();
    },
    onError: (err) =>
      push("info", err instanceof ApiError ? err.message : "Başlatılamadı."),
  });

  const stop = useMutation({
    mutationFn: () =>
      api<SimulatorStatus>("/admin/simulator/stop", { method: "POST" }),
    onSuccess: () => {
      push("info", "Simülatör durduruldu.");
      refresh();
    },
  });

  const running = status.data?.running === true;

  return (
    <div className="sim-card">
      <h3>Trafik Simülatörü</h3>
      <p className="muted">
        Durum:{" "}
        {running ? (
          <span className="status-on">● çalışıyor</span>
        ) : (
          <span className="status-off">durdu</span>
        )}{" "}
        · {status.data?.bot_count ?? 0} bot · {status.data?.ticks_completed ?? 0}{" "}
        tur · {status.data?.events_recorded ?? 0} event
      </p>
      <p className="muted">
        Botlar (binge'çi / gündelik / eleştirmen) gerçek ingestion yolundan
        event üretir; günlük kotalar ve ödül kuralları onlara da aynen
        uygulanır. Liderlik tablosunda 🤖 ile görünürler.
      </p>
      {!running && (
        <div className="sim-controls">
          <label>
            Bot sayısı
            <input
              type="number"
              min={1}
              max={50}
              value={botCount}
              onChange={(e) => setBotCount(Number(e.target.value))}
            />
          </label>
          <label>
            Tur aralığı (sn)
            <input
              type="number"
              min={1}
              max={60}
              value={tickSeconds}
              onChange={(e) => setTickSeconds(Number(e.target.value))}
            />
          </label>
        </div>
      )}
      <div className="admin-form-actions">
        {running ? (
          <button
            className="btn-primary"
            onClick={() => stop.mutate()}
            disabled={stop.isPending}
          >
            ■ Durdur
          </button>
        ) : (
          <button
            className="btn-primary"
            onClick={() => start.mutate()}
            disabled={start.isPending}
          >
            ▶ Başlat
          </button>
        )}
      </div>
    </div>
  );
}

const TABS: { id: Tab; label: string }[] = [
  { id: "challenges", label: "Challenge'lar" },
  { id: "users", label: "Kullanıcılar" },
  { id: "runs", label: "Koşular" },
  { id: "simulator", label: "Simülatör" },
];

export function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("challenges");

  if (user !== null && !user.is_admin) {
    return <Navigate to="/" replace />;
  }
  return (
    <div className="admin-page">
      <h1 className="section-title">Yönetim Paneli</h1>
      <div className="tab-bar">
        {TABS.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? "tab tab-active" : "tab"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "challenges" && <ChallengesTab />}
      {tab === "users" && <UsersTab />}
      {tab === "runs" && <RunsTab />}
      {tab === "simulator" && <SimulatorTab />}
    </div>
  );
}
