import {
  LayoutDashboard,
  Package,
  Truck,
  FileText,
  ChefHat,
  Bot,
  Video,
  Calculator,
  SlidersHorizontal,
  FileSpreadsheet,
  Settings,
  TrendingUp,
  ClipboardList,
  ShoppingCart,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** If set, only users holding one of these roles see the item. */
  roles?: string[];
}

export const navItems: NavItem[] = [
  { title: "Tableau de bord", href: "/dashboard", icon: LayoutDashboard },
  { title: "Produits", href: "/produits", icon: Package },
  { title: "Fournisseurs", href: "/fournisseurs", icon: Truck },
  { title: "Factures", href: "/factures", icon: FileText },
  { title: "Devis", href: "/devis", icon: ClipboardList },
  // Juste apres Devis : la barre suit l'ordre du cycle d'achat.
  { title: "Commandes", href: "/commandes", icon: ShoppingCart },
  { title: "Variations prix", href: "/prix", icon: TrendingUp },
  { title: "Recettes", href: "/recettes", icon: ChefHat },
  { title: "Import vidéo", href: "/import-video", icon: Video },
  { title: "Assistant IA", href: "/assistant", icon: Bot },
  { title: "Indicateurs", href: "/indicateurs", icon: Calculator },
  { title: "Champs perso", href: "/champs", icon: SlidersHorizontal },
  { title: "Rapports", href: "/rapports", icon: FileSpreadsheet },
  { title: "Administration", href: "/administration", icon: Settings, roles: ["admin"] },
];
