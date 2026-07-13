import Link from "next/link";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary">
        <Compass className="h-6 w-6 text-primary" />
      </div>
      <div className="space-y-1">
        <h1 className="font-serif text-2xl font-semibold">Cette page n&apos;existe pas</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          Le lien est peut-être erroné, ou la fiche a été supprimée.
        </p>
      </div>
      <Button asChild>
        <Link href="/dashboard">Retour au tableau de bord</Link>
      </Button>
    </div>
  );
}
