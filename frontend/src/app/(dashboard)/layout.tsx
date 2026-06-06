"use client";

import { useState } from "react";

import { AuthGuard } from "@/components/layout/auth-guard";
import { SidebarNav } from "@/components/layout/sidebar";
import { Topnav } from "@/components/layout/topnav";
import { MobileDrawer } from "@/components/layout/mobile-drawer";
import { useMe } from "@/hooks/use-auth";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  // Refresh current user/roles once mounted (token already present via guard).
  useMe();

  return (
    <AuthGuard>
      <div className="min-h-screen bg-muted/20">
        {/* Desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-card md:block">
          <SidebarNav />
        </aside>

        {/* Mobile drawer */}
        <MobileDrawer open={mobileOpen} onClose={() => setMobileOpen(false)}>
          <SidebarNav onNavigate={() => setMobileOpen(false)} />
        </MobileDrawer>

        <div className="md:pl-64">
          <Topnav onMenu={() => setMobileOpen(true)} />
          <main className="mx-auto w-full max-w-7xl p-4 md:p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}
