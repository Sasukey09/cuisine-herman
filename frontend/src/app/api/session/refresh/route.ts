import { NextRequest, NextResponse } from "next/server";

import { API_BASE, REFRESH_COOKIE, refreshCookieOptions } from "../cookie";

/**
 * Mints a fresh access token from the httpOnly refresh cookie. Called on 401
 * and on app boot (to restore a session across reloads without any token ever
 * touching localStorage). Rotates the refresh cookie on success; clears it when
 * the session is gone.
 */
export async function POST(request: NextRequest) {
  const rt = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!rt) {
    return NextResponse.json({ detail: "Session absente" }, { status: 401 });
  }

  const upstream = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
    cache: "no-store",
  });

  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok || !data?.access_token || !data?.refresh_token) {
    const res = NextResponse.json({ detail: "Session expirée" }, { status: 401 });
    res.cookies.set(REFRESH_COOKIE, "", refreshCookieOptions(0));
    return res;
  }

  const res = NextResponse.json({ access_token: data.access_token });
  res.cookies.set(REFRESH_COOKIE, data.refresh_token, refreshCookieOptions());
  return res;
}
