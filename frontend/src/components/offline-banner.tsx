"use client";

import * as React from "react";
import { WifiOff } from "lucide-react";

/**
 * A slim, fixed banner shown whenever the browser goes offline. It reassures the
 * user their data is safe and that the app is simply waiting for the network —
 * so a dropped connection is never mistaken for lost data. Reconnection hides it
 * automatically (the `online` event).
 */
export function OfflineBanner() {
  const [offline, setOffline] = React.useState(false);

  React.useEffect(() => {
    const sync = () => setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-[100] flex items-center justify-center gap-2 bg-destructive px-4 py-2 text-center text-sm font-medium text-destructive-foreground shadow"
    >
      <WifiOff className="h-4 w-4 shrink-0" />
      <span>Hors ligne — vos données sont en sécurité. Reconnexion automatique dès le retour du réseau.</span>
    </div>
  );
}
