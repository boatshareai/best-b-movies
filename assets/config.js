/* Velvet Octopus Films — site config
   ENDPOINT and SUBMISSION_ENDPOINT point at deployed Cloudflare Workers.
   Leave them empty during local dev; the forms will show a mailto fallback.
   Never put RESEND_API_KEY here — it lives in the Worker env vars only. */
window.VOF_CONFIG = {
  ENDPOINT: "",
  SUBMISSION_ENDPOINT: "",
  SITE_CONTACT_EMAIL: "hello@velvetoctopusfilms.com",
  LICENSING_EMAIL: "licensing@velvetoctopusfilms.com",
  YOUTUBE_CHANNEL_URL: "",
};
