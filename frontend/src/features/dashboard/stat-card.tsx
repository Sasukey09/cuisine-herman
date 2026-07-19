import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  hint?: string;
  loading?: boolean;
  accentClassName?: string;
}

export function StatCard({
  title,
  value,
  icon: Icon,
  hint,
  loading,
  accentClassName,
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <div
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary",
            accentClassName,
          )}
        >
          <Icon className="h-6 w-6" />
        </div>
        <div className="min-w-0 space-y-1">
          <p className="truncate text-sm text-muted-foreground">{title}</p>
          {loading ? (
            <Skeleton className="h-7 w-24" />
          ) : (
            <p className="font-serif text-2xl font-semibold">{value}</p>
          )}
          {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}
