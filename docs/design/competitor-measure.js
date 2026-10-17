/**
 * The function used for the Sprint 76 competitor review (docs/design/competitor-review.md).
 *
 * Paste it into the browser console of a page opened at 375 x 812 (mobile emulation), or run it
 * through the built-in browser's script tool, and read the JSON it returns. It measures only what
 * the page shows at that moment: the scroll height in screens, how many interactive elements there
 * are, how many are under 44 px in height or width ("small"), how many visible text nodes are under
 * 12 px, how many images and inline SVGs, the font sizes in use and the fixed or sticky elements.
 *
 * "Small" counts any link, button, input, select or textarea under 44 px in either dimension, so it
 * is stricter than the capture script's count in web/scripts/capture-review.mjs (which is why our own
 * page was re-measured with this function for the comparison table).
 */
(() => {
  const vh = innerHeight;
  const vw = innerWidth;
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none";
  };
  const interactive = [
    ...document.querySelectorAll("a[href],button,input,select,textarea,[role=button]"),
  ].filter(visible);
  const small = interactive.filter((e) => {
    const r = e.getBoundingClientRect();
    return r.height < 44 || r.width < 44;
  });
  let tiny = 0;
  const sizes = {};
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.textContent.trim()) continue;
    const parent = node.parentElement;
    if (!parent || !visible(parent)) continue;
    const size = parseFloat(getComputedStyle(parent).fontSize);
    if (size < 12) tiny++;
    const key = Math.round(size);
    sizes[key] = (sizes[key] || 0) + 1;
  }
  const fixed = [...document.querySelectorAll("*")]
    .filter((e) => {
      const p = getComputedStyle(e).position;
      return (p === "fixed" || p === "sticky") && visible(e);
    })
    .map((e) => (e.innerText || "").trim().replace(/\s+/g, " ").slice(0, 30));
  return JSON.stringify({
    url: location.href,
    screens: +(document.documentElement.scrollHeight / vh).toFixed(1),
    interactive: interactive.length,
    small: small.length,
    tinyText: tiny,
    fontSizes: sizes,
    images: document.images.length,
    svgs: document.querySelectorAll("svg").length,
    fixed: fixed.slice(0, 5),
    overflowX: document.documentElement.scrollWidth > vw,
  });
})();
