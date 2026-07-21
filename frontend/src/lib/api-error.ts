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

export type ErrorKind =
  | "offline"
  | "timeout"
  | "network"
  | "unauthorized"
  | "forbidden"
  | "notFound"
  | "conflict"
  | "validation"
  | "rateLimited"
  | "server"
  | "unavailable"
  | "unknown";

export interface ClassifiedError {
  kind: ErrorKind;
  /** HTTP status when there was a response. */
  status?: number;
  title: string;
  message: string;
  /** Whether offering a "Réessayer" button makes sense for this kind. */
  retryable: boolean;
}

/**
 * Turn any thrown error (Axios or otherwise) into a stable, user-facing shape so
 * every screen can say *what* went wrong and *what to do* — instead of showing
 * an empty list that reads as "your data is gone". Covers the full set:
 * offline / timeout / cold start / 401 / 403 / 404 / 409 / 422 / 429 / 500 / 503.
 */
export function classifyError(error: unknown): ClassifiedError {
  // Browser is offline: the most common "it looks broken" cause.
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return {
      kind: "offline",
      title: "Vous êtes hors ligne",
      message: "Vérifiez votre connexion internet. Vos données sont en sécurité — rien n'a été perdu.",
      retryable: true,
    };
  }

  if (error instanceof AxiosError) {
    const status = error.response?.status;
    if (error.code === "ECONNABORTED" || /timeout/i.test(error.message)) {
      return {
        kind: "timeout",
        title: "Le serveur met trop de temps à répondre",
        message:
          "La connexion a expiré (le serveur démarrait peut-être). Réessayez dans un instant — vos données sont intactes.",
        retryable: true,
      };
    }
    if (error.code === "ERR_NETWORK" || status === undefined) {
      return {
        kind: "network",
        title: "Impossible de joindre le serveur",
        message:
          "Le serveur est momentanément injoignable (il redémarre peut-être). Vos données sont en sécurité. Réessayez dans un instant.",
        retryable: true,
      };
    }
    const detail = getApiErrorMessage(error, "");
    switch (status) {
      case 401:
        return {
          kind: "unauthorized",
          status,
          title: "Session expirée",
          message: "Votre session a expiré. Reconnectez-vous pour continuer.",
          retryable: false,
        };
      case 403:
        return {
          kind: "forbidden",
          status,
          title: "Accès non autorisé",
          message: detail || "Vous n'avez pas les droits nécessaires pour cette action.",
          retryable: false,
        };
      case 404:
        return {
          kind: "notFound",
          status,
          title: "Introuvable",
          message: detail || "Cette ressource n'existe pas ou a été supprimée.",
          retryable: false,
        };
      case 409:
        return {
          kind: "conflict",
          status,
          title: "Conflit",
          message: detail || "Cette action entre en conflit avec l'état actuel des données.",
          retryable: false,
        };
      case 422:
        return {
          kind: "validation",
          status,
          title: "Données invalides",
          message: detail || "Certaines informations saisies ne sont pas valides.",
          retryable: false,
        };
      case 429:
        return {
          kind: "rateLimited",
          status,
          title: "Trop de requêtes",
          message: detail || "Vous avez effectué trop de requêtes. Patientez un instant avant de réessayer.",
          retryable: true,
        };
      case 503:
        return {
          kind: "unavailable",
          status,
          title: "Service momentanément indisponible",
          message:
            "Le service redémarre ou est en maintenance. Réessayez dans quelques secondes — aucune donnée n'est perdue.",
          retryable: true,
        };
      default:
        if (status >= 500) {
          return {
            kind: "server",
            status,
            title: "Erreur du serveur",
            message:
              "Une erreur est survenue côté serveur. Ce n'est pas votre faute et vos données sont intactes. Réessayez.",
            retryable: true,
          };
        }
        return {
          kind: "unknown",
          status,
          title: "Une erreur est survenue",
          message: detail || "Réessayez dans un instant.",
          retryable: true,
        };
    }
  }

  return {
    kind: "unknown",
    title: "Une erreur est survenue",
    message: getApiErrorMessage(error),
    retryable: true,
  };
}

/** A 401 is handled globally (silent refresh then redirect to /login), so it
 *  must not raise a toast or an error card mid-flow. */
export function isHandledAuthError(error: unknown): boolean {
  return error instanceof AxiosError && error.response?.status === 401;
}
