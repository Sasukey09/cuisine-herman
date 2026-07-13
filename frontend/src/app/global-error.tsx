"use client";

/**
 * Last line of defence: catches errors thrown in the root layout itself, where
 * `error.tsx` cannot run. It must render its own <html>/<body>, and it cannot
 * rely on the app's providers — so no fancy components here, only inline styles.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="fr">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#f4efe6",
          color: "#2a2620",
          fontFamily: "system-ui, sans-serif",
          textAlign: "center",
          padding: "24px",
        }}
      >
        <div>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: 26, margin: "0 0 8px" }}>
            L&apos;application n&apos;a pas pu démarrer
          </h1>
          <p style={{ color: "#8a847a", fontSize: 14, margin: "0 0 20px" }}>
            Un problème technique est survenu. Vos données ne sont pas perdues.
          </p>
          <button
            onClick={reset}
            style={{
              border: "none",
              background: "#c2632f",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              padding: "10px 18px",
              borderRadius: 10,
              cursor: "pointer",
            }}
          >
            Réessayer
          </button>
          {error.digest && (
            <p style={{ fontSize: 12, color: "#8a847a", marginTop: 16 }}>
              Référence : {error.digest}
            </p>
          )}
        </div>
      </body>
    </html>
  );
}
