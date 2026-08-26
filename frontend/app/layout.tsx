import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Placement Week Scheduler",
  description: "Minimal-disruption placement week scheduler"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

