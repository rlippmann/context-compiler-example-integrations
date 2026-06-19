import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Context Compiler Next.js basic starter",
  description: "Minimal compiler-only Next.js starter app for Context Compiler example integrations."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "Georgia, serif", background: "#f4efe6", color: "#1d1b18" }}>
        {children}
      </body>
    </html>
  );
}
