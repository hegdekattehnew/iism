"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";

import { useMemberships } from "@/lib/org";

import { CollapsiblePanel } from "./CollapsiblePanel";
import { sectionId } from "./admin-sections";

/**
 * The four reference panels of `/admin`, folded and lazily loaded (Sprint 73, UI-16).
 *
 * The `dynamic()` calls are at module level, so each panel is one stable chunk that is fetched the
 * first time its row is opened and never on a visit that does not open it. `/admin` is the route
 * nearest the first-load budget: these four components were a third of what it shipped.
 */
const Programmes = dynamic(() =>
  import("./ProgrammeDashboard").then((m) => m.ProgrammeDashboard),
);
const Districts = dynamic(() => import("./DistrictSkillGap").then((m) => m.DistrictSkillGap));
const Aliases = dynamic(() => import("./RoleAliasEditor").then((m) => m.RoleAliasEditor));
const Enrolment = dynamic(() => import("./EnrolmentUpload").then((m) => m.EnrolmentUpload));

export function ReferencePanels() {
  const t = useTranslations();
  const { data: me } = useMemberships();
  // Enrolment is the admin tier's alone: a row that opens onto nothing is worse than none.
  const admin = me?.staff_tier === "admin";

  return (
    <div className="space-y-4">
      <CollapsiblePanel
        id={sectionId("programmes")}
        title={t("ops.programmeDashboard.title")}
        Panel={Programmes}
      />
      <CollapsiblePanel
        id={sectionId("districts")}
        title={t("ops.districtGap.title")}
        Panel={Districts}
      />
      <CollapsiblePanel id={sectionId("aliases")} title={t("ops.aliasesTitle")} Panel={Aliases} />
      {admin ? (
        <CollapsiblePanel
          id={sectionId("enrolment")}
          title={t("enrolment.title")}
          Panel={Enrolment}
        />
      ) : null}
    </div>
  );
}
