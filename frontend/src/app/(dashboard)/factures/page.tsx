import { PageHeader } from "@/components/page-header";
import { InvoicesView } from "@/features/invoices/invoices-view";

export default function InvoicesPage() {
  return (
    <>
      <PageHeader
        title="Factures"
        description="Importez vos factures et validez l'extraction OCR."
      />
      <InvoicesView />
    </>
  );
}
