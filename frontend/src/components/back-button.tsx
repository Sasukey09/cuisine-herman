"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * A visible "Retour" control for pages reached from elsewhere (imports, detail
 * views…). Web is never truly trapped (the sidebar is always there), but the
 * import flows must offer an explicit way back — mirrors the mobile shell's back
 * arrow. Uses real history when there is some, else a safe fallback route.
 */
export function BackButton({
  fallbackHref = "/dashboard",
  label = "Retour",
}: {
  fallbackHref?: string;
  label?: string;
}) {
  const router = useRouter();
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="mb-2 -ml-2 text-muted-foreground"
      onClick={() => {
        if (typeof window !== "undefined" && window.history.length > 1) {
          router.back();
        } else {
          router.push(fallbackHref);
        }
      }}
    >
      <ArrowLeft className="h-4 w-4" />
      <span className="ml-1">{label}</span>
    </Button>
  );
}
