import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only auto-cleans when the runner exposes globals; these
// tests import `describe`/`it` explicitly, so unmount by hand.
afterEach(() => cleanup());
