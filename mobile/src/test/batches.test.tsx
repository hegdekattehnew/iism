import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import Batches from "../../app/batches/index";
import BatchDetail from "../../app/batches/[id]";
import Interests from "../../app/interests";
import { BatchCard } from "../ui/BatchCard";
import { NextBatches } from "../ui/NextBatches";
import { account, api, batch, batchInterest, failed, ok, page, resetWorld, router, serve, world } from "./mocks";
import { renderScreen, settle } from "./harness";

jest.mock("../runtime", () => require("./mocks").runtimeModule);
jest.mock("expo-router", () => require("./mocks").routerModule);

beforeEach(() => resetWorld());

const ID = "00000000-0000-4000-8000-000000000001";
const press = async (name: string) => fireEvent.press(await screen.findByRole("button", { name }));
const asked = () => api.GET.mock.calls.map((c) => ({ path: c[0], query: c[1]?.params?.query }));

function signedIn(extra: Record<string, unknown> = {}, kind: "seeker" | "organisation" = "seeker") {
  world.signedIn = true;
  serve(api.GET, { "/auth/me": ok(account(kind)), ...(extra as Record<string, never>) });
}

describe("batches near you", () => {
  it("shows a placeholder first, never 'nothing' before the answer", async () => {
    api.GET.mockReturnValue(new Promise(() => undefined));
    await renderScreen(<Batches />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(screen.queryByText("No batches to show")).toBeNull();
  });

  it("says who sells the course and who runs it, with the dates, the place, the seats and the fee", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1)])));
    await renderScreen(<Batches />);
    expect(await screen.findByText("Welding basics 1")).toBeTruthy();
    expect(screen.getByText("Course by Seller Academy")).toBeTruthy();
    expect(screen.getByText("Delivered by Partner Skills at Hadapsar Centre")).toBeTruthy();
    expect(screen.getByText("9 Nov 2026 to 9 Dec 2026")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("12 of 20 seats left · ₹4,000")).toBeTruthy();
    expect(screen.getAllByText("In person").length).toBeGreaterThan(1);
    expect(screen.getByText("In your district")).toBeTruthy();
    expect(screen.getByText("Mon to Fri, 9 to 1")).toBeTruthy();
  });

  it("prints the server's count, not the page's length", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1)], 41)));
    await renderScreen(<Batches />);
    expect(await screen.findByText("41 batches")).toBeTruthy();
  });

  it("says plainly when there is none", async () => {
    api.GET.mockResolvedValue(ok(page([])));
    await renderScreen(<Batches />);
    expect(await screen.findByText("No batches to show")).toBeTruthy();
  });

  it("says it could not load when it could not, and not that there are none", async () => {
    api.GET.mockResolvedValue(failed(500));
    await renderScreen(<Batches />);
    await settle();
    expect((await screen.findAllByText(/Could not load|Something went wrong|try again/i)).length).toBeGreaterThan(0);
    expect(screen.queryByText("No batches to show")).toBeNull();
  });

  it("labels a batch in another state and never hides it", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1, { reach: "elsewhere" }), batch(2, { reach: "unknown" })])));
    await renderScreen(<Batches />);
    expect(await screen.findByText("Outside your state")).toBeTruthy();
    expect(screen.getAllByText(/Welding basics/)).toHaveLength(2);
    expect(screen.queryByText("Place not known")).toBeNull();
  });

  it("asks the server to narrow by how it is taught, and by the course it was opened for", async () => {
    world.params = { course: "welding-1" };
    api.GET.mockResolvedValue(ok(page([batch(1)])));
    await renderScreen(<Batches />);
    await screen.findByText("Welding basics 1");
    expect(asked().at(-1)?.query).toEqual({ limit: 12, offset: 0, course: "welding-1" });
    await press("Online");
    await settle();
    expect(asked().at(-1)?.query).toEqual({ limit: 12, offset: 0, course: "welding-1", mode: "online" });
  });

  it("opens the batch's own screen from a card", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1)])));
    await renderScreen(<Batches />);
    fireEvent.press(await screen.findByRole("button", { name: /Welding basics 1/ }));
    expect(router.push).toHaveBeenCalledWith(`/batches/${ID}`);
  });

  it("makes no personal request for a visitor", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1)])));
    await renderScreen(<Batches />);
    await screen.findByText("Welding basics 1");
    expect(asked().map((c) => c.path)).toEqual(["/batches"]);
  });
});

describe("one batch", () => {
  const open = (extra: Record<string, unknown> = {}) => {
    world.params = { id: ID };
    return { [`/batches/{batch_id}`]: ok(batch(1, extra)) };
  };

  it("asks for it by its id and shows the same card", async () => {
    world.params = { id: ID };
    api.GET.mockResolvedValue(ok(batch(1)));
    await renderScreen(<BatchDetail />);
    expect(await screen.findByText("Delivered by Partner Skills at Hadapsar Centre")).toBeTruthy();
    expect(api.GET.mock.calls[0]).toEqual(["/batches/{batch_id}", { params: { path: { batch_id: ID } } }]);
  });

  it("says a batch that is not there does not exist, with a way back, never a blank screen", async () => {
    world.params = { id: ID };
    api.GET.mockResolvedValue(failed(404));
    await renderScreen(<BatchDetail />);
    expect(await screen.findByText(/does not exist|not found|Not found/i)).toBeTruthy();
  });

  it("asks a visitor to sign in instead of showing a button that would fail", async () => {
    serve(api.GET, open());
    await renderScreen(<BatchDetail />);
    await press("Sign in to register interest");
    expect(router.push).toHaveBeenCalledWith("/sign-in");
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("offers an organisation-only account nothing", async () => {
    signedIn(open(), "organisation");
    await renderScreen(<BatchDetail />);
    await screen.findByText("Delivered by Partner Skills at Hadapsar Centre");
    await settle();
    expect(screen.queryByRole("button", { name: /Register interest/ })).toBeNull();
  });

  it("names the centre and the organisation behind it before anything is sent", async () => {
    signedIn(open());
    await renderScreen(<BatchDetail />);
    await press("Register interest: Welding basics 1");
    const share = await screen.findByText(/Hadapsar Centre will see your name, phone number, email and district/);
    expect(share.props.children).toContain("Partner Skills");
    expect(screen.getByText(/not the organisation that sells the course/)).toBeTruthy();
    expect(screen.getByText(/You can withdraw at any time/)).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("sends the batch and the trimmed note on confirming, and nothing on cancelling", async () => {
    signedIn({ ...open(), "/me/batch-interests": ok([]) });
    serve(api.POST, { "/me/batch-interests": ok(batchInterest(1)) });
    await renderScreen(<BatchDetail />);
    await press("Register interest: Welding basics 1");
    await press("Cancel");
    expect(api.POST).not.toHaveBeenCalled();
    await press("Register interest: Welding basics 1");
    fireEvent.changeText(await screen.findByLabelText("Anything they should know (optional)"), "  evenings only ");
    await press("Register my interest");
    await settle();
    expect(api.POST.mock.calls[0]).toEqual([
      "/me/batch-interests",
      { body: { batch_id: ID, message: "evenings only" } },
    ]);
  });

  it("shows the state in words with a way to take it back, named for the course", async () => {
    signedIn(open({ my_interest: { id: "bi1", status: "contacted" } }));
    serve(api.POST, { "/me/batch-interests/{interest_id}/withdraw": ok(batchInterest(1, { status: "withdrawn" })) });
    await renderScreen(<BatchDetail />);
    expect(await screen.findByText("They got in touch")).toBeTruthy();
    await press("Withdraw: Welding basics 1");
    await settle();
    expect(api.POST.mock.calls[0]).toEqual([
      "/me/batch-interests/{interest_id}/withdraw",
      { params: { path: { interest_id: "bi1" } } },
    ]);
  });

  it.each([
    ["full", "This batch is full. Ask the centre about the next one."],
    ["cancelled", "This batch was cancelled."],
    ["running", "This batch has already started."],
    ["finished", "This batch has ended."],
  ])("says why a %s batch cannot be joined instead of offering the button", async (phase, words) => {
    signedIn(open({ phase, seats_left: 0 }));
    await renderScreen(<BatchDetail />);
    expect(await screen.findByText(words)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Register interest/ })).toBeNull();
  });

  it.each([
    [409, "This batch started yesterday", /This batch started yesterday/],
    [429, "You have registered a lot today", /You have registered a lot today/],
    [403, undefined, /Only a job seeker account can register interest/],
    [500, undefined, /That did not work/],
  ])("shows what the server said when it refuses (%s), and keeps the form", async (status, detail, words) => {
    signedIn(open());
    serve(api.POST, { "/me/batch-interests": failed(status as number, detail) });
    await renderScreen(<BatchDetail />);
    await press("Register interest: Welding basics 1");
    await press("Register my interest");
    expect(await screen.findByText(words)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Register my interest" })).toBeTruthy();
  });

  it("asks again for the batch after registering, so the seats and the state are the server's", async () => {
    signedIn({ ...open(), "/me/batch-interests": ok([]) });
    serve(api.POST, { "/me/batch-interests": ok(batchInterest(1)) });
    await renderScreen(<BatchDetail />);
    await press("Register interest: Welding basics 1");
    await press("Register my interest");
    await settle();
    await waitFor(() => expect(asked().filter((c) => c.path === "/batches/{batch_id}").length).toBeGreaterThanOrEqual(2));
  });
});

const TONES: Record<string, string> = {};

describe("the batches a learner asked about", () => {
  const list = (items: unknown[]) => ({ "/me/course-interests": ok([]), "/me/batch-interests": ok(items) });

  it("is absent for a learner who never looked at a batch", async () => {
    signedIn(list([]));
    await renderScreen(<Interests />);
    await settle();
    expect(screen.queryByText("Batches you asked about")).toBeNull();
  });

  it("shows each with its state in words, the batch's page and a way to withdraw", async () => {
    signedIn(list([batchInterest(1), batchInterest(2, { status: "enrolled" })]));
    serve(api.POST, { "/me/batch-interests/{interest_id}/withdraw": ok(batchInterest(1, { status: "withdrawn" })) });
    await renderScreen(<Interests />);
    expect(await screen.findByText("Batches you asked about")).toBeTruthy();
    expect(screen.getByText("Registered")).toBeTruthy();
    expect(screen.getByText("Enrolled")).toBeTruthy();
    fireEvent.press(screen.getAllByRole("button", { name: "Batch details" })[0]);
    expect(router.push).toHaveBeenCalledWith(`/batches/${ID}`);
    await press("Withdraw: Welding basics 1");
    await settle();
    expect(api.POST.mock.calls[0][0]).toBe("/me/batch-interests/{interest_id}/withdraw");
  });

  it("gives the date a reply is expected by, as an ask, only while nobody has answered", async () => {
    signedIn(list([batchInterest(1), batchInterest(2, { status: "contacted" })]));
    await renderScreen(<Interests />);
    expect(await screen.findByText("Reply expected by 23 Oct 2026")).toBeTruthy();
    expect(screen.getAllByText(/Reply expected by/)).toHaveLength(1);
    expect(screen.getByText("Centres are asked to reply within 3 days.")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Not heard back? Tell us" }));
    expect(router.push).toHaveBeenCalledWith("/contact");
  });

  it("says why a cancelled batch was cancelled and offers nothing to withdraw", async () => {
    signedIn(list([batchInterest(1, { batch: batch(1, { phase: "cancelled", cancel_reason: "centre_closed" }) })]));
    await renderScreen(<Interests />);
    expect(await screen.findByText("The centre closed, so this batch was cancelled.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Withdraw/ })).toBeNull();
    expect(screen.queryByText(/Reply expected by/)).toBeNull();
  });

  it.each([
    ["registered", { status: "registered" }, "Registered"],
    ["withdrawn", { status: "withdrawn" }, "Withdrawn"],
    ["cancelled", { batch: batch(1, { phase: "cancelled", cancel_reason: "centre_closed" }) }, "Registered"],
  ])("draws a %s interest in its own tone", async (_name, extra, word) => {
    signedIn(list([batchInterest(1, extra)]));
    await renderScreen(<Interests />);
    const badge = (await screen.findByText(word)).parent;
    const colour = StyleSheet.flatten(badge?.props.style).backgroundColor;
    expect(colour).toBeTruthy();
    TONES[_name as string] = colour;
  });

  it("gives the three states three different looks", () => {
    expect(new Set(Object.values(TONES)).size).toBe(3);
  });

  it("offers a withdrawn one nothing to press but its page", async () => {
    signedIn(list([batchInterest(1, { status: "withdrawn" })]));
    await renderScreen(<Interests />);
    expect(await screen.findByText("Withdrawn")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Withdraw:/ })).toBeNull();
  });
});

describe("a batch card", () => {
  it("is not itself a button when it holds one, even if it is also given a press", async () => {
    const view = batch(1) as never;
    await renderScreen(<BatchCard batch={view} onPress={() => undefined} footer={<></>} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("a course's next batches", () => {
  it("shows the first three and a way to the rest, for that course", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1), batch(2), batch(3), batch(4)], 7)));
    await renderScreen(<NextBatches course="welding-1" />);
    expect(await screen.findByText("Next batches of this course")).toBeTruthy();
    expect(screen.getAllByText(/Welding basics/)).toHaveLength(3);
    expect(asked()[0].query).toEqual({ limit: 12, offset: 0, course: "welding-1" });
    fireEvent.press(screen.getByRole("button", { name: "See all 7 batches of this course" }));
    expect(router.push).toHaveBeenCalledWith("/batches?course=welding-1");
  });

  it("offers no 'see all' when it has shown them all", async () => {
    api.GET.mockResolvedValue(ok(page([batch(1)])));
    await renderScreen(<NextBatches course="welding-1" />);
    await screen.findByText("Next batches of this course");
    expect(screen.queryByRole("button", { name: /See all/ })).toBeNull();
  });

  it("says nothing for a course nobody planned a batch of", async () => {
    api.GET.mockResolvedValue(ok(page([])));
    await renderScreen(<NextBatches course="welding-1" />);
    await settle();
    expect(screen.queryByText("Next batches of this course")).toBeNull();
  });

  it("says nothing when the read fails", async () => {
    api.GET.mockResolvedValue(failed(500));
    await renderScreen(<NextBatches course="welding-1" />);
    await settle();
    expect(screen.queryByText("Next batches of this course")).toBeNull();
  });
});
