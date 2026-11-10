/* Copyright (c) 2026 Billy Sorrells Entertainment LLC · BilloTech Source License 1.1 (free for personal and school use; paid client work needs BilloTech Pro) · billysorrells.com/billotech/license */
/* BilloCloud — the shared account, plan and save layer for BilloTech apps.
   Save rule: projects live with the person. Save to your device or snap to your own Google Drive;
   small project files can also sync to your BilloTech account. BilloTech never holds your media.
   Google Drive uses the drive.file scope: the app only sees files it created. */
(function () {
  "use strict";
  var FN = "https://hnzekejoaamsnmtqtwie.supabase.co/functions/v1";
  var KEY_LS = "billotech.key", PLAN_LS = "billotech.plan";
  var ls = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} },
  };
  var C = { config: {}, plans: [], plan: { plan: "free" }, account: null, listeners: [] };

  function api(path, opt) {
    opt = opt || {};
    var h = { "content-type": "application/json" }, k = ls.get(KEY_LS);
    if (k) h.authorization = "Bearer " + k;
    return fetch(FN + "/billotech-api" + path, { method: opt.method || "GET", headers: h, body: opt.body ? JSON.stringify(opt.body) : undefined })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || ("HTTP " + r.status)); return d; }); });
  }
  function emit() { C.listeners.forEach(function (f) { try { f(C); } catch (e) {} }); }
  C.on = function (f) { C.listeners.push(f); f(C); };
  C.isPaid = function () { return ["basic", "premium", "schools"].indexOf(C.plan.plan) >= 0; };
  C.key = function () { return ls.get(KEY_LS); };

  C.boot = function () {
    try { var cached = JSON.parse(ls.get(PLAN_LS) || "null"); if (cached) C.plan = cached; } catch (e) {}
    var a = fetch(FN + "/billotech-billing/plans").then(function (r) { return r.json(); }).then(function (d) {
      C.plans = d.plans || []; C.config = d.config || {}; emit();
    }).catch(function () {});
    var b = C.key() ? api("/me").then(function (d) { C.account = d.account; C.plan = d.plan || { plan: "free" }; ls.set(PLAN_LS, JSON.stringify(C.plan)); emit(); })
      .catch(function (e) { if (/bad API key/.test(e.message)) { ls.set(KEY_LS, null); ls.set(PLAN_LS, null); C.plan = { plan: "free" }; C.account = null; emit(); } }) : Promise.resolve();
    return Promise.all([a, b]).then(function () { emit(); return C; });
  };
  C.createAccount = function (handle, email) {
    return api("/accounts", { method: "POST", body: { handle: handle, kind: "human", email: email || undefined } }).then(function (d) {
      ls.set(KEY_LS, d.api_key); C.account = d.account; C.plan = { plan: "free" }; emit(); return d;
    });
  };
  C.useKey = function (k) {
    k = String(k || "").trim(); if (!/^bt_[A-Za-z0-9]+$/.test(k)) return Promise.reject(new Error("That doesn't look like a BilloTech key (starts with bt_)."));
    ls.set(KEY_LS, k); return C.boot();
  };
  C.signOut = function () { ls.set(KEY_LS, null); ls.set(PLAN_LS, null); C.account = null; C.plan = { plan: "free" }; emit(); };
  C.link = function (email, last4) {
    return api("/billing/link", { method: "POST", body: { email: email, last4: last4 } }).then(function (d) {
      C.plan = d.plan; ls.set(PLAN_LS, JSON.stringify(C.plan)); emit(); return d;
    });
  };
  C.usage = function (kind, qty, app) { if (C.key()) api("/usage", { method: "POST", body: { kind: kind, qty: qty || 1, app: app } }).catch(function () {}); };

  // ---------- save: device ----------
  C.saveDevice = function (name, blobOrText, type) {
    var blob = blobOrText instanceof Blob ? blobOrText : new Blob([blobOrText], { type: type || "application/json" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
    return Promise.resolve({ where: "device", name: name });
  };
  // ---------- save: BilloTech account (small project files) ----------
  C.saveCloud = function (app, title, body, id) {
    if (!C.key()) return Promise.reject(new Error("Make a free BilloTech account first."));
    return id ? api("/docs/" + id, { method: "PUT", body: { title: title, body: body } }) : api("/docs", { method: "POST", body: { app: app, title: title, body: body } });
  };
  C.listCloud = function (app) { return api("/docs?app=" + encodeURIComponent(app)); };
  C.loadCloud = function (id) { return api("/docs/" + id); };

  // ---------- save: Google Drive (drive.file) ----------
  var gToken = null, gExp = 0, gisReady = null;
  function loadGis() {
    if (gisReady) return gisReady;
    gisReady = new Promise(function (res, rej) {
      var s = document.createElement("script"); s.src = "https://accounts.google.com/gsi/client"; s.async = true;
      s.onload = res; s.onerror = function () { gisReady = null; rej(new Error("Couldn't reach Google sign-in. Check the connection, or save to your device.")); };
      document.head.appendChild(s);
    });
    return gisReady;
  }
  C.driveReady = function () { return !!(C.config && C.config.google_client_id); };
  function driveToken() {
    if (gToken && Date.now() < gExp - 60000) return Promise.resolve(gToken);
    if (!C.driveReady()) return Promise.reject(new Error("Google Drive saving is switching on soon. Save to your device for now."));
    return loadGis().then(function () {
      return new Promise(function (res, rej) {
        var tc = google.accounts.oauth2.initTokenClient({
          client_id: C.config.google_client_id, scope: "https://www.googleapis.com/auth/drive.file",
          callback: function (r) { if (r.error) return rej(new Error("Google said: " + r.error)); gToken = r.access_token; gExp = Date.now() + (r.expires_in || 3600) * 1000; res(gToken); },
          error_callback: function (e) { rej(new Error(e && e.type === "popup_closed" ? "Google sign-in was closed." : "Google sign-in didn't finish.")); },
        });
        tc.requestAccessToken();
      });
    });
  }
  function gapi(path, opt) {
    return driveToken().then(function (tok) {
      opt = opt || {}; opt.headers = Object.assign({ authorization: "Bearer " + tok }, opt.headers || {});
      return fetch("https://www.googleapis.com" + path, opt).then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error((d.error && d.error.message) || ("Drive HTTP " + r.status)); return d; }); });
    });
  }
  function driveFolder(app) {
    var q = encodeURIComponent("name='BilloTech' and mimeType='application/vnd.google-apps.folder' and trashed=false");
    return gapi("/drive/v3/files?q=" + q + "&fields=files(id)").then(function (d) {
      if (d.files && d.files.length) return d.files[0].id;
      return gapi("/drive/v3/files?fields=id", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "BilloTech", mimeType: "application/vnd.google-apps.folder" }) }).then(function (f) { return f.id; });
    });
  }
  C.saveDrive = function (name, blobOrText, type, existingId) {
    var blob = blobOrText instanceof Blob ? blobOrText : new Blob([blobOrText], { type: type || "application/json" });
    return driveFolder().then(function (folder) {
      var meta = existingId ? { name: name } : { name: name, parents: [folder] };
      var boundary = "billo" + Math.random().toString(36).slice(2);
      var body = new Blob(["--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + JSON.stringify(meta) + "\r\n--" + boundary + "\r\nContent-Type: " + (blob.type || "application/octet-stream") + "\r\n\r\n", blob, "\r\n--" + boundary + "--"]);
      var path = existingId ? "/upload/drive/v3/files/" + existingId + "?uploadType=multipart&fields=id,name,webViewLink" : "/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink";
      return gapi(path, { method: existingId ? "PATCH" : "POST", headers: { "content-type": "multipart/related; boundary=" + boundary }, body: body });
    }).then(function (f) { return { where: "drive", id: f.id, name: f.name, link: f.webViewLink }; });
  };
  C.listDrive = function (suffix) {
    var q = encodeURIComponent("trashed=false and name contains '" + (suffix || ".billo") + "'");
    return gapi("/drive/v3/files?q=" + q + "&orderBy=modifiedTime desc&pageSize=50&fields=files(id,name,modifiedTime,webViewLink)");
  };
  C.loadDrive = function (id) {
    return driveToken().then(function (tok) { return fetch("https://www.googleapis.com/drive/v3/files/" + id + "?alt=media", { headers: { authorization: "Bearer " + tok } }).then(function (r) { if (!r.ok) throw new Error("Drive HTTP " + r.status); return r.text(); }); });
  };
  window.BilloCloud = C;
})();
