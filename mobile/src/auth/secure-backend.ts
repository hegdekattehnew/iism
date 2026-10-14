import * as SecureStore from "expo-secure-store";

import type { SecretBackend } from "../core/token-store";

/**
 * The phone's Keychain (iOS) and Keystore (Android), behind the three operations `TokenStore`
 * needs. The only file that touches the native module, so everything else is testable in Node.
 *
 * `WHEN_UNLOCKED_THIS_DEVICE_ONLY`: the session is not restored onto a new phone from a backup.
 */
const options: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export const secureBackend: SecretBackend = {
  read: (key) => SecureStore.getItemAsync(key, options),
  write: (key, value) => SecureStore.setItemAsync(key, value, options),
  remove: (key) => SecureStore.deleteItemAsync(key, options),
};
