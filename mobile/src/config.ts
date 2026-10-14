import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Where the API and the website are. Set at build time through Expo's public environment
 * (`EXPO_PUBLIC_*`), never hard-coded for production.
 *
 * The defaults are the development machine: an Android emulator reaches the host at `10.0.2.2`
 * and an iOS simulator at `localhost`. **Plain HTTP is for development only**: a release build
 * must point at an HTTPS origin (Android blocks cleartext traffic in release builds, and Apple
 * requires App Transport Security).
 */
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000");

/** The website: the privacy notice and terms live there, and an organisation signs in there. */
export const WEB_BASE_URL = process.env.EXPO_PUBLIC_WEB_BASE_URL ?? "http://localhost:3000";

/** This build's version, from `app.json`; sent on every request (ADR-072). */
export const APP_VERSION: string = Constants.expoConfig?.version ?? "0.0.0";

export const PLATFORM: "android" | "ios" = Platform.OS === "ios" ? "ios" : "android";

/**
 * Where "update the app" sends somebody. **Placeholders**: the real listing ids exist only once the
 * store accounts do (the app id `in.iism.app` is itself a placeholder, ADR-072).
 */
export const STORE_URL =
  Platform.OS === "ios" ? "https://apps.apple.com/" : "market://details?id=in.iism.app";
