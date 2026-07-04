// Navbar bell: unread count + dropdown listing stored notifications.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { NotificationItem } from "../api/types";

const SEEN_KEY = "dge_notifications_seen";

function lastSeen(): string {
  return localStorage.getItem(SEEN_KEY) ?? "";
}

function formatTime(iso: string): string {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(lastSeen());
  const containerRef = useRef<HTMLDivElement | null>(null);

  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationItem[]>("/me/notifications"),
    refetchInterval: 60_000,
  });

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (
        containerRef.current !== null &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const items = notifications.data ?? [];
  const unread = items.filter((item) => item.created_at > seen).length;

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && items.length > 0) {
      const newest = items[0].created_at;
      localStorage.setItem(SEEN_KEY, newest);
      setSeen(newest);
    }
  }

  return (
    <div className="bell-wrap" ref={containerRef}>
      <button
        className="btn-ghost bell-button"
        onClick={toggle}
        title="Bildirimler"
      >
        🔔
        {unread > 0 && <span className="bell-count">{unread}</span>}
      </button>
      {open && (
        <div className="bell-dropdown">
          <div className="bell-header">Bildirimler</div>
          {items.length === 0 && (
            <div className="bell-empty">
              Henüz bildirim yok — izlemeye başla, ödüller düşsün.
            </div>
          )}
          {items.slice(0, 20).map((item) => (
            <div key={item.notification_id} className="bell-item">
              <span className="bell-message">{item.message}</span>
              <span className="bell-time">{formatTime(item.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
