// Safari exposes browser.*; Chromium exposes chrome.*. Both support Promise APIs
// for the methods used here on current supported browser versions.
globalThis.PiExtension = globalThis.browser || globalThis.chrome;
