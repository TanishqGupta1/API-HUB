// Task 9 replaces this with real composition:
// loads categories + products, computes counts, mounts LeftRail + MobileFilterSheet.
// function LeftRail() { return null; }         // replaced by Sinchana 8
// function MobileFilterSheet() { return null; } // replaced by Sinchana 10

import { SearchProvider } from "./search-context";
import { TopBar } from "./top-bar";

export default function StorefrontShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SearchProvider>
      <div className="min-h-screen bg-[#f2f0ed] text-[#1e1e24]">
        <TopBar />
        <main>{children}</main>
      </div>
    </SearchProvider>
  );
}
