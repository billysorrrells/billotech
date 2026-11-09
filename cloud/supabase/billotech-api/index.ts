// billotech-api — BilloTech public toolkit backend (BILLO BINDER). v10: plans, Square subscription linking, usage, Edit Forge app.
// Accounts for humans and agents (API-key auth), and save/load for every BilloTech app.
// Keys are shown once and stored only as SHA-256 hashes. DB access via SUPABASE_DB_URL (server-side only).
import postgres from "npm:postgres@3.4.5";

// Connect through the Supavisor transaction pooler (BILLO BINDER has only 60 direct connections; idle direct
// connections from several functions filled it on 19 Oct). Same password as SUPABASE_DB_URL, user postgres.<ref>.
// Falls back to a single direct connection if the pooler can't be reached.
async function connect() {
  const DIRECT = Deno.env.get("SUPABASE_DB_URL")!;
  const ref = (Deno.env.get("SUPABASE_URL") || "").match(/^https:\/\/([a-z0-9]+)\./)?.[1];
  for (const host of ["aws-0-us-east-1.pooler.supabase.com", "aws-1-us-east-1.pooler.supabase.com"]) {
    if (!ref) break;
    try {
      const u = new URL(DIRECT); u.username = "postgres." + ref; u.hostname = host; u.port = "6543";
      const c = postgres(u.toString(), { max: 3, idle_timeout: 10, max_lifetime: 300, connect_timeout: 4, prepare: false });
      await c`select 1`;
      return c;
    } catch (_) { /* try the next host */ }
  }
  return postgres(DIRECT, { max: 1, idle_timeout: 10, prepare: false });
}
const sql = await connect();

const APPS = new Set([
  "draft", "analysis", "budget", "plot", "dispatch",
  "photo", "light", "vector", "layout", "cut", "motion", "sound",
  "write", "grid", "deck", "pdf", "frame", "cad", "notes", "laugh", "drop", "direct", "director", "live", "clip", "mail", "voice", "forge",
]);
const REQ_APPS = new Set([...APPS, "nle-bridge", "hardware-lab", "audio-hub", "binder", "the-door", "agent-access-mcp", "os", "hub"]);
const MAX_BYTES = 2_000_000;
const MAX_DOCS = 1000;
const MAX_NEW_ACCOUNTS_PER_IP_DAY = 25;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
  "Access-Control-Allow-Headers": "authorization,content-type,x-billo-key",
  "Access-Control-Max-Age": "86400",
};
const j = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { ...CORS, "content-type": "application/json" } });
const err = (status: number, message: string) => j({ error: message }, status);

async function sha256(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function newKey() {
  const b = crypto.getRandomValues(new Uint8Array(24));
  return "bt_" + btoa(String.fromCharCode(...b)).replace(/[+/=]/g, (c) => ({ "+": "A", "/": "z", "=": "" }[c]!));
}
function keyFrom(req: Request) {
  const h = req.headers.get("authorization") || "";
  const m = h.match(/^Bearer\s+(bt_[A-Za-z0-9]+)$/);
  return m ? m[1] : (req.headers.get("x-billo-key") || "").trim() || null;
}
async function who(req: Request) {
  const k = keyFrom(req);
  if (!k) return null;
  const [a] = await sql`select id, handle, kind from billotech.accounts where key_hash = ${await sha256(k)} and not disabled`;
  if (a) await sql`update billotech.accounts set last_seen = now() where id = ${a.id}`;
  return a || null;
}
const RANK: Record<string, number> = { free: 0, schools: 2, basic: 2, premium: 3 };
async function planOf(accountId: string) {
  const rows = await sql`select plan_id, status, current_until, source, org from billotech.entitlements
    where account_id = ${accountId} and (status = 'active' or (status in ('canceled','paused','past_due') and current_until > now()))`;
  rows.sort((a: any, b: any) => (RANK[b.plan_id] ?? 0) - (RANK[a.plan_id] ?? 0));
  const e = rows[0];
  return e ? { plan: e.plan_id, status: e.status, until: e.current_until, source: e.source, org: e.org } : { plan: "free", status: "active", until: null, source: null, org: null };
}
const clean = (s: unknown, n: number) => String(s ?? "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, n);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const url = new URL(req.url);
  const path = url.pathname.replace(/^.*\/billotech-api/, "") || "/";
  try {
    // ---------- public ----------
    if (path === "/" && req.method === "GET") {
      return j({
        name: "BilloTech API", apps: [...APPS],
        endpoints: {
          "POST /accounts": "create an account {handle, kind:'human'|'agent', email?, agent_client?} -> {api_key} (shown once)",
          "GET /me": "who am I + my plan (Bearer key)", "GET /plans": "BilloTech plans and prices",
          "GET /plan": "my plan (Bearer key)", "POST /billing/link": "attach a Square subscription {email,last4} (Bearer key)",
          "GET /docs?app=": "list my documents",
          "POST /docs": "save a new document {app,title,body}",
          "GET /docs/:id": "load one", "PUT /docs/:id": "update {title?,body?}", "DELETE /docs/:id": "delete",
          "POST /requests": "request a feature {app,title,body?,priority?:now|next|later,audio_b64?,audio_type?,audio_secs?} — key optional",
          "GET /requests?app=": "my feature requests with status and Billy's reply (Bearer key)",
          "GET /requests/status?ids=": "status of requests by id (guests)", "GET /requests/shipped?app=": "what shipped from requests",
          "GET|PUT /prefs/:app": "my knobs for an app (Bearer key)", "GET /funds?state=&kind=&q=": "film incentives and grants",
        },
        auth: "Authorization: Bearer bt_…",
      });
    }
    if (path === "/plans" && req.method === "GET") {
      const plans = await sql`select id, name, price_cents, interval, status, tagline, features, checkout_url from billotech.plans order by sort`;
      return j({ plans });
    }
    // incentives + grants (BILLO BINDER fund_programs), public research data
    if (path === "/funds" && req.method === "GET") {
      const st = clean(url.searchParams.get("state") || "", 40), kind = clean(url.searchParams.get("kind") || "", 30), q = clean(url.searchParams.get("q") || "", 60);
      const rows = await sql`select kind, jurisdiction, funder, program, audience, amount, cap, min_spend, cycle, url, verified_at, confidence, notes
        from public.fund_programs
        where (${st} = '' or jurisdiction ilike ${st} or jurisdiction = 'National')
          and (${kind} = '' or kind = ${kind})
          and (${q} = '' or concat_ws(' ', funder, program, audience, notes) ilike ${"%" + q + "%"})
        order by (jurisdiction = ${st}) desc, kind, jurisdiction, funder limit 120`;
      return j({ programs: rows });
    }
    // what got shipped from requests — public changelog per app
    if (path === "/requests/shipped" && req.method === "GET") {
      const app = clean(url.searchParams.get("app") || "", 31);
      const rows = await sql`select id, room, title, shipped_note, shipped_at from public.bse_dev_requests
        where room like 'billotech-%' and status = 'shipped' and (${app} = '' or room = ${"billotech-" + app})
        order by shipped_at desc nulls last limit 50`;
      const [{ open }] = await sql`select count(*)::int open from public.bse_dev_requests where room like 'billotech-%' and status in ('new','building') and (${app} = '' or room = ${"billotech-" + app})`;
      return j({ shipped: rows.map((r: any) => ({ ...r, app: String(r.room).replace("billotech-", "") })), open });
    }
    // guests check their own requests by id (uuids they were handed back)
    if (path === "/requests/status" && req.method === "GET") {
      const ids = (url.searchParams.get("ids") || "").split(",").filter((x) => /^[0-9a-f-]{36}$/.test(x)).slice(0, 50);
      if (!ids.length) return j({ requests: [] });
      const rows = await sql`select id, room, title, body, priority, status, shipped_note, shipped_at, reply_at, created_at, audio_secs
        from public.bse_dev_requests where id = any(${ids}::uuid[]) and room like 'billotech-%'`;
      return j({ requests: rows });
    }
    if (path === "/requests" && req.method === "POST") {
      const b = await req.json().catch(() => null);
      if (!b) return err(400, "JSON body required");
      const app = clean(b.app, 31);
      if (!REQ_APPS.has(app)) return err(400, "unknown app");
      const title = clean(b.title, 160), body = clean(b.body, 4000).replace(/ {2,}/g, " ");
      if (title.length < 3 && !b.audio_b64) return err(400, "say what you need (3+ characters) or leave a voice note");
      const priority = ["now", "next", "later"].includes(b.priority) ? b.priority : "next";
      const meA = await who(req);
      const ip = req.headers.get("x-forwarded-for")?.split(",")[0].trim() || "0";
      const ipHash = await sha256("billotech-req:" + ip);
      const [{ n }] = await sql`select count(*)::int n from public.bse_dev_requests where source = ${"billotech:" + ipHash.slice(0, 16)} and created_at > now() - interval '1 day'`;
      if (n >= 30) return err(429, "that's a lot of requests from one place today — try tomorrow");
      let audioPath: string | null = null, audioSecs: number | null = null;
      if (b.audio_b64) {
        const bytes = Uint8Array.from(atob(String(b.audio_b64)), (c) => c.charCodeAt(0));
        if (bytes.length > 3_000_000) return err(413, "voice note too long (about 2 minutes max)");
        const ct = /^audio\/[a-z0-9.+-]+$/.test(b.audio_type || "") ? b.audio_type : "audio/webm";
        audioPath = `billotech/${app}/${crypto.randomUUID()}.${ct.includes("mp4") ? "m4a" : ct.includes("ogg") ? "ogg" : "webm"}`;
        const up = await fetch(`${Deno.env.get("SUPABASE_URL")}/storage/v1/object/desk-voice/${audioPath}`, {
          method: "POST", headers: { authorization: "Bearer " + Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"), "content-type": ct, "x-upsert": "false" }, body: bytes });
        if (!up.ok) return err(502, "voice note didn't upload");
        audioSecs = Math.min(600, Math.max(0, Number(b.audio_secs) || 0));
      }
      const who_ = meA ? `bt:${meA.id} ${meA.handle}` : "bt:guest " + clean(b.name || "guest", 60);
      const [r] = await sql`insert into public.bse_dev_requests (room, area, title, body, priority, status, requested_by, source, audio_path, audio_secs, seat)
        values (${"billotech-" + app}, 'site', ${title || "Voice note"}, ${body}, ${priority}, 'new', ${who_}, ${"billotech:" + ipHash.slice(0, 16)}, ${audioPath}, ${audioSecs}, ${meA ? meA.kind : "guest"})
        returning id, room, title, priority, status, created_at`;
      if (meA) await sql`insert into billotech.events (account_id, action, app) values (${meA.id}, 'request.create', ${app})`;
      return j({ request: r, note: "It's on Billy's build list. Check back here for the status and his reply." }, 201);
    }
    if (path === "/accounts" && req.method === "POST") {
      const b = await req.json().catch(() => ({}));
      const handle = clean(b.handle, 60);
      if (handle.length < 2) return err(400, "handle (2-60 chars) is required");
      const kind = b.kind === "human" ? "human" : "agent";
      const email = b.email ? clean(b.email, 200) : null;
      if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return err(400, "email looks wrong");
      const ip = req.headers.get("x-forwarded-for")?.split(",")[0].trim() || "0";
      const ipHash = await sha256("billotech:" + ip);
      const [{ n }] = await sql`select count(*)::int n from billotech.accounts where ip_hash = ${ipHash} and created_at > now() - interval '1 day'`;
      if (n >= MAX_NEW_ACCOUNTS_PER_IP_DAY) return err(429, "too many new accounts from this address today");
      const key = newKey();
      const [a] = await sql`insert into billotech.accounts (handle, kind, email, agent_client, key_hash, key_prefix, ip_hash)
        values (${handle}, ${kind}, ${email}, ${b.agent_client ? clean(b.agent_client, 80) : null}, ${await sha256(key)}, ${key.slice(0, 8)}, ${ipHash})
        returning id, handle, kind, created_at`;
      await sql`insert into billotech.events (account_id, action) values (${a.id}, 'account.create')`;
      return j({ account: a, api_key: key, note: "Save this key now. It is shown once. Send it as: Authorization: Bearer <key>" }, 201);
    }

    // ---------- authed ----------
    const me = await who(req);
    if (!me) return err(401, "missing or bad API key — create one with POST /accounts");

    if (path === "/me" && req.method === "GET") {
      const [{ docs }] = await sql`select count(*)::int docs from billotech.docs where account_id = ${me.id}`;
      return j({ account: me, docs, plan: await planOf(me.id) });
    }
    if (path === "/plan" && req.method === "GET") return j(await planOf(me.id));
    if (path === "/billing/link" && req.method === "POST") {
      // Attach a Square subscription to this account: the email used at checkout + the card's last 4 digits.
      const b = await req.json().catch(() => ({}));
      const email = clean(b.email, 200).toLowerCase(), last4 = clean(b.last4, 4);
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !/^\d{4}$/.test(last4)) return err(400, "enter the email you paid with and the last 4 digits of that card");
      const [{ n }] = await sql`select count(*)::int n from billotech.link_attempts where account_id = ${me.id} and not ok and at > now() - interval '1 hour'`;
      if (n >= 8) return err(429, "too many tries — wait an hour, or email support");
      await fetch(`${Deno.env.get("SUPABASE_URL")}/functions/v1/billotech-billing/sync`, { method: "POST", signal: AbortSignal.timeout(25000) }).catch(() => null);
      const h = await sha256(email + "|" + last4);
      const [e] = await sql`update billotech.entitlements set account_id = ${me.id}, updated_at = now()
        where id = (select id from billotech.entitlements where ${h} = any(proof_hashes) and (account_id is null or account_id = ${me.id})
                    order by created_at desc limit 1) returning plan_id, status`;
      await sql`insert into billotech.link_attempts (account_id, ok) values (${me.id}, ${!!e})`;
      if (!e) return err(404, "no subscription found for that email and card yet — if you just paid, give it a minute and try again");
      await sql`insert into billotech.events (account_id, action) values (${me.id}, 'plan.link')`;
      return j({ linked: true, plan: await planOf(me.id) });
    }
    if (path === "/usage" && req.method === "POST") {
      const b = await req.json().catch(() => ({}));
      const kind = clean(b.kind, 40), app = clean(b.app, 31);
      if (!/^[a-z][a-z0-9_.-]{1,39}$/.test(kind)) return err(400, "kind required");
      await sql`insert into billotech.usage (account_id, kind, qty, app) values (${me.id}, ${kind}, ${Math.min(10000, Math.max(0, Number(b.qty) || 1))}, ${app || null})`;
      return j({ ok: true });
    }
    if (path === "/requests" && req.method === "GET") {
      const app = clean(url.searchParams.get("app") || "", 31);
      const rows = await sql`select id, room, title, body, priority, status, shipped_note, shipped_at, reply_at, created_at, audio_secs
        from public.bse_dev_requests where requested_by like ${"bt:" + me.id + " %"} and (${app} = '' or room = ${"billotech-" + app})
        order by created_at desc limit 100`;
      return j({ requests: rows });
    }
    const pm = path.match(/^\/prefs\/([a-z][a-z0-9-]{1,30})$/);
    if (pm) {
      if (req.method === "GET") {
        const [r] = await sql`select prefs, updated_at from billotech.prefs where account_id = ${me.id} and app = ${pm[1]}`;
        return j({ app: pm[1], prefs: r ? r.prefs : {}, updated_at: r ? r.updated_at : null });
      }
      if (req.method === "PUT") {
        const b = await req.json().catch(() => null);
        if (!b || typeof b.prefs !== "object") return err(400, "{prefs:{…}} required");
        if (JSON.stringify(b.prefs).length > 64_000) return err(413, "knobs too large");
        const [r] = await sql`insert into billotech.prefs (account_id, app, prefs) values (${me.id}, ${pm[1]}, ${sql.json(b.prefs)})
          on conflict (account_id, app) do update set prefs = excluded.prefs, updated_at = now() returning prefs, updated_at`;
        return j({ app: pm[1], prefs: r.prefs, updated_at: r.updated_at });
      }
    }
    if (path === "/docs" && req.method === "GET") {
      const app = url.searchParams.get("app");
      if (app && !APPS.has(app)) return err(400, "unknown app");
      const rows = app
        ? await sql`select id, app, title, bytes, created_at, updated_at from billotech.docs where account_id = ${me.id} and app = ${app} order by updated_at desc limit 200`
        : await sql`select id, app, title, bytes, created_at, updated_at from billotech.docs where account_id = ${me.id} order by updated_at desc limit 200`;
      return j({ docs: rows });
    }
    if (path === "/docs" && req.method === "POST") {
      const b = await req.json().catch(() => null);
      if (!b) return err(400, "JSON body required");
      const app = clean(b.app, 31);
      if (!APPS.has(app)) return err(400, "app must be one of: " + [...APPS].join(", "));
      const title = clean(b.title || "Untitled", 200) || "Untitled";
      const body = b.body ?? {};
      const bytes = new TextEncoder().encode(JSON.stringify(body)).length;
      if (bytes > MAX_BYTES) return err(413, "document too large (2 MB max)");
      const [{ n }] = await sql`select count(*)::int n from billotech.docs where account_id = ${me.id}`;
      if (n >= MAX_DOCS) return err(409, "document limit reached (1000)");
      const [d] = await sql`insert into billotech.docs (account_id, app, title, body, bytes)
        values (${me.id}, ${app}, ${title}, ${sql.json(body)}, ${bytes}) returning id, app, title, bytes, created_at, updated_at`;
      await sql`insert into billotech.events (account_id, action, app, doc_id) values (${me.id}, 'doc.create', ${app}, ${d.id})`;
      return j({ doc: d }, 201);
    }
    const m = path.match(/^\/docs\/([0-9a-f-]{36})$/);
    if (m) {
      const id = m[1];
      const [d] = await sql`select id, app, title, body, bytes, created_at, updated_at from billotech.docs where id = ${id} and account_id = ${me.id}`;
      if (!d) return err(404, "not found");
      if (req.method === "GET") return j({ doc: d });
      if (req.method === "DELETE") {
        await sql`delete from billotech.docs where id = ${id} and account_id = ${me.id}`;
        await sql`insert into billotech.events (account_id, action, app, doc_id) values (${me.id}, 'doc.delete', ${d.app}, ${id})`;
        return j({ deleted: id });
      }
      if (req.method === "PUT") {
        const b = await req.json().catch(() => null);
        if (!b) return err(400, "JSON body required");
        const title = b.title !== undefined ? clean(b.title, 200) || d.title : d.title;
        const body = b.body !== undefined ? b.body : d.body;
        const bytes = new TextEncoder().encode(JSON.stringify(body)).length;
        if (bytes > MAX_BYTES) return err(413, "document too large (2 MB max)");
        const [u] = await sql`update billotech.docs set title = ${title}, body = ${sql.json(body)}, bytes = ${bytes}, updated_at = now()
          where id = ${id} and account_id = ${me.id} returning id, app, title, bytes, created_at, updated_at`;
        await sql`insert into billotech.events (account_id, action, app, doc_id) values (${me.id}, 'doc.update', ${d.app}, ${id})`;
        return j({ doc: u });
      }
    }
    return err(404, "no such route");
  } catch (e) {
    console.error(e);
    return err(500, "server error");
  }
});
