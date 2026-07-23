"use client";

import { AlertTriangle } from "lucide-react";

import { Input } from "@/components/ui/input";

/**
 * Ligne éditable d'un import de document (facture OU devis).
 *
 * Les deux imports posent exactement la même question à l'utilisateur pour
 * chaque ligne détectée : « ce libellé, c'est quel produit — un existant, un
 * nouveau, ou on ignore ? ». Cette logique vivait dans la vue facture ; elle est
 * ici pour être partagée au lieu d'être recopiée dans la vue devis.
 *
 * Les champs propres à un type de document (remise et conditionnement sur un
 * devis) passent par `extraFields`, rendu à la suite des champs communs.
 */
export const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export type ImportAction = "create" | "associate" | "skip";

export interface ImportRowBase {
  description: string;
  qty?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  vat_rate?: number | null;
  matched_product_name?: string | null;
  match_confidence?: number | null;
  needs_review: boolean;
  /** Choix de l'utilisateur. */
  action: ImportAction;
  category: string;
  product_id: string;
}

export interface ProductOption {
  id: string;
  name: string;
}

export function ImportLineRow<T extends ImportRowBase>({
  row,
  onChange,
  categories,
  products,
  extraFields,
}: {
  row: T;
  onChange: (patch: Partial<T>) => void;
  categories?: string[];
  products?: ProductOption[];
  extraFields?: React.ReactNode;
}) {
  const num = (v: string) => (v === "" ? null : Number(v));

  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="min-w-40 flex-1"
          value={row.description}
          onChange={(e) => onChange({ description: e.target.value } as Partial<T>)}
          aria-label="Description"
        />
        <Input
          className="w-16"
          type="number"
          value={row.qty ?? ""}
          onChange={(e) => onChange({ qty: num(e.target.value) } as Partial<T>)}
          placeholder="Qté"
          aria-label="Quantité"
        />
        <Input
          className="w-16"
          value={row.unit ?? ""}
          onChange={(e) => onChange({ unit: e.target.value } as Partial<T>)}
          placeholder="unité"
          aria-label="Unité"
        />
        <Input
          className="w-20"
          type="number"
          value={row.unit_price ?? ""}
          onChange={(e) => onChange({ unit_price: num(e.target.value) } as Partial<T>)}
          placeholder="PU"
          aria-label="Prix unitaire"
        />
        <Input
          className="w-16"
          type="number"
          value={row.vat_rate ?? ""}
          onChange={(e) => onChange({ vat_rate: num(e.target.value) } as Partial<T>)}
          placeholder="TVA%"
          aria-label="TVA %"
        />
        {extraFields}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <select
          className={`${SELECT_CLASS} w-32`}
          value={row.action}
          onChange={(e) => onChange({ action: e.target.value as ImportAction } as Partial<T>)}
          aria-label="Action"
        >
          <option value="create">➕ Créer</option>
          <option value="associate">🔗 Associer</option>
          <option value="skip">Ignorer</option>
        </select>

        {row.action === "create" && (
          <select
            className={`${SELECT_CLASS} w-44`}
            value={row.category}
            onChange={(e) => onChange({ category: e.target.value } as Partial<T>)}
            aria-label="Catégorie"
          >
            <option value="">Catégorie auto</option>
            {(categories ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}

        {row.action === "associate" && (
          <select
            className={`${SELECT_CLASS} w-64`}
            value={row.product_id}
            onChange={(e) => onChange({ product_id: e.target.value } as Partial<T>)}
            aria-label="Produit"
          >
            <option value="">Choisir un produit…</option>
            {(products ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}

        {row.matched_product_name && row.action === "associate" && (
          <span className="text-xs text-muted-foreground">
            Suggéré : {row.matched_product_name}
            {row.match_confidence != null ? ` (${Math.round(row.match_confidence)}%)` : ""}
          </span>
        )}

        {row.needs_review && row.action === "create" && (
          <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5" /> nouveau produit
          </span>
        )}
      </div>
    </div>
  );
}
