import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Public paths — no auth_token required.
// "/signup" is public because it POSTs to /api/auth/register which is a
// public bootstrap/open-signup endpoint (not /api/auth/users which is vg_admin-only).
// "/portal" sub-routes are protected by the server-side CustomerAdmin dep,
// but the Next.js middleware must not gate them here because the customer_admin
// JWT is a valid auth_token — they just can't reach /(admin) routes.
const PUBLIC_PATHS = ["/login", "/setup", "/signup", "/storefront"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));

  const token = request.cookies.get("auth_token")?.value;

  if (!token && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (token && (pathname === "/login" || pathname === "/signup")) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|icon|apple-icon|robots.txt|sitemap.xml|api/).*)",
  ],
};
