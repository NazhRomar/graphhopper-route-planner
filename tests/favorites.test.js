/*
 * Test cases for public/favorites.js (saved trips), using Node's own test
 * runner, so nothing needs to be installed.
 * Run: node --test tests/*.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const Favorites = require("../public/favorites.js");

const TAGAYTAY = { name: "Weekend", stops: ["Manila", "Tagaytay"], mode: "car" };

// ------------------------------------------------------------------- add
test("add puts the new trip first", () => {
  const list = Favorites.add([TAGAYTAY], "Work", ["Pasig", "Makati"], "bike");
  assert.deepEqual(list.map((t) => t.name), ["Work", "Weekend"]);
});

test("add does not change the old list", () => {
  const old = [TAGAYTAY];
  Favorites.add(old, "Work", ["Pasig", "Makati"], "car");
  assert.equal(old.length, 1);
});

test("add replaces a trip with the same name, in any letter case", () => {
  const list = Favorites.add([TAGAYTAY], "weekend", ["Manila", "Batangas"], "foot");
  assert.equal(list.length, 1);
  assert.deepEqual(list[0], { name: "weekend", stops: ["Manila", "Batangas"], mode: "foot" });
});

test("add trims the name and the stops, and drops empty stops", () => {
  const [trip] = Favorites.add([], "  Beach  ", [" Manila ", "", "  ", "Nasugbu"], "car");
  assert.deepEqual(trip, { name: "Beach", stops: ["Manila", "Nasugbu"], mode: "car" });
});

test("add cuts names that are too long", () => {
  const [trip] = Favorites.add([], "x".repeat(100), ["A", "B"], "car");
  assert.equal(trip.name.length, Favorites.MAX_NAME);
});

test("add keeps only the newest trips", () => {
  let list = [];
  for (let i = 0; i < Favorites.MAX_TRIPS + 5; i++) list = Favorites.add(list, `Trip ${i}`, ["A", "B"], "car");
  assert.equal(list.length, Favorites.MAX_TRIPS);
  assert.equal(list[0].name, `Trip ${Favorites.MAX_TRIPS + 4}`);
});

test("add refuses a trip without a name", () => {
  assert.throws(() => Favorites.add([], "   ", ["A", "B"], "car"), /name/);
});

test("add refuses a trip with fewer than 2 stops", () => {
  assert.throws(() => Favorites.add([], "Short", ["Manila", ""], "car"), /start and a destination/);
});

test("add refuses an unknown travel mode", () => {
  assert.throws(() => Favorites.add([], "Boat", ["A", "B"], "boat"), /Driving, Walking or Cycling/);
});

// ------------------------------------------------------- remove and has
test("remove deletes only the trip with that name", () => {
  const list = Favorites.add([TAGAYTAY], "Work", ["Pasig", "Makati"], "car");
  assert.deepEqual(Favorites.remove(list, "Work"), [TAGAYTAY]);
});

test("has finds a name in any letter case", () => {
  assert.equal(Favorites.has([TAGAYTAY], " WEEKEND "), true);
  assert.equal(Favorites.has([TAGAYTAY], "Work"), false);
});

// ----------------------------------------------------------------- parse
test("parse reads a saved list back", () => {
  assert.deepEqual(Favorites.parse(JSON.stringify([TAGAYTAY])), [TAGAYTAY]);
});

test("parse gives an empty list for missing or broken data", () => {
  for (const text of [null, "", "not json", "{}", "42"]) assert.deepEqual(Favorites.parse(text), []);
});

test("parse leaves out trips that are not usable", () => {
  const saved = [
    TAGAYTAY,
    { name: "", stops: ["A", "B"], mode: "car" },        // no name
    { name: "One stop", stops: ["A"], mode: "car" },      // 1 stop
    { name: "Boat", stops: ["A", "B"], mode: "boat" },    // unknown mode
    "just text",
  ];
  assert.deepEqual(Favorites.parse(JSON.stringify(saved)), [TAGAYTAY]);
});

// ------------------------------------------------------- names and text
test("suggestName uses the first and last stop without the country", () => {
  const stops = ["Manila, Philippines", "Tagaytay, Philippines", "Batangas City, Philippines"];
  assert.equal(Favorites.suggestName(stops), "Manila to Batangas City");
});

test("describe adds the number of stops when there are more than 2", () => {
  assert.equal(Favorites.describe(TAGAYTAY), "Manila to Tagaytay");
  assert.equal(Favorites.describe({ ...TAGAYTAY, stops: ["A", "B", "C"] }), "A to C · 3 stops");
});
