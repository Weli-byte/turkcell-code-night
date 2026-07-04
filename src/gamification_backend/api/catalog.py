"""Public catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from gamification_backend.api.deps import SessionDep
from gamification_backend.api.schemas import (
    CatalogResponse,
    SeriesResponse,
    VideoResponse,
)
from gamification_backend.repositories.catalog import (
    episodes_of,
    get_video,
    list_series,
    standalone_films,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
def read_catalog(session: SessionDep) -> CatalogResponse:
    """The full catalog: series (with episodes) and standalone films."""

    series = [
        SeriesResponse(
            id=record.id,
            title=record.title,
            genre=record.genre,
            description=record.description,
            episodes=[
                VideoResponse.model_validate(video)
                for video in episodes_of(session, record.id)
            ],
        )
        for record in list_series(session)
    ]
    films = [VideoResponse.model_validate(video) for video in standalone_films(session)]
    return CatalogResponse(series=series, films=films)


@router.get("/videos/{video_id}")
def read_video(video_id: str, session: SessionDep) -> VideoResponse:
    """A single catalog video."""

    video = get_video(session, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video bulunamadı."
        )
    return VideoResponse.model_validate(video)
