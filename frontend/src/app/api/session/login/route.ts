import { NextResponse } from "next/server";

import { API_BASE, REFRESH_COOKIE, refreshCookieOptions } from "../cookie";

/**
 * Exchanges credentials for tokens server-side, then keeps the long-lived
 * refresh token in an **httpOnly, first-party** cookie (unreachable by any
 * page script, so an XSS cannot exfiltrate it). Only the short-lived access
 * token is returned to the browser, where it lives in memory — never in
 * localStorage. This runs on the Vercel origin, so the cookie is first-party
 * even though the API is on a different domain.
 */
export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Requête invalide" }, { status: 400 });
  }
  const { email, password } = body;
  if (!email || !password) {
    return NextResponse.json({ detail: "Identifiants manquants" }, { status: 400 });
  }

  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);

  const upstream = await fetch(`${API_BASE}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
    cache: "no-store",
  });

  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok || !data?.access_token || !data?.refresh_token) {
    return NextResponse.json(
      { detail: data?.detail ?? "Identifiants incorrects" },
      { status: upstream.ok ? 502 : upstream.status },
    );
  }

  const res = NextResponse.json({ access_token: data.access_token });
  res.cookies.set(REFRESH_COOKIE, data.refresh_token, refreshCookieOptions());
  return res;
}
