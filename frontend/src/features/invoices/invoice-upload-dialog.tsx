"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UploadCloud, FileText } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useIngestInvoice } from "@/hooks/use-invoices";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InvoiceUploadDialog({ open, onOpenChange }: Props) {
  const router = useRouter();
  const ingest = useIngestInvoice();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);

  const reset = () => {
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const onSubmit = () => {
    if (!file) return;
    ingest.mutate(file, {
      onSuccess: (res) => {
        reset();
        onOpenChange(false);
        router.push(`/factures/${res.invoice_id}`);
      },
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Importer une facture</DialogTitle>
          <DialogDescription>
            PDF ou image. L&apos;OCR extrait les lignes, les associe aux produits et
            met à jour l&apos;historique des prix automatiquement.
          </DialogDescription>
        </DialogHeader>

        <label
          htmlFor="invoice-file"
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground transition-colors hover:bg-accent/50"
        >
          {file ? (
            <>
              <FileText className="h-8 w-8 text-primary" />
              <span className="font-medium text-foreground">{file.name}</span>
              <span>{(file.size / 1024).toFixed(0)} Ko</span>
            </>
          ) : (
            <>
              <UploadCloud className="h-8 w-8" />
              <span>Cliquez pour choisir un fichier</span>
              <span className="text-xs">PDF, PNG, JPG</span>
            </>
          )}
          <input
            id="invoice-file"
            ref={inputRef}
            type="file"
            accept=".pdf,image/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={onSubmit} disabled={!file || ingest.isPending}>
            {ingest.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Importer et analyser
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
