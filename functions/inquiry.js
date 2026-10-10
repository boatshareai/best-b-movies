/**
 * Velvet Octopus Films — licensing inquiry handler.
 *
 * Sends two emails:
 *   1. auto-reply to the inquirer
 *   2. notification to the licensing inbox
 *
 * Runs on Cloudflare Workers / Cloudflare Pages Functions.
 *
 * Required env vars:
 *   RESEND_API_KEY     API key from resend.com
 *   FROM_EMAIL         verified sender, e.g. "licensing@velvetoctopusfilms.com"
 *   NOTIFY_TO          inbox for inquiry notifications
 * Optional:
 *   ALLOW_ORIGIN       exact origin of the deployed site, e.g. "https://velvetoctopusfilms.com"
 *                      (defaults to "*" — tighten once the domain is live)
 */

const USES = [
  "Streaming platform",
  "Broadcast",
  "Home video or digital sell-through",
  "Educational or institutional",
  "Other",
];
const VOLUMES = [
  "Single title",
  "Small package (2–10)",
  "Full or near-full catalog",
];

// Simple in-memory rate limiter: max 5 requests per IP per 60-second window.
const RATE = new Map();
const RATE_MAX = 5;
const RATE_WINDOW_MS = 60_000;

function rateCheck(ip) {
  const now = Date.now();
  const entry = RATE.get(ip) || { count: 0, reset: now + RATE_WINDOW_MS };
  if (now > entry.reset) {
    entry.count = 0;
    entry.reset = now + RATE_WINDOW_MS;
  }
  entry.count++;
  RATE.set(ip, entry);
  return entry.count <= RATE_MAX;
}

function clean(v, max = 2000) {
  return typeof v === "string" ? v.trim().slice(0, max) : "";
}

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
}

function esc(s) {
  return String(s).replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );
}

async function sendEmail(env, { to, subject, text, html, replyTo }) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `Velvet Octopus Films <${env.FROM_EMAIL}>`,
      to: [to],
      subject,
      text,
      html,
      ...(replyTo ? { reply_to: replyTo } : {}),
    }),
  });
  if (!res.ok) {
    throw new Error(`email provider returned ${res.status}: ${await res.text()}`);
  }
}

export default {
  async fetch(request, env) {
    const allowOrigin = env.ALLOW_ORIGIN || "*";
    const cors = {
      "Access-Control-Allow-Origin": allowOrigin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: cors });
    }

    // Origin check: reject if caller doesn't match the configured allowed origin.
    if (allowOrigin !== "*") {
      const reqOrigin = request.headers.get("Origin") || "";
      if (reqOrigin !== allowOrigin) {
        return new Response("Forbidden", { status: 403 });
      }
    }

    // Rate limiting by IP
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (!rateCheck(ip)) {
      return new Response(
        JSON.stringify({ error: "Too many requests. Please wait a moment and try again." }),
        { status: 429, headers: { ...cors, "Content-Type": "application/json" } }
      );
    }

    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { ...cors, "Content-Type": "application/json" },
      });

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON body." }, 400);
    }

    // Honeypot: bots fill "website", humans leave it blank.
    if (clean(body.website, 200)) {
      return json({ ok: true }); // silent success to not tip off bots
    }

    const name = clean(body.name, 200);
    const company = clean(body.company, 200);
    const email = clean(body.email, 200);
    const titles = clean(body.titles, 1000);
    const message = clean(body.message, 5000);
    const use = USES.includes(clean(body.use)) ? clean(body.use) : "";
    const volume = VOLUMES.includes(clean(body.volume)) ? clean(body.volume) : "";

    if (!name || !company || !validEmail(email)) {
      return json(
        { error: "Name, company, and a valid email address are required." },
        400
      );
    }

    const about = titles || "the catalog";
    const ns = "(not specified)";

    const replyText =
      `Hi ${name},\n\n` +
      `Thanks for reaching out about ${about}. We’ll review your request ` +
      `and get back to you within a few business days with availability, ` +
      `territory, and licensing terms.\n\n` +
      `If you need something sooner, feel free to reply directly to this email.\n\n` +
      `— Velvet Octopus Films`;

    const replyHtml =
      `<p>Hi ${esc(name)},</p>` +
      `<p>Thanks for reaching out about ${esc(about)}. We’ll review your ` +
      `request and get back to you within a few business days with availability, ` +
      `territory, and licensing terms.</p>` +
      `<p>If you need something sooner, feel free to reply directly to this email.</p>` +
      `<p style="color:#6B4D8A">— Velvet Octopus Films</p>`;

    const rows = [
      ["Name", name],
      ["Company", company],
      ["Email", email],
      ["Titles of interest", titles || ns],
      ["Intended use", use || ns],
      ["Estimated volume", volume || ns],
      ["Message", message || "(none)"],
    ];

    const notifyText = rows.map(([k, v]) => `${k}: ${v}`).join("\n");
    const notifyHtml =
      `<table cellpadding="6" style="border-collapse:collapse;font-family:sans-serif;font-size:14px">` +
      rows.map(([k, v]) =>
        `<tr><td style="border-bottom:1px solid #e5e5e5;color:#666;vertical-align:top"><strong>${esc(k)}</strong></td>` +
        `<td style="border-bottom:1px solid #e5e5e5;white-space:pre-wrap">${esc(v)}</td></tr>`
      ).join("") +
      `</table>`;

    try {
      await sendEmail(env, {
        to: env.NOTIFY_TO,
        subject: `New licensing inquiry — ${company}`,
        text: notifyText,
        html: notifyHtml,
        replyTo: email,
      });

      let autoReplySent = true;
      try {
        await sendEmail(env, {
          to: email,
          subject: "We received your Velvet Octopus Films inquiry",
          text: replyText,
          html: replyHtml,
        });
      } catch (e) {
        autoReplySent = false;
        console.error("auto-reply failed:", e.message);
      }

      return json({ ok: true, autoReplySent });
    } catch (e) {
      console.error("inquiry failed:", e.message);
      return json({ error: "Could not send the inquiry. Please email us directly." }, 502);
    }
  },
};
