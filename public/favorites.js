/*
 * favorites.js  -  Saved ("favorite") trips
 *
 * The list logic only, with no page code, so Node can test it
 * (tests/favorites.test.js). app.js shows the list and saves it.
 * One trip: { name: "Manila to Tagaytay", stops: ["Manila", "Tagaytay"], mode: "car" }
 */
const Favorites = (() => {
  const MAX_TRIPS = 20;      // past this, the oldest saved trip is dropped
  const MAX_NAME = 40;       // characters; longer names are cut
  const MODES = ["car", "foot", "bike"];

  // A favorite is usable if it has a name, at least 2 stops and a known mode
  function isValid(trip) {
    return Boolean(trip) && typeof trip.name === "string" && trip.name.trim() !== ""
      && Array.isArray(trip.stops) && trip.stops.filter((s) => typeof s === "string" && s.trim()).length >= 2
      && MODES.includes(trip.mode);
  }

  // Read the saved text back into a list. Saved data can be missing, from an
  // older version or broken, so anything unusable is left out, never thrown.
  function parse(text) {
    let list;
    try {
      list = JSON.parse(text);
    } catch {
      return [];
    }
    return Array.isArray(list) ? list.filter(isValid).slice(0, MAX_TRIPS) : [];
  }

  // Add a trip at the top and return the new list (the old one is not changed).
  // A saved trip with the same name (in any letter case) is replaced.
  // Throws an Error whose message can be shown to the user.
  function add(list, name, stops, mode) {
    const trip = {
      name: String(name).trim().slice(0, MAX_NAME),
      stops: stops.map((s) => String(s).trim()).filter(Boolean),
      mode,
    };
    if (!trip.name) throw new Error("Give the trip a name first.");
    if (trip.stops.length < 2) throw new Error("A trip needs at least a start and a destination.");
    if (!MODES.includes(trip.mode)) throw new Error("Pick Driving, Walking or Cycling first.");
    const others = list.filter((t) => t.name.toLowerCase() !== trip.name.toLowerCase());
    return [trip, ...others].slice(0, MAX_TRIPS);
  }

  // The list without the trip of this name
  function remove(list, name) {
    return list.filter((t) => t.name !== name);
  }

  // True if a trip with this name (in any letter case) is already saved
  function has(list, name) {
    const wanted = String(name).trim().toLowerCase();
    return list.some((t) => t.name.toLowerCase() === wanted);
  }

  // A name to suggest, from the first and last stop without the country:
  // "Manila, Philippines" ... "Batangas City, Philippines" -> "Manila to Batangas City"
  function suggestName(stops) {
    const short = (stop) => stop.split(",")[0].trim();
    return `${short(stops[0])} to ${short(stops[stops.length - 1])}`.slice(0, MAX_NAME);
  }

  // One line under the name: "Manila to Batangas City · 3 stops"
  function describe(trip) {
    const text = suggestName(trip.stops);
    return trip.stops.length > 2 ? `${text} · ${trip.stops.length} stops` : text;
  }

  return { MAX_TRIPS, MAX_NAME, parse, add, remove, has, suggestName, describe };
})();

// Lets Node load this file in the tests; browsers skip this line
if (typeof module !== "undefined") module.exports = Favorites;
