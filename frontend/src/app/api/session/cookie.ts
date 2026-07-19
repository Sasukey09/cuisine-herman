/** Shared config for the session (refresh-token) cookie. Server-only. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const REFRESH_COOKIE = "fg_rt";

// Matches the backend REFRESH_TOKEN_EXPIRE_MINUTES default (14 days).
const REFRESH_MAX_AGE = 60 * 60 * 24 * 14;

type CookieOptions = {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: string;
  maxAge: number;
};

export function refreshCookieOptions(maxAge: number = REFRESH_MAX_AGE): CookieOptions {
  return {
    httpOnly: true,
    // Secure everywhere except plain-http local dev, where it would be dropped.
    secure: process.env.NODE_ENV === "production",
    // Lax: the cookie is never sent on a cross-site POST, so an attacker page
    // cannot drive /api/session/* on the user's behalf (CSRF). Same-origin
    // fetches from our own app still carry it.
    sameSite: "lax",
    path: "/",
    maxAge,
  };
}
