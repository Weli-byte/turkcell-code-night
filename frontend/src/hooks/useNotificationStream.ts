// Live notification stream over SSE.
//
// EventSource cannot send headers, so the token travels as a query
// parameter (matching the backend's /sse/notifications contract). The
// browser auto-reconnects on drops.

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { getToken } from "../api/client";
import { useToasts } from "../components/Toasts";

interface StreamPayload {
  type: string;
  message: string;
}

export function useNotificationStream(enabled: boolean): void {
  const { push } = useToasts();
  const queryClient = useQueryClient();

  useEffect(() => {
    const token = getToken();
    if (!enabled || token === null) {
      return;
    }
    const source = new EventSource(
      `/sse/notifications?token=${encodeURIComponent(token)}`,
    );
    const onNotification = (event: MessageEvent<string>) => {
      let payload: StreamPayload;
      try {
        payload = JSON.parse(event.data) as StreamPayload;
      } catch {
        return;
      }
      push(payload.type === "BADGE_EARNED" ? "badge" : "reward", payload.message);
      void queryClient.invalidateQueries({ queryKey: ["points"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["challenges"] });
      void queryClient.invalidateQueries({ queryKey: ["badges"] });
      void queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    };
    source.addEventListener("notification", onNotification);
    return () => {
      source.removeEventListener("notification", onNotification);
      source.close();
    };
  }, [enabled, push, queryClient]);
}
