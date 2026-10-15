import { BUDGET_MAX, BUDGET_STORAGE_KEY, budgetQuery, createBudgetStore, parseBudget } from "./course-budget";

function memory(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: jest.fn(async (k: string) => (k in data ? data[k] : null)),
    setItem: jest.fn(async (k: string, v: string) => void (data[k] = v)),
    removeItem: jest.fn(async (k: string) => void delete data[k]),
  };
}

describe("parseBudget", () => {
  it("blank is no budget, a number is rupees, grouping is ignored", () => {
    expect(parseBudget("")).toEqual({ ok: true, value: null });
    expect(parseBudget("   ")).toEqual({ ok: true, value: null });
    expect(parseBudget("5000")).toEqual({ ok: true, value: 5000 });
    expect(parseBudget("12,000")).toEqual({ ok: true, value: 12000 });
    expect(parseBudget("0")).toEqual({ ok: true, value: 0 });
  });

  it.each(["abc", "-5", "1.5", "1e5", "5000rs", "100000000"])("refuses %s", (text) => {
    expect(parseBudget(text).ok).toBe(false);
  });

  it("the largest budget is the server's", () => {
    expect(parseBudget(String(BUDGET_MAX))).toEqual({ ok: true, value: BUDGET_MAX });
    expect(parseBudget(String(BUDGET_MAX + 1)).ok).toBe(false);
  });
});

describe("budgetQuery", () => {
  it("sends nothing when there is no budget, and zero when the person said zero", () => {
    expect(budgetQuery(null)).toEqual({});
    expect(budgetQuery(0)).toEqual({ budget_inr: 0 });
    expect(budgetQuery(8000)).toEqual({ budget_inr: 8000 });
  });
});

describe("the store", () => {
  it("remembers a budget and tells whoever is watching", async () => {
    const disk = memory();
    const store = createBudgetStore(disk);
    const seen = jest.fn();
    store.subscribe(seen);
    store.set(7500);
    expect(store.get()).toBe(7500);
    expect(seen).toHaveBeenCalledTimes(1);
    expect(disk.setItem).toHaveBeenCalledWith(BUDGET_STORAGE_KEY, "7500");
  });

  it("an out-of-range or fractional value is no budget, and is not written", () => {
    const disk = memory();
    const store = createBudgetStore(disk);
    store.set(BUDGET_MAX + 1);
    expect(store.get()).toBeNull();
    store.set(12.5);
    expect(store.get()).toBeNull();
    expect(disk.setItem).not.toHaveBeenCalled();
  });

  it("restores what was kept, and treats rubbish on disk as nothing", async () => {
    const good = createBudgetStore(memory({ [BUDGET_STORAGE_KEY]: "3000" }));
    await good.restore();
    expect(good.get()).toBe(3000);
    const bad = createBudgetStore(memory({ [BUDGET_STORAGE_KEY]: "lots" }));
    await bad.restore();
    expect(bad.get()).toBeNull();
  });

  it("works when storage refuses: the budget still applies for this visit", async () => {
    const broken = {
      getItem: jest.fn().mockRejectedValue(new Error("no")),
      setItem: jest.fn().mockRejectedValue(new Error("no")),
      removeItem: jest.fn().mockRejectedValue(new Error("no")),
    };
    const store = createBudgetStore(broken);
    await store.restore();
    expect(store.get()).toBeNull();
    store.set(2000);
    expect(store.get()).toBe(2000);
    await expect(store.clear()).resolves.toBeUndefined();
    expect(store.get()).toBeNull();
  });

  it("clearing forgets it in memory and on disk, so a shared phone starts empty", async () => {
    const disk = memory({ [BUDGET_STORAGE_KEY]: "9000" });
    const store = createBudgetStore(disk);
    await store.restore();
    await store.clear();
    expect(store.get()).toBeNull();
    expect(disk.data[BUDGET_STORAGE_KEY]).toBeUndefined();
  });

  it("setting none removes the stored value", () => {
    const disk = memory({ [BUDGET_STORAGE_KEY]: "9000" });
    const store = createBudgetStore(disk);
    store.set(null);
    expect(disk.removeItem).toHaveBeenCalledWith(BUDGET_STORAGE_KEY);
  });
});
