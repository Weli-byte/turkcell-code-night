// Catalog: series with episodes plus standalone films.

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { Catalog, Video } from "../api/types";

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  if (minutes < 1) {
    return `${seconds} sn`;
  }
  return `${minutes} dk`;
}

function VideoCard({ video }: { video: Video }) {
  return (
    <Link to={`/watch/${video.id}`} className="video-card">
      <div className="video-thumb">
        <span className="play-icon">▶</span>
      </div>
      <div className="video-meta">
        <span className="video-title">
          {video.episode_number !== null && (
            <span className="ep-badge">B{video.episode_number}</span>
          )}
          {video.title}
        </span>
        <span className="video-sub">
          {video.genre} · {formatDuration(video.duration_seconds)}
        </span>
      </div>
    </Link>
  );
}

export function CatalogPage() {
  const catalog = useQuery({
    queryKey: ["catalog"],
    queryFn: () => api<Catalog>("/catalog"),
  });

  if (catalog.isLoading) {
    return <div className="page-center">Katalog yükleniyor…</div>;
  }
  if (catalog.isError || catalog.data === undefined) {
    return <div className="page-center">Katalog yüklenemedi.</div>;
  }
  return (
    <div className="catalog">
      <section>
        <h2 className="section-title">Filmler</h2>
        <div className="video-grid">
          {catalog.data.films.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      </section>
      {catalog.data.series.map((series) => (
        <section key={series.id}>
          <h2 className="section-title">
            {series.title} <span className="genre-tag">{series.genre}</span>
          </h2>
          {series.description !== null && (
            <p className="section-desc">{series.description}</p>
          )}
          <div className="video-grid">
            {series.episodes.map((video) => (
              <VideoCard key={video.id} video={video} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
