"use client";

import * as React from "react";
import {
  AlertTriangle,
  RefreshCw,
  WifiOff,
  Clock,
  ServerCrash,
  ShieldAlert,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { classifyError, type ErrorKind } from "@/lib/api-error";

const ICONS: Record<ErrorKind, React.ComponentType<{ className?: string }>> = {
  offline: WifiOff,
  timeout: Clock,
  network: ServerCrash,
  unavailable: ServerCrash,
  server: ServerCrash,
  unauthorized: ShieldAlert,
  forbidden: ShieldAlert,
  notFound: AlertTriangle,
  conflict: AlertTriangle,
  validation: AlertTriangle,
  rateLimited: Clock,
  unknown: AlertTriangle,
};

/** A tiny standalone "Réessayer" button, exported for reuse. */
export function RetryWidget({
  onRetry,
  pending,
  label = "Réessayer",
}: {
  onRetry: () => void;
  pending?: boolean;
  label?: string;
}) {
  return (
    <Button variant="outline" size="sm" onClick={onRetry} disabled={pending}>
      {pending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {label}
    </Button>
  );
}

interface ErrorStateProps {
  /** The thrown error; it is classified into an explanation + an action. */
  error?: unknown;
  /** Called when the user presses "Réessayer". Omit to hide the button. */
  onRetry?: () => void;
  /** True while a retry is in flight (spinner on the button). */
  retrying?: boolean;
  /** Override the derived title/message when a screen wants its own wording. */
  title?: string;
  message?: string;
  /** Compact inline variant (no big padding), for smaller regions. */
  compact?: boolean;
  className?: string;
}

/**
 * The single component every screen renders instead of an empty state when a
 * query FAILS. It always says what happened and what to do, and offers a real
 * "Réessayer" — so a network blip never reads as "your data disappeared".
 */
export function ErrorState({
  error,
  onRetry,
  retrying,
  title,
  message,
  compact,
  className,
}: ErrorStateProps) {
  const info = classifyError(error);
  const Icon = ICONS[info.kind] ?? AlertTriangle;
  const showRetry = Boolean(onRetry) && info.retryable;

  return (
    <div
      role="alert"
      className={[
        "flex flex-col items-center justify-center gap-3 text-center",
        compact ? "py-8 px-4" : "py-14 px-6",
        className ?? "",
      ].join(" ")}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
        <Icon className="h-6 w-6 text-destructive" />
      </div>
      <div className="space-y-1">
        <p className="font-serif text-lg font-semibold">{title ?? info.title}</p>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">
          {message ?? info.message}
        </p>
      </div>
      {showRetry && onRetry && <RetryWidget onRetry={onRetry} pending={retrying} />}
    </div>
  );
}

/** Named variants the design brief asked for — thin wrappers over ErrorState. */
export function NetworkErrorCard({ onRetry, retrying }: { onRetry?: () => void; retrying?: boolean }) {
  return (
    <ErrorState
      onRetry={onRetry}
      retrying={retrying}
      title="Impossible de joindre le serveur"
      message="Le serveur est momentanément injoignable. Vos données sont en sécurité. Réessayez dans un instant."
    />
  );
}

export function TimeoutCard({ onRetry, retrying }: { onRetry?: () => void; retrying?: boolean }) {
  return (
    <ErrorState
      onRetry={onRetry}
      retrying={retrying}
      title="Le serveur met trop de temps à répondre"
      message="La connexion a expiré (le serveur démarrait peut-être). Réessayez — vos données sont intactes."
    />
  );
}
