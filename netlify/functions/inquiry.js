/**
 * Velvet Octopus Films — licensing inquiry handler (Netlify Functions).
 *
 * Required env vars (set in Netlify dashboard → Site configuration → Environment variables):
 *   RESEND_API_KEY   API key from resend.com
 *   FROM_EMAIL       verified sender, e.g. "licensing@velvetoctopusfilms.com"
 *   NOTIFY_TO        comma-separated list of notification inboxes
 *                    e.g. "joshua@velvetoctopusfilms.com,stephan@velvetoctopusfilms.com,matt@velvetoctopusfilms.com"
 *
 * Optional env vars:
 *   ALLOW_ORIGIN     Exact site origin for CORS, e.g. "https://velvetoctopusfilms.com"
 *                    Defaults to "*" — tighten this once the domain is live.
 *
 * Rate limiting note: the in-process Map resets on cold starts (serverless).
 * It catches burst spam within a warm instance. For persistent rate limiting,
 * add Upstash Redis or Netlify Blobs in front of this handler.
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

async function sendEmail({ apiKey, from, to, subject, text, html, replyTo }) {
  const toList = Array.isArray(to) ? to : [to];
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      to: toList,
      subject,
      text,
      html,
      ...(replyTo ? { reply_to: replyTo } : {}),
    }),
  });
  if (!res.ok) {
    throw new Error(`Resend returned ${res.status}: ${await res.text()}`);
  }
}

// Simple in-process rate limiter — 5 requests per IP per 60s window.
// Resets on cold starts; see header comment for persistent alternative.
const RATE = new Map();
const RATE_MAX = 5;
const RATE_WINDOW_MS = 60_000;

function rateCheck(ip) {
  const now = Date.now();
  const entry = RATE.get(ip) || { count: 0, reset: now + RATE_WINDOW_MS };
  if (now > entry.reset) { entry.count = 0; entry.reset = now + RATE_WINDOW_MS; }
  entry.count++;
  RATE.set(ip, entry);
  return entry.count <= RATE_MAX;
}

exports.handler = async (event) => {
  const allowOrigin = process.env.ALLOW_ORIGIN || "*";
  const cors = {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };

  // Reject cross-origin requests when ALLOW_ORIGIN is locked down.
  if (allowOrigin !== "*" && event.httpMethod !== "OPTIONS") {
    const reqOrigin = (event.headers && event.headers.origin) || "";
    if (reqOrigin !== allowOrigin) {
      return { statusCode: 403, headers: cors, body: "Forbidden" };
    }
  }

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: cors, body: "" };
  }
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers: cors, body: "Method not allowed" };
  }

  const ip =
    (event.headers && (event.headers["x-forwarded-for"] || event.headers["client-ip"])) ||
    "unknown";
  if (!rateCheck(ip.split(",")[0].trim())) {
    return {
      statusCode: 429,
      headers: { ...cors, "Content-Type": "application/json", "Retry-After": "60" },
      body: JSON.stringify({ error: "Too many requests. Please wait a moment and try again." }),
    };
  }

  const json = (body, statusCode = 200) => ({
    statusCode,
    headers: { ...cors, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return json({ error: "Invalid JSON body." }, 400);
  }

  // Honeypot
  if (clean(body.website, 200)) return json({ ok: true });

  const name = clean(body.name, 200);
  const company = clean(body.company, 200);
  const email = clean(body.email, 200);
  const titles = clean(body.titles, 1000);
  const message = clean(body.message, 5000);
  const use = USES.includes(clean(body.use)) ? clean(body.use) : "";
  const volume = VOLUMES.includes(clean(body.volume)) ? clean(body.volume) : "";

  if (!name || !company || !validEmail(email)) {
    return json({ error: "Name, company, and a valid email address are required." }, 400);
  }

  const apiKey = process.env.RESEND_API_KEY;
  const fromEmail = process.env.FROM_EMAIL || "licensing@velvetoctopusfilms.com";
  const notifyTo = (process.env.NOTIFY_TO || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  if (!apiKey || !notifyTo.length) {
    return json({ error: "Server not configured. Please email us directly." }, 503);
  }

  const about = titles || "the catalog";
  const ns = "(not specified)";
  const from = `Velvet Octopus Films <${fromEmail}>`;

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
    rows
      .map(
        ([k, v]) =>
          `<tr><td style="border-bottom:1px solid #e5e5e5;color:#666;vertical-align:top"><strong>${esc(k)}</strong></td>` +
          `<td style="border-bottom:1px solid #e5e5e5;white-space:pre-wrap">${esc(v)}</td></tr>`
      )
      .join("") +
    `</table>`;

  const replyText =
    `Hi ${name},\n\n` +
    `Thanks for reaching out about ${about}. We'll review your request ` +
    `and get back to you within a few business days with availability, ` +
    `territory, and licensing terms.\n\n` +
    `If you need something sooner, feel free to reply directly to this email.\n\n` +
    `— Velvet Octopus Films`;

  const replyHtml =
    `<p>Hi ${esc(name)},</p>` +
    `<p>Thanks for reaching out about ${esc(about)}. We'll review your ` +
    `request and get back to you within a few business days with availability, ` +
    `territory, and licensing terms.</p>` +
    `<p>If you need something sooner, feel free to reply directly to this email.</p>` +
    `<p style="color:#6B4D8A">— Velvet Octopus Films</p>`;

  try {
    await sendEmail({
      apiKey,
      from,
      to: notifyTo,
      subject: `New licensing inquiry — ${company}`,
      text: notifyText,
      html: notifyHtml,
      replyTo: email,
    });

    let autoReplySent = true;
    try {
      await sendEmail({
        apiKey,
        from,
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
};
