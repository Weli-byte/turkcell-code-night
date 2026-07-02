"""
State Processor for Gamification System.

Builds a consolidated per-user state DataFrame from raw activity data,
computing daily, 7-day rolling, and streak engagement metrics.
"""

import pandas as pd
from datetime import timedelta


def build_user_state(activity_df: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    """Build a per-user engagement state DataFrame from activity records.

    Computes today metrics, 7-day rolling metrics, and watch-streak days
    for every user present in the activity data.

    Expected DataFrame columns:
        user_id, date, watch_minutes, episodes_completed,
        unique_genres, watch_party_minutes, ratings

    Args:
        activity_df: A pandas DataFrame containing raw activity records
            for all users.
        as_of_date: The reference date as a string (YYYY-MM-DD).

    Returns:
        A pandas DataFrame with one row per user_id and columns:
            watch_minutes_today, episodes_completed_today,
            unique_genres_today, watch_party_minutes_today, ratings_today,
            watch_minutes_7d, episodes_completed_7d, ratings_7d,
            watch_streak_days.
    """
    df = activity_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    ref_date = pd.Timestamp(as_of_date).date()

    today_metrics = _compute_today_metrics(df, ref_date)
    seven_day_metrics = _compute_7d_metrics(df, ref_date)
    streak_metrics = _compute_streak(df, ref_date)

    result = (
        today_metrics
        .merge(seven_day_metrics, on="user_id", how="outer")
        .merge(streak_metrics, on="user_id", how="outer")
    )

    fill_values = {
        "watch_minutes_today": 0.0,
        "episodes_completed_today": 0,
        "unique_genres_today": 0,
        "watch_party_minutes_today": 0.0,
        "ratings_today": 0,
        "watch_minutes_7d": 0.0,
        "episodes_completed_7d": 0,
        "ratings_7d": 0,
        "watch_streak_days": 0,
    }
    result = result.fillna(fill_values)

    int_cols = [
        "episodes_completed_today", "unique_genres_today", "ratings_today",
        "episodes_completed_7d", "ratings_7d", "watch_streak_days",
    ]
    result[int_cols] = result[int_cols].astype(int)

    return result.reset_index(drop=True)


def _compute_today_metrics(df: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    """Aggregate today's engagement metrics grouped by user_id.

    Args:
        df: Activity DataFrame with a datetime 'date' column.
        ref_date: The target date.

    Returns:
        DataFrame with columns: user_id, watch_minutes_today,
        episodes_completed_today, unique_genres_today,
        watch_party_minutes_today, ratings_today.
    """
    today_df = df[df["date"] == ref_date]

    if today_df.empty:
        return pd.DataFrame(columns=[
            "user_id", "watch_minutes_today", "episodes_completed_today",
            "unique_genres_today", "watch_party_minutes_today", "ratings_today",
        ])

    agg = (
        today_df
        .groupby("user_id", as_index=False)
        .agg(
            watch_minutes_today=("watch_minutes", "sum"),
            episodes_completed_today=("episodes_completed", "sum"),
            unique_genres_today=("unique_genres", "sum"),
            watch_party_minutes_today=("watch_party_minutes", "sum"),
            ratings_today=("ratings", "sum"),
        )
    )
    return agg


def _compute_7d_metrics(df: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    """Aggregate 7-day rolling engagement metrics grouped by user_id.

    The window covers [ref_date - 6 days, ref_date] inclusive.

    Args:
        df: Activity DataFrame with a datetime 'date' column.
        ref_date: The anchor date for the rolling window.

    Returns:
        DataFrame with columns: user_id, watch_minutes_7d,
        episodes_completed_7d, ratings_7d.
    """
    start_date = ref_date - timedelta(days=6)
    window_df = df[(df["date"] >= start_date) & (df["date"] <= ref_date)]

    if window_df.empty:
        return pd.DataFrame(columns=[
            "user_id", "watch_minutes_7d", "episodes_completed_7d", "ratings_7d",
        ])

    agg = (
        window_df
        .groupby("user_id", as_index=False)
        .agg(
            watch_minutes_7d=("watch_minutes", "sum"),
            episodes_completed_7d=("episodes_completed", "sum"),
            ratings_7d=("ratings", "sum"),
        )
    )
    return agg


def _compute_streak(df: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    """Compute consecutive watch-streak days per user ending on *ref_date*.

    A day qualifies toward the streak only if the user's total
    watch_minutes on that day is >= 30.

    Pre-aggregates daily totals per user to avoid repeated full-dataset
    filtering inside loops.

    Args:
        df: Activity DataFrame with a datetime 'date' column.
        ref_date: The anchor date for streak calculation.

    Returns:
        DataFrame with columns: user_id, watch_streak_days.
    """
    daily = (
        df.groupby(["user_id", "date"], as_index=False)["watch_minutes"]
        .sum()
        .rename(columns={"watch_minutes": "total_minutes"})
    )

    user_ids = daily["user_id"].unique()
    streaks: list[dict] = []

    for uid in user_ids:
        user_daily = daily[daily["user_id"] == uid].set_index("date")["total_minutes"]
        streak = 0
        current_date = ref_date

        while True:
            if current_date not in user_daily.index:
                break
            if user_daily[current_date] < 30.0:
                break
            streak += 1
            current_date -= timedelta(days=1)

        streaks.append({"user_id": uid, "watch_streak_days": streak})

    return pd.DataFrame(streaks)
