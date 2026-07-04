// Player page: measures real watch time and reports it to the engine.
//
// Measurement strategy: `timeupdate` deltas are accumulated only while the
// video advances normally (0 < delta < 2s), so seeking/paused time never
// counts. Accumulated seconds are flushed as heartbeats every 15s and on
// pause/end/unmount. Completion fires once on `ended`.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { EventResponse, Video } from "../api/types";
import { useToasts } from "../components/Toasts";

const HEARTBEAT_INTERVAL_MS = 15_000;
const MAX_SECONDS_PER_REPORT = 300;

export function WatchPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const { push } = useToasts();
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pendingSecondsRef = useRef(0);
  const lastTimeRef = useRef<number | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  const video = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => api<Video>(`/catalog/videos/${videoId}`),
    enabled: videoId !== undefined,
  });

  const celebrate = useCallback(
    (response: EventResponse) => {
      if (response.reward !== null) {
        push(
          "reward",
          `🎉 '${response.reward.challenge_name}' tamamlandı: +${response.reward.points} puan!`,
        );
      }
      for (const badge of response.new_badges) {
        push("badge", `🏆 ${badge} rozetini kazandın!`);
      }
      if (response.counted) {
        void queryClient.invalidateQueries({ queryKey: ["points"] });
      }
    },
    [push, queryClient],
  );

  const sendHeartbeat = useMutation({
    mutationFn: (seconds: number) =>
      api<EventResponse>("/events/heartbeat", {
        method: "POST",
        body: { video_id: videoId, watch_seconds: seconds },
      }),
    onSuccess: celebrate,
  });

  const sendComplete = useMutation({
    mutationFn: () =>
      api<EventResponse>("/events/complete", {
        method: "POST",
        body: { video_id: videoId },
      }),
    onSuccess: (response) => {
      celebrate(response);
      if (response.counted) {
        push("info", "✅ Bölüm tamamlandı olarak sayıldı.");
      }
    },
  });

  const sendRating = useMutation({
    mutationFn: (value: number) =>
      api<EventResponse>("/events/rating", {
        method: "POST",
        body: { video_id: videoId, rating: value },
      }),
    onSuccess: (response, value) => {
      celebrate(response);
      push(
        "info",
        response.counted
          ? `⭐ ${value} yıldız verdin.`
          : "Bu videoyu zaten puanlamışsın.",
      );
    },
  });

  const flush = useCallback(() => {
    const whole = Math.floor(pendingSecondsRef.current);
    if (whole < 1 || videoId === undefined) {
      return;
    }
    pendingSecondsRef.current -= whole;
    sendHeartbeat.mutate(Math.min(whole, MAX_SECONDS_PER_REPORT));
  }, [sendHeartbeat, videoId]);

  useEffect(() => {
    const timer = window.setInterval(flush, HEARTBEAT_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      flush();
    };
  }, [flush]);

  function onTimeUpdate() {
    const element = videoRef.current;
    if (element === null || element.paused || element.seeking) {
      lastTimeRef.current = element?.currentTime ?? null;
      return;
    }
    const current = element.currentTime;
    const last = lastTimeRef.current;
    if (last !== null) {
      const delta = current - last;
      if (delta > 0 && delta < 2) {
        pendingSecondsRef.current += delta;
      }
    }
    lastTimeRef.current = current;
  }

  function onEnded() {
    flush();
    sendComplete.mutate();
  }

  function onRate(value: number) {
    setRating(value);
    sendRating.mutate(value);
  }

  if (video.isLoading) {
    return <div className="page-center">Video yükleniyor…</div>;
  }
  if (video.isError || video.data === undefined) {
    return (
      <div className="page-center">
        Video bulunamadı. <Link to="/">Kataloğa dön</Link>
      </div>
    );
  }
  return (
    <div className="watch">
      <Link to="/" className="back-link">
        ← Katalog
      </Link>
      <div className="player-frame">
        <video
          ref={videoRef}
          src={video.data.url}
          controls
          preload="metadata"
          onTimeUpdate={onTimeUpdate}
          onPause={flush}
          onEnded={onEnded}
        />
      </div>
      <div className="watch-info">
        <div>
          <h1 className="watch-title">{video.data.title}</h1>
          <p className="watch-sub">
            {video.data.genre}
            {video.data.episode_number !== null &&
              ` · ${video.data.episode_number}. bölüm`}
            {" · "}
            {Math.floor(video.data.duration_seconds / 60)} dk{" "}
            {video.data.duration_seconds % 60} sn
          </p>
        </div>
        <div className="rating" aria-label="Videoyu puanla">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              className={
                (hover ?? rating ?? 0) >= value ? "star star-on" : "star"
              }
              onMouseEnter={() => setHover(value)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onRate(value)}
              title={`${value} yıldız`}
            >
              ★
            </button>
          ))}
        </div>
      </div>
      <p className="watch-hint">
        İzlediğin her saniye ölçülür ve 15 saniyede bir motora raporlanır —
        eşikleri aştığın anda ödül bildirimi düşer.
      </p>
    </div>
  );
}
