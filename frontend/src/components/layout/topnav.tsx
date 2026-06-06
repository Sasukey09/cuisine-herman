"use client";

import { Menu, LogOut, User as UserIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ModeToggle } from "./mode-toggle";
import { useAuthStore } from "@/stores/auth-store";
import { useLogout } from "@/hooks/use-auth";

function initials(name?: string | null, email?: string) {
  const base = name?.trim() || email || "?";
  return base.slice(0, 2).toUpperCase();
}

export function Topnav({ onMenu }: { onMenu: () => void }) {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Ouvrir le menu"
        onClick={onMenu}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex-1" />

      <ModeToggle />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="rounded-full">
            <Avatar>
              <AvatarFallback>{initials(user?.name, user?.email)}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="flex flex-col">
              <span className="text-sm font-medium">{user?.name ?? "Utilisateur"}</span>
              <span className="text-xs text-muted-foreground">{user?.email}</span>
              {user?.roles?.length ? (
                <span className="mt-1 text-xs text-muted-foreground">
                  {user.roles.join(", ")}
                </span>
              ) : null}
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link href="/profile">
              <UserIcon className="h-4 w-4" />
              Profil
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
            <LogOut className="h-4 w-4" />
            Déconnexion
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
