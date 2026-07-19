import { NextRequest, NextResponse } from "next/server";

import { API_BASE, REFRESH_COOKIE, refreshCookieOptions } from "../cookie";

/**
 * Revokes the session server-side (bumps token_version so every issued token
 * dies) and clears the refresh cookie. Best-effort on the upstream call: a
 * network blip must never trap the user signed in locally.
 */
export async function POST(request: NextRequest) {
  const auth = request.headers.get("authorization");
  if (auth) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { authorization: auth },
      cache: "no-store",
    }).catch(() => undefined);
  }

  const res = new NextResponse(null, { status: 204 });
  res.cookies.set(REFRESH_COOKIE, "", refreshCookieOptions(0));
  return res;
}
