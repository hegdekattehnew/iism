import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * The phone's plain key-value store, in one file. It holds the language the person chose and the
 * public query cache (`core/persist.ts`): **nothing secret**. Tokens live in the Keychain / Keystore
 * (`auth/secure-backend.ts`), never here; a test holds each native module to its one file.
 */
export const storage = AsyncStorage;

export const LOCALE_KEY = "iism.locale";
