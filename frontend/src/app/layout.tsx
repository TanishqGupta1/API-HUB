import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "API-HUB",
  description: "Universal Connector",
};

import { Toaster } from "sonner";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
