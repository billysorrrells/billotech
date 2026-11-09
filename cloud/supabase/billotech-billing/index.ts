// billotech-billing — Square webhooks → BilloTech plans (BILLO BINDER).
// POST /billotech-billing/square   Square webhook (subscription.*, invoice.payment_made, payment.*), HMAC verified.
// POST /billotech-billing/sync     pull subscriptions straight from Square (pg_cron every 10 min + on account link).
// GET  /billotech-billing/plans    public plan list + checkout link (the Pro page reads this).
// Card data never lands here: a payment leaves only sha256(lower(email)|last4) so a subscriber can prove
// "that's my subscription" when they link it to their BilloTech account (billotech-api POST /billing/link).
// Secret: SQUARE_WEBHOOK_SIGNATURE_KEY (from the Square webhook subscription). DB via SUPABASE_DB_URL.
import postgres from "npm:postgres@3.4.5";

async function connect() {
  const DIRECT = Deno.env.get("SUPABASE_DB_URL")!;
  const ref = (Deno.env.get("SUPABASE_URL") || "").match(/^https:\/\/([a-z0-9]+)\./)?.[1];
  for (const host of ["aws-0-us-east-1.pooler.supabase.com", "aws-1-us-east-1.pooler.supabase.com"]) {
    if (!ref) break;
    try {
      const u = new URL(DIRECT); u.username = "postgres." + ref; u.hostname = host; u.port = "6543";
      const c = postgres(u.toString(), { max: 2, idle_timeout: 10, max_lifetime: 300, connect_timeout: 4, prepare: false });
      await c`select 1`;
      return c;
    } catch (_) { /* next */ }
  }
  return postgres(DIRECT, { max: 1, idle_timeout: 10, prepare: false });
}
const sql = await connect();

const NOTIFY_URL = "https://hnzekejoaamsnmtqtwie.supabase.co/functions/v1/billotech-billing/square";
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Access-Control-Allow-Headers": "content-type" };
const j = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { ...CORS, "content-type": "application/json", "cache-control": "no-store" } });

const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
async function sha256(s: string) { return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s))); }
export async function proofHash(email: string, last4: string) { return sha256(email.trim().toLowerCase() + "|" + last4.trim()); }

async function validSignature(raw: string, sig: string | null) {
  const k = Deno.env.get("SQUARE_WEBHOOK_SIGNATURE_KEY") || "";
  if (!k || !sig) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(k), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(NOTIFY_URL + raw));
  const want = btoa(String.fromCharCode(...new Uint8Array(mac)));
  if (want.length !== sig.length) return false;
  let x = 0; for (let i = 0; i < want.length; i++) x |= want.charCodeAt(i) ^ sig.charCodeAt(i);
  return x === 0;
}

const STATUS: Record<string, string> = { ACTIVE: "active", PENDING: "pending", PAUSED: "paused", CANCELED: "canceled", DEACTIVATED: "canceled" };

async function planForVariation(variationId: string | undefined) {
  if (!variationId) return null;
  const [p] = await sql`select id from billotech.plans where square_variation_id = ${variationId}`;
  return p?.id || null;
}

async function onSubscription(s: any) {
  const plan = await planForVariation(s.plan_variation_id);
  if (!plan) return "ignored: not a BilloTech plan";
  const status = STATUS[s.status] || "pending";
  const until = s.charged_through_date ? new Date(s.charged_through_date + "T23:59:59Z") : null;
  const [e] = await sql`insert into billotech.entitlements (plan_id, status, source, square_customer_id, square_subscription_id, current_until)
      values (${plan}, ${status}, 'square', ${s.customer_id || null}, ${s.id}, ${until})
      on conflict (square_subscription_id) do update set plan_id = excluded.plan_id, status = excluded.status,
        square_customer_id = coalesce(excluded.square_customer_id, billotech.entitlements.square_customer_id),
        current_until = coalesce(excluded.current_until, billotech.entitlements.current_until), updated_at = now()
      returning id, square_customer_id`;
  // pick up any payment proofs that arrived before the subscription did
  if (e.square_customer_id) {
    await sql`update billotech.entitlements set proof_hashes = (
        select coalesce(array_agg(distinct h), '{}') from (select unnest(proof_hashes) h from billotech.entitlements where id = ${e.id}
          union select proof_hash from billotech.square_proofs where customer_id = ${e.square_customer_id}) x)
      where id = ${e.id}`;
  }
  return `subscription ${s.id} → ${plan}/${status}`;
}

async function onInvoicePaid(inv: any) {
  if (!inv.subscription_id) return "ignored: not a subscription invoice";
  const email = inv.primary_recipient?.email_address || null;
  const r = await sql`update billotech.entitlements set status = 'active', email = coalesce(${email}, email), updated_at = now()
      where square_subscription_id = ${inv.subscription_id} returning id`;
  return r.length ? `invoice paid for ${inv.subscription_id}` : "invoice for unknown subscription (subscription event not seen yet)";
}

async function onPayment(p: any) {
  const last4 = p.card_details?.card?.last_4, email = p.buyer_email_address, cust = p.customer_id;
  if (!last4 || !email || !cust || !["COMPLETED", "APPROVED"].includes(p.status)) return "ignored payment";
  const h = await proofHash(email, last4);
  await sql`insert into billotech.square_proofs (customer_id, proof_hash) values (${cust}, ${h}) on conflict do nothing`;
  await sql`update billotech.entitlements set proof_hashes = array(select distinct unnest(proof_hashes || ${[h]}::text[])),
      email = coalesce(email, ${email}), updated_at = now() where square_customer_id = ${cust}`;
  await sql`delete from billotech.square_proofs where at < now() - interval '30 days'`;
  return "payment proof stored";
}

// ---------- Square polling (works with no webhook): vault pay_square_access_token, shared with billo-pay ----------
async function sqToken() {
  const [r] = await sql`select decrypted_secret v from vault.decrypted_secrets where name = 'pay_square_access_token'`;
  return (r?.v as string) || "";
}
async function sq(tok: string, method: string, path: string, body?: unknown) {
  const r = await fetch("https://connect.squareup.com" + path, {
    method, headers: { authorization: "Bearer " + tok, "content-type": "application/json", "square-version": "2025-01-23" },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`square ${path.split("?")[0]} ${r.status} ${d?.errors?.[0]?.code || ""}`);
  return d;
}
async function syncSquare(force = false) {
  const tok = await sqToken();
  if (!tok) return { ok: false, need: "vault secret pay_square_access_token (Square production access token)" };
  const [last] = await sql`select value from billotech.config where key = 'last_square_sync'`;
  if (!force && last?.value && Date.now() - Date.parse(last.value) < 60_000) return { ok: true, skipped: "synced under a minute ago" };
  await sql`insert into billotech.config (key, value, public) values ('last_square_sync', ${new Date().toISOString()}, false)
      on conflict (key) do update set value = excluded.value, updated_at = now()`;
  const [loc] = await sql`select value from billotech.config where key = 'square_location_id'`;
  const vars = new Set((await sql`select square_variation_id v from billotech.plans where square_variation_id is not null`).map((r: any) => r.v));
  let cursor: string | undefined, subs = 0;
  do {
    const d = await sq(tok, "POST", "/v2/subscriptions/search", { cursor, limit: 200, query: { filter: { location_ids: [loc?.value || "CF5503WR98TJK"] } } });
    for (const s of d.subscriptions || []) if (vars.has(s.plan_variation_id)) { await onSubscription(s); subs++; }
    cursor = d.cursor;
  } while (cursor);
  const need = await sql`select id, square_customer_id from billotech.entitlements
      where source = 'square' and square_customer_id is not null and (email is null or proof_hashes = '{}') limit 50`;
  for (const e of need) {
    const c = (await sq(tok, "GET", `/v2/customers/${e.square_customer_id}`)).customer || {};
    const cards = (await sq(tok, "GET", `/v2/cards?customer_id=${encodeURIComponent(e.square_customer_id)}`)).cards || [];
    const hashes = c.email_address ? await Promise.all(cards.map((k: any) => proofHash(c.email_address, k.last_4))) : [];
    await sql`update billotech.entitlements set email = coalesce(${c.email_address || null}, email),
        proof_hashes = array(select distinct unnest(proof_hashes || ${hashes}::text[])), updated_at = now() where id = ${e.id}`;
  }
  return { ok: true, subscriptions: subs, filled: need.length };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const path = new URL(req.url).pathname.replace(/^.*\/billotech-billing/, "") || "/";
  try {
    if (path === "/plans" && req.method === "GET") {
      const plans = await sql`select id, name, price_cents, interval, status, tagline, features, checkout_url from billotech.plans order by sort`;
      const cfg = await sql`select key, value from billotech.config where public`;
      return j({ plans, config: Object.fromEntries(cfg.map((r: any) => [r.key, r.value])) });
    }
    if (path === "/sync" && req.method === "POST") return j(await syncSquare(false));
    if (path === "/square" && req.method === "POST") {
      const raw = await req.text();
      if (!(await validSignature(raw, req.headers.get("x-square-hmacsha256-signature")))) return j({ error: "bad signature" }, 401);
      const ev = JSON.parse(raw);
      const seen = await sql`insert into billotech.square_events (event_id, type, object_id, payload)
          values (${ev.event_id}, ${ev.type}, ${ev.data?.id || null}, ${String(ev.type || "").startsWith("payment.") ? null : sql.json(ev)})
          on conflict do nothing returning event_id`;  // payment payloads carry buyer email + card data: never stored
      if (!seen.length) return j({ ok: true, duplicate: true });
      const o = ev.data?.object || {};
      let note = "ignored";
      if (ev.type?.startsWith("subscription.") && o.subscription) note = await onSubscription(o.subscription);
      else if (ev.type === "invoice.payment_made" && o.invoice) note = await onInvoicePaid(o.invoice);
      else if (ev.type?.startsWith("payment.") && o.payment) note = await onPayment(o.payment);
      return j({ ok: true, note });
    }
    return j({ error: "no such route" }, 404);
  } catch (e) {
    console.error(e);
    return j({ error: "server error" }, 500);
  }
});
