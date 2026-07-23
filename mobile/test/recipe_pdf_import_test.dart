import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/common/format.dart';
import 'package:foodgad_mobile/features/recipes/recipe_pdf_import_screen.dart';

/// Ce que l'écran d'import de recette envoie réellement au serveur.
///
/// C'est la seule logique non triviale de l'écran, et deux erreurs y coûtent
/// cher côté backend :
/// - une unité vide envoyée comme `""` fait chercher une unité nommée `""`,
///   qui n'existe pas, et la ligne sort du calcul de coût sans le dire ;
/// - un `product_id` vide (`""`) est refusé par le contrôle d'appartenance à
///   l'organisation, qui répond 400 sur toute la fiche.
void main() {
  group('lecture de l\'aperçu OCR', () {
    test('une ligne reconnue garde sa correspondance produit', () {
      final ing = RecipeIngredientDraft.fromPreview({
        'name': 'Farine T55',
        'quantity': 250,
        'unit': 'g',
        'matched_product_id': 'p1',
        'matched_product_name': 'Farine de blé T55',
        'match_confidence': 92,
      });
      expect(ing.name, 'Farine T55');
      expect(ing.qty, 250);
      expect(ing.unit, 'g');
      expect(ing.productId, 'p1');
      expect(ing.matchedName, 'Farine de blé T55');
    });

    test('une ligne sans correspondance reste sans produit, pas en chaîne vide', () {
      final ing = RecipeIngredientDraft.fromPreview({
        'name': 'Fleur de sel de Guérande',
        'quantity': null,
        'unit': null,
        'matched_product_id': null,
      });
      expect(ing.productId, isNull);
      expect(ing.qty, isNull);
      expect(ing.unit, isNull);
    });

    test('un aperçu incomplet ne fait pas planter la lecture', () {
      final ing = RecipeIngredientDraft.fromPreview(const {});
      expect(ing.name, '');
      expect(ing.qty, isNull);
      expect(ing.productId, isNull);
    });
  });

  group('envoi au serveur', () {
    test('une unité vide part à null, jamais en chaîne vide', () {
      expect(RecipeIngredientDraft(name: 'Sel', unit: '').toJson()['unit'], isNull);
      expect(RecipeIngredientDraft(name: 'Sel', unit: '   ').toJson()['unit'], isNull);
      expect(RecipeIngredientDraft(name: 'Sel', unit: null).toJson()['unit'], isNull);
    });

    test('un produit non associé part à null, jamais en chaîne vide', () {
      // Le backend refuserait la fiche entière : assert_products_in_tenant
      // n'a rien à valider pour "" et répond 400.
      expect(RecipeIngredientDraft(name: 'Sel', productId: '').toJson()['product_id'], isNull);
      expect(RecipeIngredientDraft(name: 'Sel', productId: null).toJson()['product_id'], isNull);
    });

    test('les valeurs renseignées passent nettoyées', () {
      final json = RecipeIngredientDraft(
        name: '  Beurre doux  ',
        qty: 125,
        unit: '  g ',
        productId: 'p9',
      ).toJson();
      expect(json['name'], 'Beurre doux');
      expect(json['quantity'], 125);
      expect(json['unit'], 'g');
      expect(json['product_id'], 'p9');
    });

    test('une quantité absente reste absente plutôt que de valoir zéro', () {
      // 0 g d'un ingrédient et « quantité inconnue » ne veulent pas dire la
      // même chose : le coût du second est incalculable, pas nul.
      expect(RecipeIngredientDraft(name: 'Poivre').toJson()['quantity'], isNull);
    });

    test('aller-retour aperçu → envoi sans perte', () {
      final json = RecipeIngredientDraft.fromPreview({
        'name': 'Lait entier',
        'quantity': 0.5,
        'unit': 'L',
        'matched_product_id': 'p3',
      }).toJson();
      expect(json, {
        'name': 'Lait entier',
        'quantity': 0.5,
        'unit': 'L',
        'product_id': 'p3',
      });
    });
  });

  group('affichage des quantités dans les champs', () {
    // L'API rend les quantités en flottants : une quantité ronde arrivait à
    // « 300.0 » dans le champ, là où la fiche recette affiche « 300 ».
    // Le correctif est dans le helper partagé, donc l'import facture et l'import
    // devis en bénéficient aussi.
    test('une quantité ronde perd son .0', () {
      expect(plainNumber(300.0), '300');
      expect(plainNumber(8.0), '8');
      expect(plainNumber(0.0), '0');
    });

    test('une vraie décimale est conservée', () {
      expect(plainNumber(18.5), '18.5');
      expect(plainNumber(0.25), '0.25');
    });

    test('un entier reste un entier', () {
      expect(plainNumber(12), '12');
    });

    test('rien à afficher plutôt qu un zéro inventé', () {
      expect(plainNumber(null), '');
      expect(plainNumber(double.nan), '');
      expect(plainNumber(double.infinity), '');
    });
  });
}
