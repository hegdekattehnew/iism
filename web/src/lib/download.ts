/**
 * Save text as a UTF-8 CSV that Excel opens with Devanagari intact (hence the byte-order mark).
 *
 * Lifted out of the bulk-upload screen in Sprint 60 so the applicant export uses the same code,
 * not a second copy that forgets the BOM. The server has already made every cell safe to open
 * (`core.text.csv_safe`); this only hands the file to the browser.
 */
export function saveCsv(name: string, text: string): void {
  const blob = new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
