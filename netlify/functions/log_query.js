/**
 * Log a checker query to Netlify Blobs (persistent key-value store).
 *
 * Called by the frontend after each checker use. Stores one JSON line
 * per query in a blob keyed by date, so we can aggregate later.
 *
 * Body: { level, audience, tool, verdict }
 */

import { getStore } from "@netlify/blobs";

export default async (request, context) => {
  // Only accept POST
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  const { level, audience, tool, verdict } = body;
  if (!level || !audience || !tool) {
    return new Response("Missing required fields", { status: 400 });
  }

  const store = getStore("queries");
  const today = new Date().toISOString().slice(0, 10); // "2026-10-18"
  const key = `queries-${today}.jsonl`;

  const line = JSON.stringify({
    ts: new Date().toISOString(),
    level,
    audience,
    tool,
    verdict: verdict || "UNKNOWN",
  }) + "\n";

  // Append to the day's file. get() returns null if key doesn't exist yet.
  const existing = (await store.get(key, { type: "text" })) || "";
  await store.set(key, existing + line);

  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
};

export const config = {
  path: "/api/log_query",
};
