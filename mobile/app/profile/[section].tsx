import { Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError, isSignedOut } from "../../src/core/errors";
import {
  blankForm,
  formFromEntry,
  isCollection,
  summaryOf,
  type Collection,
  type Entry,
  type Form,
} from "../../src/core/profile-sections";
import { useMonthName } from "../../src/lib/months";
import { useAddEntry, useProfile, useRemoveEntry, useUpdateEntry } from "../../src/lib/me-queries";
import { space } from "../../src/theme";
import { SeekerGate } from "../../src/ui/gate";
import { Card, FailureNotice, SkeletonRows } from "../../src/ui/list";
import { Button, Notice, Screen, Text } from "../../src/ui/primitives";
import { SectionForm } from "../../src/ui/SectionForm";
import { SessionExpired } from "../../src/ui/session";

/**
 * One section of the profile's history: the entries, and a form to add, change or remove one. The
 * six sections are one screen over one table (`core/profile-sections.ts`), as on the website. The
 * path segment is checked against that table, so a mistyped or hostile link reaches nothing.
 */
export default function Section() {
  const { section } = useLocalSearchParams<{ section: string }>();
  const s = useTranslations("mobile.profileSections");
  const t = useTranslations("profilePage");
  if (!isCollection(section)) {
    return (
      <Screen>
        <Stack.Screen options={{ title: s("title") }} />
        <Notice tone="warning">{s("notFound")}</Notice>
      </Screen>
    );
  }
  return (
    <Screen>
      <Stack.Screen options={{ title: s(`names.${section}`) }} />
      <Text variant="title">{s(`names.${section}`)}</Text>
      <SeekerGate prompt={t("signInPrompt")}>
        <Body collection={section} />
      </SeekerGate>
    </Screen>
  );
}

type Editing = { id: string | null; form: Form };

function Body({ collection }: { collection: Collection }) {
  const s = useTranslations("mobile.profileSections");
  const t = useTranslations("profilePage");
  const monthName = useMonthName();
  const profile = useProfile();
  const add = useAddEntry(collection);
  const update = useUpdateEntry(collection);
  const remove = useRemoveEntry(collection);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  if (profile.isPending) return <SkeletonRows count={3} />;
  if (profile.isError) {
    return isSignedOut(profile.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={profile.error} onRetry={() => void profile.refetch()} />
    );
  }
  const entries = ((profile.data as unknown as Record<string, Entry[] | undefined>)[collection] ?? []) as Entry[];
  const write = editing?.id ? update : add;

  const sentence = (error: unknown) =>
    error instanceof ApiError && error.detail ? error.detail : t("errors.generic");

  if (editing) {
    return (
      <View style={{ gap: space.lg }}>
        {write.isError && isSignedOut(write.error) ? <SessionExpired /> : null}
        <SectionForm
          // A new form for each entry, so one entry's typing never leaks into another.
          key={editing.id ?? "new"}
          collection={collection}
          initial={editing.form}
          busy={write.isPending}
          error={write.isError && !isSignedOut(write.error) ? sentence(write.error) : null}
          onCancel={() => {
            write.reset();
            setEditing(null);
          }}
          onSubmit={(body) => {
            const done = { onSuccess: () => setEditing(null) };
            if (editing.id) update.mutate({ id: editing.id, body }, done);
            else add.mutate(body, done);
          }}
        />
      </View>
    );
  }

  return (
    <View style={{ gap: space.md }}>
      {entries.length === 0 ? <Text tone="muted">{s("empty")}</Text> : null}
      {entries.map((entry) => {
        const line = summaryOf(collection, entry, (m) => monthName(m, "short"));
        const confirming = removing === entry.id;
        const mine = remove.variables === entry.id;
        return (
          <Card key={entry.id}>
            <Text variant="lead">{line.title}</Text>
            {line.lines.map((l) => (
              <Text key={l} tone="muted" variant="small">
                {l}
              </Text>
            ))}
            <Button
              variant="secondary"
              label={s("edit")}
              accessibilityLabel={`${s("edit")}: ${line.title}`}
              onPress={() => {
                write.reset();
                setEditing({ id: entry.id, form: formFromEntry(collection, entry) });
              }}
            />
            {confirming ? (
              <View style={{ gap: space.sm }}>
                <Text>{s("removeConfirm")}</Text>
                <Button
                  label={mine && remove.isPending ? s("saving") : s("removeYes")}
                  busy={mine && remove.isPending}
                  onPress={() => remove.mutate(entry.id, { onSuccess: () => setRemoving(null) })}
                />
                <Button variant="secondary" label={s("cancel")} onPress={() => setRemoving(null)} />
              </View>
            ) : (
              <Button
                variant="secondary"
                label={s("remove")}
                accessibilityLabel={`${s("remove")}: ${line.title}`}
                onPress={() => {
                  remove.reset();
                  setRemoving(entry.id);
                }}
              />
            )}
            {mine && remove.isError ? (
              isSignedOut(remove.error) ? <SessionExpired /> : <Notice tone="danger">{sentence(remove.error)}</Notice>
            ) : null}
          </Card>
        );
      })}
      <Button
        label={s("add")}
        onPress={() => {
          write.reset();
          setEditing({ id: null, form: blankForm(collection) });
        }}
      />
    </View>
  );
}
