"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { navItems } from "./nav-config";

function initials(name?: string | null, email?: string | null) {
  const base = name?.trim() || email || "?";
  return base.slice(0, 2).toUpperCase();
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const hasRole = useAuthStore((s) => s.hasRole);
  const user = useAuthStore((s) => s.user);
  const roleLabel = user?.roles?.[0] ?? "Membre";

  return (
    <div className="flex h-full flex-col bg-sidebar p-3.5 text-sidebar-foreground">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-2 pb-5 pt-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-[9px] bg-primary font-serif text-[21px] font-semibold text-white">
          H
        </div>
        <div className="leading-tight">
          <div className="font-serif text-lg text-[#f4efe6]">Herman</div>
          <div className="text-[11px] tracking-wide text-sidebar-muted">Coûts cuisine</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-px overflow-y-auto">
        {navItems
          .filter((item) => !item.roles || hasRole(...item.roles))
          .map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] transition-colors",
                  active
                    ? "bg-sidebar-active font-semibold text-[#f4efe6]"
                    : "font-medium text-sidebar-foreground hover:bg-sidebar-active hover:text-[#f4efe6]",
                )}
              >
                <item.icon
                  className={cn(
                    "h-[18px] w-[18px] flex-none",
                    active && "text-sidebar-accent",
                  )}
                />
                {item.title}
              </Link>
            );
          })}
      </nav>

      {/* User */}
      <div className="mt-auto flex items-center gap-2.5 border-t border-white/10 px-2 pt-3.5">
        <div className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
          {initials(user?.name, user?.email)}
        </div>
        <div className="leading-tight">
          <div className="text-[12.5px] font-semibold text-[#f4efe6]">
            {user?.name ?? "Utilisateur"}
          </div>
          <div className="text-[11px] capitalize text-sidebar-muted">{roleLabel}</div>
        </div>
      </div>
    </div>
  );
}
