import { ChefHat } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/40 px-4">
      <div className="mb-6 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ChefHat className="h-5 w-5" />
        </div>
        <span className="text-xl font-semibold">FoodGad</span>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
