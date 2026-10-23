import type { components } from "@/lib/api-schema";

/** The modes a batch can be taught in, typed over the server's own union. */
export const BATCH_MODES = ["in_person", "hybrid", "online"] as const satisfies readonly components["schemas"]["BatchOut"]["mode"][];
