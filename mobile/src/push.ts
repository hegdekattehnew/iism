import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { useCallback, useEffect, useState } from "react";
import { Platform } from "react-native";

import type { Api } from "./core/api";
import { registerDevice, unregisterDevice } from "./core/me";
import { deviceBody, pathFromPush, shouldRegister, type Permission } from "./core/push";
import { PUSH_DECLINED_KEY, storage } from "./storage";

/**
 * Push notifications on this phone (BL-15.6, ADR-075). **The one file that touches
 * `expo-notifications`** (a Python guard fails if another does), and the decisions it carries out
 * (when to ask, where a tap goes) are in `core/push.ts`, tested in Node.
 *
 * It is **best-effort by design**: a failure to ask, to get a token or to register is never shown
 * and never stops the app, because the in-app notice is always there. Two things stop it quietly
 * rather than failing: the web (no native module), and a build with **no EAS project id**, which
 * Expo needs to issue a token. That id belongs to the owner's Expo account (the same one release
 * builds need), so until it exists registration is a no-op and the README says so.
 *
 * Not exercised here beyond compiling and bundling: there is no device and no EAS project.
 */

const supported = Platform.OS !== "web";

function projectId(): string | null {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? null;
}

const toPermission = (status: string): Permission =>
  status === "granted" ? "granted" : status === "denied" ? "denied" : "undetermined";

async function readPermission(): Promise<Permission> {
  if (!supported) return "denied";
  try {
    return toPermission((await Notifications.getPermissionsAsync()).status);
  } catch {
    return "denied";
  }
}

async function askPermission(): Promise<Permission> {
  if (!supported) return "denied";
  try {
    if (Platform.OS === "android") {
      // Android 13 asks only once a channel exists.
      await Notifications.setNotificationChannelAsync("default", {
        name: "Updates",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    return toPermission((await Notifications.requestPermissionsAsync()).status);
  } catch {
    return "denied";
  }
}

/** While the app is open a notification is shown as a banner and does not play a sound. */
export function showForegroundNotifications(): void {
  if (!supported) return;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  });
}

// Held in memory only: a push token is a credential for sending to this phone, and `storage` holds
// nothing secret. It is set each launch by `usePushRegistration`, so the next sign-out has it.
let currentToken: string | null = null;

/** Tell the server about this phone. A no-op without permission, a project id or a native module. */
export async function registerThisDevice(api: Api, locale: string): Promise<void> {
  const project = projectId();
  if (!supported || project === null) return;
  try {
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: project });
    await registerDevice(api, deviceBody(token, Platform.OS === "ios" ? "ios" : "android", locale));
    currentToken = token;
  } catch {
    // Offline, or the service refused: the person still has every notice in the app.
  }
}

/**
 * Stop pushes to this phone for the person who is signing out. **Called while still signed in**
 * (the server only lets a person remove their own phone), and never allowed to hold sign-out up.
 */
export async function unregisterThisDevice(api: Api): Promise<void> {
  try {
    if (currentToken) await unregisterDevice(api, currentToken);
  } catch {
    // The token stays on the server until the next person to sign in registers this phone, which
    // moves it (a token belongs to one person at a time); the pushes it could carry say nothing.
  } finally {
    currentToken = null;
  }
}

/** A tapped notification, while the app is open or from cold, goes to the in-app place it names. */
export function listenForTaps(go: (path: string) => void): () => void {
  if (!supported) return () => undefined;
  const open = (data: unknown) => {
    const path = pathFromPush(data);
    if (path) go(path);
  };
  const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
    open(response.notification.request.content.data);
  });
  void Notifications.getLastNotificationResponseAsync()
    .then((response) => {
      if (response) {
        open(response.notification.request.content.data);
        Notifications.clearLastNotificationResponse();
      }
    })
    .catch(() => undefined);
  return () => subscription.remove();
}

/** What the notices screen needs to ask in context: the state, and the two answers. */
export function usePushPermission() {
  const [permission, setPermission] = useState<Permission>("denied");
  const [declined, setDeclined] = useState(true);
  useEffect(() => {
    let live = true;
    void (async () => {
      const [p, d] = await Promise.all([
        readPermission(),
        storage.getItem(PUSH_DECLINED_KEY).catch(() => null),
      ]);
      if (!live) return;
      setPermission(p);
      setDeclined(d === "1");
    })();
    return () => {
      live = false;
    };
  }, []);
  const ask = useCallback(async () => setPermission(await askPermission()), []);
  const decline = useCallback(() => {
    setDeclined(true);
    void storage.setItem(PUSH_DECLINED_KEY, "1").catch(() => undefined);
  }, []);
  return { permission, declined, ask, decline };
}

/** Register this phone once the person is a signed-in job seeker who has allowed notifications. */
export function usePushRegistration(
  api: Api,
  locale: string,
  state: { signedIn: boolean; isJobSeeker: boolean | undefined },
): void {
  const { signedIn, isJobSeeker } = state;
  useEffect(() => {
    if (!signedIn || isJobSeeker !== true) return;
    let live = true;
    void readPermission().then((permission) => {
      if (live && shouldRegister({ signedIn, isJobSeeker, permission })) {
        void registerThisDevice(api, locale);
      }
    });
    return () => {
      live = false;
    };
  }, [api, locale, signedIn, isJobSeeker]);
}
