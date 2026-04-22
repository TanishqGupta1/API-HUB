import CursorTrail from "@/components/CursorTrail";
import SidebarNav from "@/components/SidebarNav";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <div className="shell">
        <SidebarNav />
        <div className="main">{children}</div>
      </div>
      <CursorTrail />
    </>
  );
}
