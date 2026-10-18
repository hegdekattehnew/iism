import { useState } from "react";
import { Pressable, Text as NativeText, View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError, isSignedOut } from "../core/errors";
import type { RoleHit } from "../core/me";
import { bulkBody, groupStandards, toggle } from "../core/role-picker";
import { useAddSkills, useRoleHits, useRoleStandards } from "../lib/me-queries";
import { MIN_TOUCH, space, useColours } from "../theme";
import { Badge, BadgeRow, Card, Chip, ChipRow, FailureNotice, SearchBox, SkeletonRows } from "./list";
import { Button, Notice, Text } from "./primitives";
import { SessionExpired } from "./session";

/**
 * "What work do you do?", and the national standards behind the answer.
 *
 * A candidate cannot name a National Occupational Standard; they are called things like "Follow
 * infection control policies & procedures including biomedical waste disposal protocols". They can
 * name their job. Every qualification pack carries a job role, and the pack names its standards, so
 * the candidate names the role and ticks what they can already do.
 *
 * **Nothing starts ticked**: pre-ticking the whole qualification would let the easy path claim
 * standards nobody affirmed (the server writes every one as `self_declared`, never `inferred`).
 * **Electives stay in their groups**, and a standard already held is shown ticked and cannot be
 * ticked again. The rules live in `core/role-picker.ts`; this is the screen.
 */
export function RolePicker({ held }: { held: ReadonlySet<string> }) {
  const t = useTranslations("profilePage.roles");
  const tp = useTranslations("profilePage");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleHit | null>(null);
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set());
  const [proficiency, setProficiency] = useState(3);
  const [asPreferred, setAsPreferred] = useState(true);
  const [added, setAdded] = useState<number | null>(null);
  const hits = useRoleHits(role ? "" : query);
  const standards = useRoleStandards(role?.slug ?? null);
  const add = useAddSkills();

  const choose = (hit: RoleHit) => {
    setRole(hit);
    setTicked(new Set());
    setAdded(null);
    add.reset();
  };
  const reset = () => {
    setRole(null);
    setTicked(new Set());
    add.reset();
  };

  // ------------------------------------------------ step 2: the standards
  if (role) {
    const groups = groupStandards(standards.data?.standards ?? []);
    const body = bulkBody(ticked, held, proficiency, asPreferred ? role.job_role : null);
    const count = body?.items.length ?? 0;
    return (
      <View style={{ gap: space.md }}>
        <Text variant="lead">{role.job_role}</Text>
        <Text tone="muted" variant="small">
          {`${role.qp_code}${role.nsqf_level != null ? ` · ${t("level", { level: role.nsqf_level })}` : ""}`}
        </Text>
        <Button variant="secondary" label={t("changeRole")} onPress={reset} />
        <Text>{t("tickPrompt")}</Text>

        {standards.isPending ? <SkeletonRows count={3} /> : null}
        {standards.isError ? <Notice tone="danger">{t("loadError")}</Notice> : null}

        {groups.map((group) => (
          <View key={group.key} style={{ gap: space.xs }}>
            <Text tone="muted" variant="small">
              {group.requirement === "compulsory"
                ? t("groupCore")
                : group.requirement === "elective"
                  ? t("groupElective", { group: group.name ?? t("electives") })
                  : t("groupOptional")}
            </Text>
            {group.items.map((s) => {
              const already = held.has(s.slug);
              return (
                <Check
                  key={s.slug}
                  checked={already || ticked.has(s.slug)}
                  disabled={already}
                  onPress={() => setTicked((cur) => toggle(cur, s.slug, held))}
                  label={s.name}
                  note={already ? t("alreadyHeld") : (s.nos_code ?? null)}
                />
              );
            })}
          </View>
        ))}

        {groups.length > 0 ? (
          <View style={{ gap: space.md }}>
            <Text tone="muted" variant="small">
              {tp("proficiencyLabel")}
            </Text>
            <ChipRow>
              {[1, 2, 3, 4, 5].map((n) => (
                <Chip key={n} label={String(n)} selected={proficiency === n} onPress={() => setProficiency(n)} />
              ))}
            </ChipRow>
            <Check
              checked={asPreferred}
              onPress={() => setAsPreferred((v) => !v)}
              label={t("asPreferred")}
              note={null}
            />
            <Button
              label={add.isPending ? t("adding") : t("confirm", { count })}
              disabled={body === null}
              busy={add.isPending}
              onPress={() =>
                body &&
                add.mutate(body, {
                  onSuccess: () => {
                    setAdded(body.items.length);
                    setTicked(new Set());
                  },
                })
              }
            />
            {add.isError ? (
              isSignedOut(add.error) ? (
                <SessionExpired />
              ) : (
                // The server's own sentence when it kept one ("a profile may hold at most 60"),
                // the generic line only for a failure that carried nothing.
                <Notice tone="danger">{add.error instanceof ApiError && add.error.detail ? add.error.detail : t("saveError")}</Notice>
              )
            ) : null}
            {added !== null && !add.isError ? <Notice tone="info">{t("added", { count: added })}</Notice> : null}
          </View>
        ) : null}
      </View>
    );
  }

  // ---------------------------------------------------- step 1: the role
  const term = query.trim();
  return (
    <View style={{ gap: space.md }}>
      <Text>{t("prompt")}</Text>
      <SearchBox value={query} onChangeText={setQuery} placeholder={t("placeholder")} />
      {term && hits.isPending ? <SkeletonRows count={2} /> : null}
      {term && hits.isError ? (
        <FailureNotice error={hits.error} onRetry={() => void hits.refetch()} />
      ) : null}
      {(hits.data ?? []).map((hit) => (
        <Card key={hit.slug} level="inset" onPress={() => choose(hit)} label={hit.job_role}>
          <Text>{hit.job_role}</Text>
          <BadgeRow>
            <Badge label={t("standardsCount", { count: hit.standards_count })} />
            {hit.match_kind === "alias" ? <Badge tone="brand" label={t("matchedVia", { term: hit.matched_on })} /> : null}
          </BadgeRow>
          <Text tone="muted" variant="small">
            {`${hit.qp_code}${hit.nsqf_level != null ? ` · ${t("level", { level: hit.nsqf_level })}` : ""}`}
          </Text>
          {hit.variants > 1 ? (
            <Text tone="muted" variant="small">
              {t("variants", { count: hit.variants })}
            </Text>
          ) : null}
        </Card>
      ))}
      {term && hits.isFetched && (hits.data ?? []).length === 0 ? <Text tone="muted">{t("noRoles")}</Text> : null}
    </View>
  );
}

/** A tickbox row: the whole row is the target, and the state is said to a screen reader. */
function Check({
  checked,
  onPress,
  label,
  note,
  disabled = false,
}: {
  checked: boolean;
  onPress: () => void;
  label: string;
  note: string | null;
  disabled?: boolean;
}) {
  const c = useColours();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityLabel={label}
      accessibilityState={{ checked, disabled }}
      disabled={disabled}
      onPress={onPress}
      style={{ minHeight: MIN_TOUCH, flexDirection: "row", alignItems: "center", gap: space.md, opacity: disabled ? 0.6 : 1 }}
    >
      <View
        style={{
          width: 24,
          height: 24,
          borderRadius: 6,
          borderWidth: 2,
          borderColor: checked ? c.brand : c.inputBorder,
          backgroundColor: checked ? c.brand : c.surface,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {checked ? (
          <NativeText
            // The mark is the checkbox's drawn state; its name and state are on the row.
            importantForAccessibility="no"
            accessibilityElementsHidden
            style={{ color: c.brandContrast, fontWeight: "700" }}
          >
            ✓
          </NativeText>
        ) : null}
      </View>
      <View style={{ flex: 1 }}>
        <Text>{label}</Text>
        {note ? (
          <Text tone="muted" variant="small">
            {note}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}
