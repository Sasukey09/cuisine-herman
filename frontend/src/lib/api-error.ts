import { AxiosError } from "axios";

/** Extracts a human-readable message from a FastAPI error response. */
export function getApiErrorMessage(error: unknown, fallback = "Une erreur est survenue"): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors: [{ msg, loc, ... }]
      return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ") || fallback;
    }
    if (error.code === "ERR_NETWORK") return "Impossible de joindre le serveur.";
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
