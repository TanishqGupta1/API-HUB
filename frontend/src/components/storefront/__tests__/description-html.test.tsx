import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { DescriptionHtml } from "@/components/storefront/description-html";

// The component imports dompurify dynamically inside a useEffect, so each
// test needs an explicit waitFor on a stable selector before reading the DOM.
async function findAnchor(container: HTMLElement): Promise<HTMLAnchorElement> {
  return await waitFor(
    () => {
      const a = container.querySelector("a");
      if (!a) throw new Error("anchor not yet rendered");
      return a as HTMLAnchorElement;
    },
    { timeout: 3000 },
  );
}

describe("DescriptionHtml — Issue #29 tabnapping protection", () => {
  it('forces rel="noopener noreferrer" on <a target="_blank">', async () => {
    const malicious =
      '<p>See <a href="https://attacker.example" target="_blank">this link</a>.</p>';
    const { container } = render(<DescriptionHtml html={malicious} />);

    const anchor = await findAnchor(container);
    expect(anchor.getAttribute("target")).toBe("_blank");
    // The new hook MUST add this rel even when supplier HTML omits it.
    expect(anchor.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("leaves anchors without target unchanged", async () => {
    const safe = '<p>See <a href="https://example.com">our docs</a>.</p>';
    const { container } = render(<DescriptionHtml html={safe} />);

    const anchor = await findAnchor(container);
    expect(anchor.getAttribute("target")).toBeNull();
    // No tabnapping risk without target=_blank, so the hook leaves rel alone.
    expect(anchor.getAttribute("rel")).toBeNull();
  });

  it("overrides supplier-provided rel that omits noopener", async () => {
    const tricky =
      '<p><a href="https://x.example" target="_blank" rel="nofollow">x</a></p>';
    const { container } = render(<DescriptionHtml html={tricky} />);

    const anchor = await findAnchor(container);
    // We replace whatever rel the supplier sent with the safe value rather
    // than appending — pre-existing rel="nofollow" is dropped so the fix
    // is deterministic.
    expect(anchor.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("renders plain-text features when no block tags present", async () => {
    render(<DescriptionHtml html="First feature. Second feature." />);
    await waitFor(() => {
      expect(screen.getByText("First feature")).toBeTruthy();
      expect(screen.getByText("Second feature")).toBeTruthy();
    });
  });
});
