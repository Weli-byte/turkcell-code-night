// Lightweight toast stack for reward/badge celebrations.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface Toast {
  id: number;
  kind: "reward" | "badge" | "info";
  message: string;
}

interface ToastState {
  toasts: Toast[];
  push: (kind: Toast["kind"], message: string) => void;
}

const ToastContext = createContext<ToastState | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const push = useCallback((kind: Toast["kind"], message: string) => {
    setToasts((current) => {
      // The same reward can arrive twice (event response + SSE); dedupe
      // identical messages that are still on screen.
      if (current.some((toast) => toast.message === message)) {
        return current;
      }
      const id = nextId.current++;
      window.setTimeout(() => {
        setToasts((live) => live.filter((toast) => toast.id !== id));
      }, 5000);
      return [...current, { id, kind, message }];
    });
  }, []);

  const value = useMemo(() => ({ toasts, push }), [toasts, push]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.kind}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToasts(): ToastState {
  const context = useContext(ToastContext);
  if (context === null) {
    throw new Error("useToasts must be used inside ToastProvider");
  }
  return context;
}
