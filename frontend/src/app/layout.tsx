import type { Metadata } from "next";
import "./globals.css";
import CursorTrail from "@/components/CursorTrail";
import SidebarNav from "@/components/SidebarNav";

export const metadata: Metadata = {
  title: "API-HUB",
  description: "Universal Connector",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <SidebarNav />
          <div className="main">
            <div className="main-ruler"></div>
            {children}
          </div>
        </div>
        <CursorTrail />
      </body>
    </html>
  );
}
