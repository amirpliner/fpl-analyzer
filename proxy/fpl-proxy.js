// Cloudflare Worker: adds CORS headers so the static site's browser JS can
// call the FPL API live (fantasy.premierleague.com sends no CORS headers
// of its own). Only forwards GET requests to a small allow-list of FPL API
// paths - it is not an open proxy to arbitrary hosts.

const FPL_BASE = "https://fantasy.premierleague.com/api";

const ALLOWED_PREFIXES = [
  "bootstrap-static/",
  "fixtures",
  "entry/",
  "element-summary/",
  "leagues-classic/",
];

const ALLOWED_ORIGINS = [
  "https://amirpliner.github.io",
];

function isAllowedOrigin(origin) {
  return ALLOWED_ORIGINS.includes(origin) || /^http:\/\/localhost(:\d+)?$/.test(origin);
}

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "";
    const allowOrigin = isAllowedOrigin(origin) ? origin : ALLOWED_ORIGINS[0];

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(allowOrigin) });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers: corsHeaders(allowOrigin) });
    }

    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/+/, "");

    if (!ALLOWED_PREFIXES.some(p => path.startsWith(p))) {
      return new Response("Not found", { status: 404, headers: corsHeaders(allowOrigin) });
    }

    const targetUrl = `${FPL_BASE}/${path}${url.search}`;
    const fplResponse = await fetch(targetUrl, {
      headers: { "User-Agent": "Mozilla/5.0" },
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    const body = await fplResponse.text();
    return new Response(body, {
      status: fplResponse.status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        ...corsHeaders(allowOrigin),
      },
    });
  },
};
