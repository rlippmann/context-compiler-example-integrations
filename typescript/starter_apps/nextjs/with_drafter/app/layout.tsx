import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Context Compiler Next.js starter with drafter",
  description: "Minimal Next.js starter app with the optional directive-drafter layer."
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
