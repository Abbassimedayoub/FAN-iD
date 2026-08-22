export interface SessionDevice {
  id: string;
  label: string;
}

export interface AuthSession {
  id: string;
  device: SessionDevice | null;
  ip: string | null;
  user_agent: string;
  issued_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
}
