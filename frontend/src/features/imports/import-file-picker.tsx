"use client";

import { useRef } from "react";
import { Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Sélecteur de document à importer (PDF / photo / scan), partagé entre l'import
 * de facture et l'import de devis : même pipeline OCR derrière, donc même
 * affordance et mêmes formats acceptés.
 */
export function ImportFilePicker({
  label,
  pending,
  onFile,
  pendingLabel = "Analyse OCR en cours…",
}: {
  label: string;
  pending: boolean;
  onFile: (file: File) => void;
  pendingLabel?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={ref}
        type="file"
        accept=".pdf,image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // re-choisir le même fichier doit relancer l'analyse
          if (file) onFile(file);
        }}
      />
      <Button onClick={() => ref.current?.click()} disabled={pending}>
        {pending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
        <span className="ml-2">{label}</span>
      </Button>
      {pending && <p className="mt-3 text-sm text-muted-foreground">{pendingLabel}</p>}
    </>
  );
}
