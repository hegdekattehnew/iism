import { ACCESS_TOKEN_KEY } from "@/lib/storage-keys";

/**
 * Tells the stylesheet, before the first paint, that a signed-in person may get a bottom tab bar
 * (Sprint 81, BL-19.13, ADR-090): `data-auth` on `<html>` when this browser holds a sign-in and the
 * page is not an organisation's workspace, the back office or a sign-in page.
 *
 * It exists so that **the tab bar's room is already there when the bar arrives**. The bar is a
 * lazily loaded component that needs the account (is this person a job seeker?), which is known
 * well after the first paint; if the page made room only then, a short page's footer would jump up
 * by the bar's height. `globals.css` reads the attribute for `--tabbar`, the room under the page.
 * A hint, not a fact: an expired sign-in or an organisation-only account gets the room and no bar
 * until `SeekerTabs` corrects it, and a sign-in is never shown or trusted from here.
 *
 * Plain ES5 and self-contained: it is inlined as text in `<head>`, so it cannot import anything.
 */
export const authHintScript = `(function(){try{if(localStorage.getItem(${JSON.stringify(ACCESS_TOKEN_KEY)})&&!/^\\/[a-z]{2}\\/(employer|admin|signin|signup|employers\\/signin)(\\/|$)/.test(location.pathname))document.documentElement.setAttribute("data-auth","1")}catch(e){}})();`;
