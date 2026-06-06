import { PageHeader } from "@/components/page-header";
import { ProductsView } from "@/features/products/products-view";

export default function ProductsPage() {
  return (
    <>
      <PageHeader
        title="Produits"
        description="Gérez le catalogue de produits de votre organisation."
      />
      <ProductsView />
    </>
  );
}
