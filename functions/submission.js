/**
 * Velvet Octopus Films — filmmaker submission handler.
 *
 * Sends two emails:
 *   1. auto-reply to the filmmaker
 *   2. notification to the submissions inbox
 *
 * Runs on Cloudflare Workers / Cloudflare Pages Functions.
 *
 * Required env vars:
 *   RESEND_API_KEY         API key from resend.com
 *   FROM_EMAIL             verified sender, e.g. "submit@velvetoctopusfilms.com"
 *   SUBMISSION_NOTIFY_TO   inbox for submission notifications
 * Optional:
 *   ALLOW_ORIGIN           exact origin of the deployed site
 */

const GENRES = [
  "Drama", "Comedy", "Horror", "Thriller", "Action", "Animation", "Documentary", "Other",
];
const DIST_STATUSES = [
  "No distribution",
  "Self-distributed",
  "Festival circuit only",
  "Previously distributed",
  "Currently distributed",
];

const RATE = new Map();
const RATE_MAX = 3;
const RATE_WINDOW_MS = 60_000;

function rateCheck(ip) {
  const now = Date.now();
  const entry = RATE.get(ip) || { count: 0, reset: now + RATE_WINDOW_MS };
  if (now > entry.reset) { entry.count = 0; entry.reset = now + RATE_WINDOW_MS; }
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

function validUrl(v) {
  if (!v) return true; // optional field
  try {
    const u = new URL(v);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch { return false; }
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

    if (allowOrigin !== "*") {
      const reqOrigin = request.headers.get("Origin") || "";
      if (reqOrigin !== allowOrigin) {
        return new Response("Forbidden", { status: 403 });
      }
    }

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

    // Honeypot
    if (clean(body.website, 200)) {
      return json({ ok: true });
    }

    const name = clean(body.name, 200);
    const email = clean(body.email, 200);
    const filmTitle = clean(body.film_title, 400);
    const year = clean(body.year, 10);
    const genre = GENRES.includes(clean(body.genre)) ? clean(body.genre) : "";
    const runtime = clean(body.runtime, 20);
    const synopsis = clean(body.synopsis, 5000);
    const screenerLink = clean(body.screener_link, 1000);
    const distStatus = DIST_STATUSES.includes(clean(body.distribution_status))
      ? clean(body.distribution_status)
      : "";
    const rightsConfirmed = body.rights_confirmation === true || body.rights_confirmation === "true";

    if (!name || !validEmail(email) || !filmTitle || !year || !synopsis || !rightsConfirmed) {
      return json(
        { error: "Name, email, film title, year, synopsis, and rights confirmation are required." },
        400
      );
    }

    if (screenerLink && !validUrl(screenerLink)) {
      return json({ error: "Screener link must be a valid URL." }, 400);
    }

    const ns = "(not specified)";

    const replyText =
      `Hi ${name},\n\n` +
      `Thanks for submitting ${filmTitle}. We’ll read every submission ` +
      `and be in touch if it’s a good fit.\n\n` +
      `— Velvet Octopus Films`;

    const replyHtml =
      `<p>Hi ${esc(name)},</p>` +
      `<p>Thanks for submitting <strong>${esc(filmTitle)}</strong>. We’ll read every ` +
      `submission and be in touch if it’s a good fit.</p>` +
      `<p style="color:#6B4D8A">— Velvet Octopus Films</p>`;

    const rows = [
      ["Name", name],
      ["Email", email],
      ["Film title", filmTitle],
      ["Year", year],
      ["Genre", genre || ns],
      ["Runtime", runtime ? runtime + " min" : ns],
      ["Synopsis", synopsis],
      ["Screener link", screenerLink || ns],
      ["Distribution status", distStatus || ns],
      ["Rights confirmed", "Yes"],
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
        to: env.SUBMISSION_NOTIFY_TO,
        subject: `New film submission — ${filmTitle} (${year})`,
        text: notifyText,
        html: notifyHtml,
        replyTo: email,
      });

      let autoReplySent = true;
      try {
        await sendEmail(env, {
          to: email,
          subject: `We received your submission — ${filmTitle}`,
          text: replyText,
          html: replyHtml,
        });
      } catch (e) {
        autoReplySent = false;
        console.error("auto-reply failed:", e.message);
      }

      return json({ ok: true, autoReplySent });
    } catch (e) {
      console.error("submission failed:", e.message);
      return json({ error: "Could not send the submission. Please email us directly." }, 502);
    }
  },
};
