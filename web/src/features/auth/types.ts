export const USER_ROLES = ["FAN", "ORGANIZER", "SCANNER", "ADMIN"] as const;

export type UserRole = (typeof USER_ROLES)[number];

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  created_at: string;
}

export interface AuthDevice {
  id: string;
  label: string;
  bound_at: string;
}

export interface LoginResponse {
  access: string;
  user: AuthUser;
  device: AuthDevice | null;
}
