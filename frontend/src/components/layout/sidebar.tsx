"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChefHat } from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { navItems } from "./nav-config";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const hasRole = useAuthStore((s) => s.hasRole);

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ChefHat className="h-5 w-5" />
        </div>
        <span className="text-lg font-semibold">Cuisine Herman</span>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-4">
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
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            );
          })}
      </nav>

      <div className="border-t p-4 text-xs text-muted-foreground">
        © {new Date().getFullYear()} Cuisine Herman
      </div>
    </div>
  );
}
