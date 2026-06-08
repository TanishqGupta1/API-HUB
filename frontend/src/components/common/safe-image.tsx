import Image, { type ImageProps } from "next/image";

/**
 * Hosts the Next.js image optimizer is allowed to fetch server-side. This mirrors
 * `remotePatterns` in next.config.ts — keep the two in sync. Each entry is an
 * SSRF/exfil vector for the optimizer, so the list stays tight.
 *
 * SafeImage optimizes allowlisted hosts exactly as `next/image` does today, and
 * renders everything else with `unoptimized` (the browser fetches the URL directly,
 * so there is no server-side fetch and no "Invalid src prop … hostname not
 * configured" crash on hosts that aren't in remotePatterns — e.g. demo placeholder
 * images or a stray supplier URL).
 */
const ALLOWED_HOST_PATTERNS: RegExp[] = [
  /(^|\.)sanmar\.com$/,
  /^cdn\.ssactivewear\.com$/,
  /(^|\.)alphabroder\.com$/,
  /(^|\.)4over\.com$/,
  /^dei4q67dwezeh\.cloudfront\.net$/,
];

const cdnHost = process.env.NEXT_PUBLIC_CDN_HOST;
if (cdnHost) {
  ALLOWED_HOST_PATTERNS.push(
    new RegExp(`^${cdnHost.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`),
  );
}

function shouldUnoptimize(src: ImageProps["src"]): boolean {
  if (typeof src !== "string") return false; // static import — bundled, always safe
  if (!/^https?:\/\//i.test(src)) return false; // relative/same-origin — no host check, optimize
  try {
    const { hostname } = new URL(src);
    return !ALLOWED_HOST_PATTERNS.some((re) => re.test(hostname));
  } catch {
    return true; // unparseable absolute URL — don't hand it to the optimizer
  }
}

/**
 * Drop-in replacement for `next/image` that never crashes on a non-allowlisted
 * image host. Same props surface; pass `unoptimized` explicitly to override the
 * automatic decision.
 */
export function SafeImage({ unoptimized, alt, ...props }: ImageProps) {
  return (
    <Image
      {...props}
      alt={alt}
      unoptimized={unoptimized ?? shouldUnoptimize(props.src)}
    />
  );
}

export default SafeImage;
