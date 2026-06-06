import { Badge } from "@/components/ui/badge";
import type { Invoice } from "@/services/types";

export function InvoiceStatusBadge({ invoice }: { invoice: Invoice }) {
  if (invoice.parsed) {
    return <Badge variant="success">Traité</Badge>;
  }
  if (invoice.ocr_status) {
    return <Badge variant="secondary">{invoice.ocr_status}</Badge>;
  }
  return <Badge variant="warning">Non traité</Badge>;
}
