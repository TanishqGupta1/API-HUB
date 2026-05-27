import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// "/signup" is intentionally NOT public — creating users requires an
// authenticated admin session.  The page posts to /api/auth/users which is
// a VGAdmin-only endpoint.
const PUBLIC_PATHS = ["/login", "/setup", "/storefront"];

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
