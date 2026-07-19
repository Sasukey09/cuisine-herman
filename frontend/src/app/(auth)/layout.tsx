export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="mb-6 flex items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-gradient-brand font-serif text-xl font-semibold text-white shadow-glow">
          F
        </div>
        <span className="font-serif text-2xl font-semibold">FoodGad</span>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
