import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scoping Review AI | Automated Systematic Review Platform",
  description:
    "AI-powered platform for automating scoping reviews and systematic literature analysis with zero hallucination tolerance. Search, screen, extract, and validate research data using LLMs.",
  keywords: ["scoping review", "systematic review", "AI", "PICO extraction", "PubMed", "LLM"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
