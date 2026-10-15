import { BULK_MAX, bulkBody, groupStandards, toggle, type Standard } from "./role-picker";

const std = (slug: string, requirement: Standard["requirement"], group_name: string | null = null) =>
  ({ id: slug, slug, name: slug, skill_type: "technical", requirement, group_name }) as unknown as Standard;

describe("grouping a qualification's standards", () => {
  it("keeps the server's order and starts a new group when the requirement or the group changes", () => {
    const groups = groupStandards([
      std("a", "compulsory"),
      std("b", "compulsory"),
      std("c", "elective", "Pick one"),
      std("d", "elective", "Pick one"),
      std("e", "elective", "Another"),
      std("f", "optional"),
    ]);
    expect(groups.map((g) => [g.requirement, g.name, g.items.map((i) => i.slug)])).toEqual([
      ["compulsory", null, ["a", "b"]],
      ["elective", "Pick one", ["c", "d"]],
      ["elective", "Another", ["e"]],
      ["optional", null, ["f"]],
    ]);
  });

  it("never flattens electives of different groups into one", () => {
    const groups = groupStandards([std("a", "elective", "X"), std("b", "elective", "Y")]);
    expect(groups).toHaveLength(2);
  });

  it("is empty for nothing", () => {
    expect(groupStandards([])).toEqual([]);
  });
});

describe("ticking", () => {
  const held = new Set(["owned"]);

  it("starts with nothing ticked and flips one at a time without touching the old set", () => {
    const none = new Set<string>();
    const one = toggle(none, "a", held);
    expect([...none]).toEqual([]);
    expect([...one]).toEqual(["a"]);
    expect([...toggle(one, "a", held)]).toEqual([]);
  });

  it("cannot tick a standard already on the profile", () => {
    expect([...toggle(new Set(), "owned", held)]).toEqual([]);
  });
});

describe("the request that adds them", () => {
  const held = new Set(["owned"]);

  it("is null when nothing is ticked, so there is nothing to send", () => {
    expect(bulkBody(new Set(), held, 3, "Ward boy")).toBeNull();
  });

  it("carries the proficiency and the preferred role, and never a held standard", () => {
    const body = bulkBody(new Set(["a", "owned", "b"]), held, 4, "  Ward boy ");
    expect(body).toEqual({
      items: [
        { skill_slug: "a", proficiency: 4 },
        { skill_slug: "b", proficiency: 4 },
      ],
      preferred_role_title: "Ward boy",
    });
  });

  it("sends no preferred role when the person did not ask for one", () => {
    expect(bulkBody(new Set(["a"]), held, 3, null)?.preferred_role_title).toBeNull();
    expect(bulkBody(new Set(["a"]), held, 3, "   ")?.preferred_role_title).toBeNull();
  });

  it("cuts the role title to the server's limit and the batch to its cap", () => {
    const many = new Set(Array.from({ length: BULK_MAX + 5 }, (_, i) => `s${i}`));
    const body = bulkBody(many, held, 3, "x".repeat(300));
    expect(body?.items).toHaveLength(BULK_MAX);
    expect(body?.preferred_role_title).toHaveLength(120);
  });
});
