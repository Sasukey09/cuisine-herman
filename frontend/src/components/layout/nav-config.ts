import {
  LayoutDashboard,
  Package,
  Truck,
  FileText,
  ChefHat,
  Settings,
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
  { title: "Recettes", href: "/recettes", icon: ChefHat },
  { title: "Administration", href: "/administration", icon: Settings, roles: ["admin"] },
];
