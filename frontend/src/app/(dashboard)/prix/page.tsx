import { PageHeader } from "@/components/page-header";
import { PriceDashboardView } from "@/features/dashboard/price-dashboard-view";

export default function PriceVariationsPage() {
  return (
    <>
      <PageHeader
        title="Variations de prix"
        description="Suivi des prix fournisseurs, économies possibles et impact sur vos marges."
      />
      <PriceDashboardView />
    </>
  );
}
