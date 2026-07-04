// API response/request shapes mirroring gamification_backend/api/schemas.py.

export interface User {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Video {
  id: string;
  series_id: string | null;
  title: string;
  genre: string;
  duration_seconds: number;
  url: string;
  episode_number: number | null;
}

export interface Series {
  id: string;
  title: string;
  genre: string;
  description: string | null;
  episodes: Video[];
}

export interface Catalog {
  series: Series[];
  films: Video[];
}

export interface RewardInfo {
  challenge_id: string;
  challenge_name: string;
  points: number;
}

export interface EventResponse {
  status: string;
  counted: boolean;
  reward: RewardInfo | null;
  new_badges: string[];
}

export interface LedgerEntry {
  ledger_id: string;
  points_delta: number;
  source: string;
  source_ref: string;
  created_at: string;
}

export interface PointsResponse {
  total_points: number;
  entries: LedgerEntry[];
}

export interface Badge {
  badge_type: string;
  awarded_at: string;
}

export interface ChallengeProgress {
  challenge_id: string;
  name: string;
  condition: string;
  reward_points: number;
  priority: number;
  progress_current: number;
  progress_target: number;
  progress_percent: number;
  satisfied: boolean;
  won_today: boolean;
}

export interface ChallengeAdmin {
  challenge_id: string;
  name: string;
  challenge_type: string;
  condition: string;
  reward_points: number;
  priority: number;
  is_active: boolean;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  is_bot: boolean;
  created_at: string;
  total_points: number;
}

export interface RunRecord {
  id: number;
  run_date: string;
  run_type: string;
  status: string;
  executed_at: string;
  summary_json: string | null;
}

export interface BatchRunSummary {
  run_date: string;
  users_processed: number;
  new_rewards: number;
  new_badges: number;
  new_notifications: number;
  leaderboard_size: number;
}

export interface SimulatorStatus {
  running: boolean;
  bot_count: number;
  tick_seconds: number;
  ticks_completed: number;
  events_recorded: number;
  detail: string;
}

export interface ExplainResponse {
  user_id: string;
  question: string;
  answer: string;
  evidence: Record<string, unknown>;
}

export interface NotificationItem {
  notification_id: string;
  notification_type: string;
  channel: string;
  message: string;
  source_ref: string;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: string;
  username: string;
  total_points: number;
  badges: string[];
  is_bot: boolean;
}
