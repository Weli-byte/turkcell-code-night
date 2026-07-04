// Registration screen.

import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user !== null) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Parola en az 8 karakter olmalı.");
      return;
    }
    setBusy(true);
    try {
      await register(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kayıt başarısız oldu.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-center">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1 className="auth-title">
          <span className="brand-dot">●</span> DGE
        </h1>
        <p className="auth-sub">Yeni hesap oluştur — izle, puan kazan</p>
        <label>
          Kullanıcı adı
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            minLength={3}
            pattern="[a-zA-Z0-9_.\-]+"
            title="Harf, rakam, alt çizgi, nokta ve tire kullanılabilir"
            required
          />
        </label>
        <label>
          Parola (en az 8 karakter)
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        {error !== null && <div className="form-error">{error}</div>}
        <button className="btn-primary" disabled={busy}>
          {busy ? "Kaydediliyor…" : "Kayıt Ol"}
        </button>
        <p className="auth-switch">
          Zaten hesabın var mı? <Link to="/login">Giriş yap</Link>
        </p>
      </form>
    </div>
  );
}
