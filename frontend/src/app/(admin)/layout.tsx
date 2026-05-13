import CursorTrail from "@/components/CursorTrail";
import SidebarNav from "@/components/SidebarNav";
import AdminTopBar from "@/components/AdminTopBar";
import { CustomerProvider } from "@/lib/customer-context";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <CustomerProvider>
      <div className="shell">
        <SidebarNav />
        <div className="main">
          <AdminTopBar />
          {children}
        </div>
      </div>
      <CursorTrail />
    </CustomerProvider>
  );
}
