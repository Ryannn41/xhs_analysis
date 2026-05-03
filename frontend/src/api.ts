const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export interface AccountRef {
  input: string;
  user_id: string;
  nickname: string;
  profile_url: string;
}

export interface Profile {
  user_id: string;
  nickname: string;
  desc: string;
  red_id: string;
  gender: string | number;
  ip_location: string;
  [key: string]: string | number;
}

export interface AccountStats {
  followers_display: string;
  followers_count: number;
  period_start: string;
  period_end: string;
  period_note_count: number;
  period_liked_total: number;
  period_collected_total: number;
  period_comment_total: number;
  period_share_total: number;
  scanned_note_count: number;
  reached_range_start: boolean;
}

export interface Note {
  note_id: string;
  title: string;
  desc: string;
  type: string;
  liked_count: number;
  collected_count: number;
  comment_count: number;
  share_count: number;
  time: string;
  cover_url: string;
  url: string;
  liked_count_display?: string;
  collected_count_display?: string;
  comment_count_display?: string;
  share_count_display?: string;
  last_update_time?: string;
}

export interface AccountResult {
  account: AccountRef;
  profile: Profile;
  notes: Note[];
  stats: AccountStats;
  source: string;
  fetched_at: string;
}

export interface AccountInput {
  name: string;
  id: string;
}

export interface CurrentUser {
  nickname?: string;
  avatar_url?: string;
  profile_url?: string;
  red_id?: string;
}

export interface SessionStatus {
  has_login_state: boolean;
  storage_state: string;
  storage_state_updated_at: string | null;
  current_user: CurrentUser | null;
  login_in_progress: boolean;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

export async function fetchAccountProfile(
  account: string,
  startDate = "",
  endDate = "",
): Promise<AccountResult> {
  const response = await fetch(`${API_BASE_URL}/api/xhs/profile`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      account,
      start_date: startDate || null,
      end_date: endDate || null,
    }),
  });

  return parseJsonResponse<AccountResult>(response);
}

export async function fetchSessionStatus(): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE_URL}/api/xhs/session`);
  return parseJsonResponse<SessionStatus>(response);
}

export async function startLoginSession(): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE_URL}/api/xhs/session/login/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  return parseJsonResponse<SessionStatus>(response);
}

export async function saveLoginSession(): Promise<SessionStatus> {
  const response = await fetch(`${API_BASE_URL}/api/xhs/session/login/save`, {
    method: "POST",
  });
  return parseJsonResponse<SessionStatus>(response);
}
