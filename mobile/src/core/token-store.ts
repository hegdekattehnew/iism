/**
 * Where the session lives on the phone, and a small in-memory copy of it.
 *
 * The web keeps tokens in `localStorage` because it has nothing better. A phone has the Keychain and
 * the Keystore (through `expo-secure-store`), and the tokens belong there: an access token is a
 * fifteen-minute key and a refresh token is a thirty-day one.
 *
 * **The backend is injected** (`SecretBackend`) so the logic below runs in Node tests and the
 * native module stays one thin file (`src/auth/secure-backend.ts`). The in-memory copy exists
 * because the API client asks for the token on every request and a Keychain read is an IPC call.
 *
 * No React Native import: this file is tested in Node.
 */

export type Tokens = { access_token: string; refresh_token: string };

/** The three operations a secure store offers. Async, and allowed to throw. */
export interface SecretBackend {
  read(key: string): Promise<string | null>;
  write(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export const ACCESS_KEY = "iism.access_token";
export const REFRESH_KEY = "iism.refresh_token";

export interface TokenStore {
  /** Read the stored session into memory. Call once at start-up, before the first request. */
  load(): Promise<Tokens | null>;
  access(): string | null;
  refresh(): string | null;
  set(tokens: Tokens): Promise<void>;
  clear(): Promise<void>;
  /** Told whenever the session appears or ends. Returns the unsubscribe function. */
  subscribe(listener: (signedIn: boolean) => void): () => void;
}

export function createTokenStore(backend: SecretBackend): TokenStore {
  let current: Tokens | null = null;
  const listeners = new Set<(signedIn: boolean) => void>();
  const notify = () => listeners.forEach((listener) => listener(current !== null));

  return {
    async load() {
      try {
        const [access, refresh] = await Promise.all([
          backend.read(ACCESS_KEY),
          backend.read(REFRESH_KEY),
        ]);
        current = access && refresh ? { access_token: access, refresh_token: refresh } : null;
      } catch {
        // A locked or unavailable keystore means "signed out", never a crash on launch.
        current = null;
      }
      notify();
      return current;
    },
    access: () => current?.access_token ?? null,
    refresh: () => current?.refresh_token ?? null,
    async set(tokens) {
      // Memory first: the very next request must carry the new token even if the write is slow.
      current = tokens;
      notify();
      try {
        await Promise.all([
          backend.write(ACCESS_KEY, tokens.access_token),
          backend.write(REFRESH_KEY, tokens.refresh_token),
        ]);
      } catch {
        // The session still works until the app closes; the next launch asks to sign in again.
      }
    },
    async clear() {
      current = null;
      notify();
      try {
        await Promise.all([backend.remove(ACCESS_KEY), backend.remove(REFRESH_KEY)]);
      } catch {
        // Gone from memory is gone for this run; a failed delete must not block signing out.
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
