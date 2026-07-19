"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";

import { getQueryClient } from "@/lib/query-client";
import { Toaster } from "@/components/ui/sonner";
import { useSessionBootstrap } from "@/hooks/use-auth";

/** Runs the boot-time session restore (from the httpOnly refresh cookie) once,
 *  app-wide, before the guards decide. Renders nothing. */
function SessionBootstrapper() {
  useSessionBootstrap();
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <SessionBootstrapper />
        {children}
        <Toaster richColors position="top-right" />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
