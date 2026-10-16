import { fireEvent, screen } from "@testing-library/react-native";

import { JobCard } from "../ui/JobCard";
import { renderScreen } from "./harness";
import { job, resetWorld, tenant } from "./mocks";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const NOW = Date.parse("2026-10-16T06:00:00Z");
const DAY = 86_400_000;
const card = (extra: Record<string, unknown> = {}, onPress = jest.fn()) =>
  renderScreen(<JobCard job={job(1, extra) as never} onPress={onPress} now={NOW} />);

/** Sprint 69, UI-04/05/10: what a card says, and what it will not say. */
describe("a vacancy card", () => {
  it("leads with who, where and how much a month", async () => {
    await card();
    expect(screen.getByText("Ward assistant 1")).toBeTruthy();
    expect(screen.getByText("Apollo Care")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("About ₹20,000–30,000 a month")).toBeTruthy();
  });

  it("does not print the yearly figure or the NSQF level", async () => {
    await card();
    expect(screen.queryByText(/per year/)).toBeNull();
    expect(screen.queryByText(/2,40,000|3,60,000/)).toBeNull();
    expect(screen.queryByText(/NSQF/)).toBeNull();
  });

  it("marks a verified employer", async () => {
    await card();
    expect(screen.getByText("Verified employer")).toBeTruthy();
  });

  it("never says 'not verified' on a card", async () => {
    await card({ tenant: { ...tenant, is_verified: false } });
    expect(screen.queryByText(/verified/i)).toBeNull();
  });

  it("says how long ago it was posted, and nothing when it has no date", async () => {
    await card({ published_at: new Date(NOW - 3 * DAY - 1000).toISOString() });
    expect(screen.getByText("Posted 3 days ago")).toBeTruthy();
  });

  it("says nothing about posting for a vacancy with no date", async () => {
    await card({ published_at: null });
    expect(screen.queryByText(/Posted/)).toBeNull();
  });

  it("shows the employment type only when it is not the ordinary one", async () => {
    await card();
    expect(screen.queryByText("Full time")).toBeNull();
  });

  it("shows only the closing date for an ordinary job that closes soon, never 'Full time' beside it", async () => {
    await card({ closes_at: new Date(NOW + 3 * DAY - 1000).toISOString() });
    expect(screen.getByText("Closes in 3 days")).toBeTruthy();
    expect(screen.queryByText("Full time")).toBeNull();
  });

  it("shows a part-time type", async () => {
    await card({ employment_type: "part_time" });
    expect(screen.getByText("Part time")).toBeTruthy();
  });

  it("keeps a gig's posted figure", async () => {
    await card({ employment_type: "gig", salary_min_inr: 5000, salary_max_inr: 8000 });
    expect(screen.getByText("₹5,000–8,000 as posted")).toBeTruthy();
    expect(screen.queryByText(/a month/)).toBeNull();
  });

  it("says how soon it closes, only when that is near", async () => {
    await card({ closes_at: new Date(NOW + 3 * DAY - 1000).toISOString() });
    expect(screen.getByText("Closes in 3 days")).toBeTruthy();
  });

  it("says nothing of closing when it is far off", async () => {
    await card({ closes_at: new Date(NOW + 90 * DAY).toISOString() });
    expect(screen.queryByText(/Closes in/)).toBeNull();
  });

  it("opens on press, as a button named for the vacancy", async () => {
    const onPress = jest.fn();
    await card({}, onPress);
    await fireEvent.press(screen.getByRole("button", { name: "Ward assistant 1" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it("says it in Hindi too, from the same catalogue", async () => {
    await renderScreen(<JobCard job={job(1) as never} onPress={jest.fn()} now={NOW} />, "hi");
    expect(screen.getByText("लगभग ₹20,000–30,000 प्रति माह")).toBeTruthy();
  });
});
