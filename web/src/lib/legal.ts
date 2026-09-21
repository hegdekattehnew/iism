/**
 * The facts the legal pages and the consent checkbox depend on, in one place.
 *
 * `PRIVACY_NOTICE_VERSION` must equal `PRIVACY_NOTICE_VERSION` in
 * `api/core/config.py`. The API refuses consent to any other version, because
 * consent to a text nobody can identify later proves nothing -- so a mismatch
 * shows up as every signup failing, and `tests/test_privacy.py` compares the
 * two files so it fails in CI first. Change both, together, only when the
 * privacy notice or terms change in a way people must agree to again.
 */
export const PRIVACY_NOTICE_VERSION = "2026-09-11";

/**
 * DPDP Act 2023 expects a named grievance officer. Not yet appointed: every
 * `null` renders as "to be appointed" rather than a placeholder that looks
 * like a real contact. Fill these in here, and nowhere else.
 */
export const GRIEVANCE_OFFICER: {
  name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
} = {
  name: null,
  email: null,
  phone: null,
  address: null,
};
