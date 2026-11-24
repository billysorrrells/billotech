//! Drives: browse, stream, download and upload across every drive on the Mac.
//! Roots = home folder + every mounted /Volumes/* (system volumes skipped).
//! Paths are canonicalized and must sit under a root; credential folders are blocked.

use axum::{
    body::Body,
    extract::{Query, Request},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use futures_util::StreamExt;
use serde::Serialize;
use std::{collections::HashMap, path::{Path, PathBuf}};
use tokio::io::{AsyncReadExt, AsyncSeekExt, AsyncWriteExt};
use tokio_util::io::ReaderStream;

const SKIP_VOLUMES: [&str; 3] = ["Preboot", "Recovery", "Macintosh HD"];
const BLOCKED: [&str; 7] = [".ssh", ".gnupg", "Keychains", ".aws", ".netrc", ".token", ".Trashes"];

#[derive(Serialize)]
pub struct Root { name: String, path: String, free_gb: f64, total_gb: f64 }

#[derive(Serialize)]
pub struct Entry { name: String, dir: bool, size: u64, mtime: u64 }

fn home() -> PathBuf { PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| "/".into())) }

fn space(p: &Path) -> (f64, f64) {
    // statvfs via `df -k` keeps us off unsafe code
    let out = std::process::Command::new("df").arg("-k").arg(p).output();
    if let Ok(o) = out {
        let s = String::from_utf8_lossy(&o.stdout);
        if let Some(line) = s.lines().nth(1) {
            let f: Vec<&str> = line.split_whitespace().collect();
            if f.len() > 3 {
                let total = f[1].parse::<f64>().unwrap_or(0.0) / 1048576.0;
                let free = f[3].parse::<f64>().unwrap_or(0.0) / 1048576.0;
                return ((free * 10.0).round() / 10.0, (total * 10.0).round() / 10.0);
            }
        }
    }
    (0.0, 0.0)
}

pub fn roots() -> Vec<Root> {
    let mut v = Vec::new();
    let h = home();
    let (f, t) = space(&h);
    v.push(Root { name: "Mac (home)".into(), path: h.to_string_lossy().into(), free_gb: f, total_gb: t });
    if let Ok(rd) = std::fs::read_dir("/Volumes") {
        for e in rd.flatten() {
            let name = e.file_name().to_string_lossy().to_string();
            if SKIP_VOLUMES.contains(&name.as_str()) || name.starts_with('.') { continue; }
            let p = e.path();
            if std::fs::symlink_metadata(&p).map(|m| m.file_type().is_symlink()).unwrap_or(true) { continue; }
            let (f, t) = space(&p);
            v.push(Root { name, path: p.to_string_lossy().into(), free_gb: f, total_gb: t });
        }
    }
    v
}

/// Canonicalize and make sure the path lives under a root and outside blocked folders.
fn safe(p: &str) -> Result<PathBuf, (StatusCode, String)> {
    let c = std::fs::canonicalize(p).map_err(|_| (StatusCode::NOT_FOUND, "not found".to_string()))?;
    let ok_root = roots().iter().any(|r| {
        std::fs::canonicalize(&r.path).map(|rp| c.starts_with(rp)).unwrap_or(false)
    });
    if !ok_root { return Err((StatusCode::FORBIDDEN, "outside drives".into())); }
    if c.components().any(|x| BLOCKED.contains(&x.as_os_str().to_string_lossy().as_ref())) {
        return Err((StatusCode::FORBIDDEN, "blocked folder".into()));
    }
    Ok(c)
}

pub async fn list_roots() -> Response { Json(roots()).into_response() }

pub async fn list(q: Query<HashMap<String, String>>) -> Response {
    let p = match q.get("p").map(|s| safe(s)) { Some(Ok(p)) => p, Some(Err(e)) => return e.into_response(), None => return (StatusCode::BAD_REQUEST, "p").into_response() };
    let show_hidden = q.get("hidden").is_some();
    let mut out = Vec::new();
    let mut rd = match tokio::fs::read_dir(&p).await { Ok(r) => r, Err(e) => return (StatusCode::FORBIDDEN, e.to_string()).into_response() };
    while let Ok(Some(e)) = rd.next_entry().await {
        let name = e.file_name().to_string_lossy().to_string();
        if !show_hidden && name.starts_with('.') { continue; }
        if BLOCKED.contains(&name.as_str()) { continue; }
        let md = match e.metadata().await { Ok(m) => m, Err(_) => continue };
        let mtime = md.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map(|d| d.as_secs()).unwrap_or(0);
        out.push(Entry { name, dir: md.is_dir(), size: md.len(), mtime });
    }
    out.sort_by(|a, b| b.dir.cmp(&a.dir).then(a.name.to_lowercase().cmp(&b.name.to_lowercase())));
    Json(serde_json::json!({ "path": p.to_string_lossy(), "entries": out })).into_response()
}

/// Stream a file. Supports HTTP Range so iPhone Safari can play video and audio.
pub async fn get_file(q: Query<HashMap<String, String>>, headers: HeaderMap) -> Response {
    let p = match q.get("p").map(|s| safe(s)) { Some(Ok(p)) => p, Some(Err(e)) => return e.into_response(), None => return (StatusCode::BAD_REQUEST, "p").into_response() };
    let mut f = match tokio::fs::File::open(&p).await { Ok(f) => f, Err(e) => return (StatusCode::FORBIDDEN, e.to_string()).into_response() };
    let len = match f.metadata().await { Ok(m) if m.is_file() => m.len(), _ => return (StatusCode::BAD_REQUEST, "not a file").into_response() };
    let mime = mime_guess::from_path(&p).first_or_octet_stream().to_string();
    let fname = p.file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default().replace('"', "");
    let disp = if q.get("dl").is_some() { format!("attachment; filename=\"{fname}\"") } else { format!("inline; filename=\"{fname}\"") };

    let range = headers.get(header::RANGE).and_then(|v| v.to_str().ok()).and_then(|r| r.strip_prefix("bytes="))
        .and_then(|r| { let (a, b) = r.split_once('-')?;
            let (s, e) = if a.is_empty() { let n: u64 = b.parse().ok()?; (len.saturating_sub(n), len - 1) }
                         else { (a.parse().ok()?, if b.is_empty() { len - 1 } else { b.parse::<u64>().ok()?.min(len - 1) }) };
            if s <= e && e < len { Some((s, e)) } else { None } });

    match range {
        Some((s, e)) => {
            if f.seek(std::io::SeekFrom::Start(s)).await.is_err() { return StatusCode::INTERNAL_SERVER_ERROR.into_response(); }
            let n = e - s + 1;
            Response::builder().status(StatusCode::PARTIAL_CONTENT)
                .header(header::CONTENT_TYPE, mime).header(header::CONTENT_DISPOSITION, disp)
                .header(header::ACCEPT_RANGES, "bytes").header(header::CONTENT_LENGTH, n)
                .header(header::CONTENT_RANGE, format!("bytes {s}-{e}/{len}"))
                .body(Body::from_stream(ReaderStream::new(f.take(n)))).unwrap()
        }
        None => Response::builder().status(StatusCode::OK)
            .header(header::CONTENT_TYPE, mime).header(header::CONTENT_DISPOSITION, disp)
            .header(header::ACCEPT_RANGES, "bytes").header(header::CONTENT_LENGTH, len)
            .body(Body::from_stream(ReaderStream::new(f))).unwrap(),
    }
}

/// Upload: POST /drives/up?d=<folder>&name=<file> with the raw file as the body. Never overwrites.
pub async fn upload(q: Query<HashMap<String, String>>, req: Request) -> Response {
    let d = match q.get("d").map(|s| safe(s)) { Some(Ok(p)) => p, Some(Err(e)) => return e.into_response(), None => return (StatusCode::BAD_REQUEST, "d").into_response() };
    if !d.is_dir() { return (StatusCode::BAD_REQUEST, "not a folder").into_response(); }
    let raw = q.get("name").cloned().unwrap_or_else(|| "upload.bin".into());
    let name: String = Path::new(&raw).file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| "upload.bin".into());
    if name.starts_with('.') || BLOCKED.contains(&name.as_str()) { return (StatusCode::BAD_REQUEST, "bad name").into_response(); }
    // never clobber: add " (1)", " (2)"… if taken
    let mut target = d.join(&name);
    let (stem, ext) = match name.rsplit_once('.') { Some((s, e)) => (s.to_string(), format!(".{e}")), None => (name.clone(), String::new()) };
    let mut i = 1;
    while target.exists() { target = d.join(format!("{stem} ({i}){ext}")); i += 1; }
    let tmp = d.join(format!(".billo-upload-{}", std::process::id()));
    let mut f = match tokio::fs::File::create(&tmp).await { Ok(f) => f, Err(e) => return (StatusCode::FORBIDDEN, e.to_string()).into_response() };
    let mut s = req.into_body().into_data_stream();
    let mut total: u64 = 0;
    while let Some(chunk) = s.next().await {
        match chunk {
            Ok(b) => { total += b.len() as u64; if f.write_all(&b).await.is_err() { let _ = tokio::fs::remove_file(&tmp).await; return StatusCode::INSUFFICIENT_STORAGE.into_response(); } }
            Err(_) => { let _ = tokio::fs::remove_file(&tmp).await; return (StatusCode::BAD_REQUEST, "upload cut off").into_response(); }
        }
    }
    let _ = f.flush().await;
    drop(f);
    if tokio::fs::rename(&tmp, &target).await.is_err() { return StatusCode::INTERNAL_SERVER_ERROR.into_response(); }
    Json(serde_json::json!({ "saved": target.to_string_lossy(), "bytes": total })).into_response()
}
