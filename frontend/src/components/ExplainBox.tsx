// "Why am I at this score?" — chat box backed by the deterministic
// explanation engine (optionally LLM-rephrased on the server).

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "../api/client";
import type { ExplainResponse } from "../api/types";

const QUICK_QUESTIONS = [
  "Kaç puanım var?",
  "Liderlik tablosunda neden bu sıradayım?",
  "Gold rozetine ulaşmak için ne yapmalıyım?",
  "Neden bu ödülü kazandım?",
];

interface ChatEntry {
  question: string;
  answer: string;
  evidence: Record<string, unknown>;
}

export function ExplainBox() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<ChatEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const ask = useMutation({
    mutationFn: (q: string) =>
      api<ExplainResponse>("/explain", { method: "POST", body: { question: q } }),
    onSuccess: (data) => {
      setHistory((current) => [
        { question: data.question, answer: data.answer, evidence: data.evidence },
        ...current,
      ]);
      setQuestion("");
      setError(null);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Soru cevaplanamadı.");
    },
  });

  function submit(q: string) {
    const trimmed = q.trim();
    if (trimmed.length < 3 || ask.isPending) {
      return;
    }
    ask.mutate(trimmed);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit(question);
  }

  return (
    <section className="explain-box">
      <h2 className="section-title">🤖 AI Asistan</h2>
      <p className="section-desc">
        Puanın, sıran, rozetlerin ve ödüllerin hakkında soru sor — cevap
        deterministik motordan gelir, kanıtıyla birlikte.
      </p>
      <div className="quick-questions">
        {QUICK_QUESTIONS.map((item) => (
          <button
            key={item}
            className="chip"
            onClick={() => submit(item)}
            disabled={ask.isPending}
          >
            {item}
          </button>
        ))}
      </div>
      <form className="explain-form" onSubmit={onSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Sorunu yaz… (örn. Kaç puanım var?)"
          maxLength={300}
        />
        <button className="btn-primary" disabled={ask.isPending}>
          {ask.isPending ? "Düşünüyor…" : "Sor →"}
        </button>
      </form>
      {error !== null && <div className="form-error">{error}</div>}
      <div className="chat-history">
        {history.map((entry, index) => (
          <div key={`${entry.question}-${index}`} className="chat-entry">
            <div className="chat-question">Sen: {entry.question}</div>
            <div className="chat-answer">{entry.answer}</div>
            {Object.keys(entry.evidence).length > 0 && (
              <details className="chat-evidence">
                <summary>Kanıt (evidence)</summary>
                <pre>{JSON.stringify(entry.evidence, null, 2)}</pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
