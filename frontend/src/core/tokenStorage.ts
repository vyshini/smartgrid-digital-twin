import type { User } from './types';

const ACCESS_TOKEN_KEY = 'smartgrid.access_token';
const REFRESH_TOKEN_KEY = 'smartgrid.refresh_token';
const USER_KEY = 'smartgrid.user';

export interface SessionTokens {
  accessToken: string;
  refreshToken: string;
  user: User;
}

export function readSession(): SessionTokens | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  const userRaw = localStorage.getItem(USER_KEY);
  if (!accessToken || !refreshToken || !userRaw) {
    return null;
  }
  return {
    accessToken,
    refreshToken,
    user: JSON.parse(userRaw) as User,
  };
}

export function writeSession(session: SessionTokens): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
  localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearSessionStorage(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
