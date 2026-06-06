import { PageHeader } from "@/components/page-header";
import { RecipesView } from "@/features/recipes/recipes-view";

export default function RecipesPage() {
  return (
    <>
      <PageHeader
        title="Recettes"
        description="Fiches techniques, coûts matière et marges."
      />
      <RecipesView />
    </>
  );
}
