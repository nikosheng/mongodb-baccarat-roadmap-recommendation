import type { ReactNode } from "react";
import { NavBar } from "./NavBar";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-bg-deep text-text-primary">
      <NavBar />
      <main className="flex-1 p-6 max-w-[1440px] w-full mx-auto">{children}</main>
    </div>
  );
}
