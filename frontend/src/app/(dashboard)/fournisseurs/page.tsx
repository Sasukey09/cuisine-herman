import { PageHeader } from "@/components/page-header";
import { SuppliersView } from "@/features/suppliers/suppliers-view";

export default function SuppliersPage() {
  return (
    <>
      <PageHeader
        title="Fournisseurs"
        description="Gérez vos fournisseurs et consultez leur historique de prix."
      />
      <SuppliersView />
    </>
  );
}
