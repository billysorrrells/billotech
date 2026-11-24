//! Billo Remote — drive the Billo Browser on Billy's Mac from any phone.
//! Streams the main display as JPEG frames and sends taps, typing, keys and scroll back.
//! Locked by a random token in the URL. Binds 127.0.0.1 only; expose with `tailscale funnel`.
//!
//!   billo_remote [port]            (default 8651)   prints the token on start
//!   BILLO_REMOTE_TOKEN=... to pin a token

use axum::{
    extract::{Query, State},
    http::{header, StatusCode},
    response::{Html, IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use core_graphics::display::CGDisplay;
use enigo::{Axis, Button, Coordinate, Direction, Enigo, Key, Keyboard, Mouse, Settings};
use rand::{distributions::Alphanumeric, Rng};
use serde::Deserialize;
use std::{collections::HashMap, io::Cursor, sync::{mpsc, Arc}, thread};

#[derive(Clone)]
struct App {
    token: Arc<String>,
    input: mpsc::Sender<Input>,
}

#[derive(Deserialize, Debug)]
#[serde(tag = "t", rename_all = "lowercase")]
enum Input {
    Click { x: f64, y: f64 },
    Dbl { x: f64, y: f64 },
    Text { s: String },
    Key { k: String },
    Scroll { dy: i32 },
    Front,
}

fn authed(app: &App, q: &HashMap<String, String>) -> bool {
    q.get("k").map(|k| k == app.token.as_str()).unwrap_or(false)
}

async fn page(State(app): State<App>, Query(q): Query<HashMap<String, String>>) -> Response {
    if !authed(&app, &q) {
        return (StatusCode::FORBIDDEN, "locked").into_response();
    }
    Html(include_str!("viewer.html").replace("__TOKEN__", app.token.as_str())).into_response()
}

async fn frame(State(app): State<App>, Query(q): Query<HashMap<String, String>>) -> Response {
    if !authed(&app, &q) {
        return (StatusCode::FORBIDDEN, "locked").into_response();
    }
    let w: u32 = q.get("w").and_then(|v| v.parse().ok()).unwrap_or(1280).clamp(480, 2400);
    let jpg = tokio::task::spawn_blocking(move || -> Result<Vec<u8>, String> {
        let mons = xcap::Monitor::all().map_err(|e| e.to_string())?;
        let mon = mons.first().ok_or("no display")?;
        let img = mon.capture_image().map_err(|e| e.to_string())?;
        let h = (img.height() as f64 * w as f64 / img.width() as f64) as u32;
        let small = image::imageops::resize(&img, w, h, image::imageops::FilterType::Triangle);
        let rgb = image::DynamicImage::ImageRgba8(small).to_rgb8();
        let mut out = Cursor::new(Vec::new());
        image::codecs::jpeg::JpegEncoder::new_with_quality(&mut out, 70)
            .encode_image(&rgb)
            .map_err(|e| e.to_string())?;
        Ok(out.into_inner())
    })
    .await;
    match jpg {
        Ok(Ok(b)) => ([(header::CONTENT_TYPE, "image/jpeg"), (header::CACHE_CONTROL, "no-store")], b).into_response(),
        Ok(Err(e)) => (StatusCode::INTERNAL_SERVER_ERROR, e).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

async fn input(State(app): State<App>, Query(q): Query<HashMap<String, String>>, Json(i): Json<Input>) -> Response {
    if !authed(&app, &q) {
        return (StatusCode::FORBIDDEN, "locked").into_response();
    }
    let _ = app.input.send(i);
    (StatusCode::OK, "ok").into_response()
}

fn key_of(k: &str) -> Option<Key> {
    Some(match k {
        "enter" => Key::Return,
        "tab" => Key::Tab,
        "backspace" => Key::Backspace,
        "escape" => Key::Escape,
        "up" => Key::UpArrow,
        "down" => Key::DownArrow,
        "left" => Key::LeftArrow,
        "right" => Key::RightArrow,
        _ => return None,
    })
}

/// Enigo is not Send on macOS, so all input runs on one thread.
fn input_thread(rx: mpsc::Receiver<Input>) {
    let mut en = Enigo::new(&Settings::default()).expect("enigo (needs Accessibility permission)");
    for i in rx {
        // normalized 0..1 -> display points (CoreGraphics main display bounds are in points)
        let b = CGDisplay::main().bounds();
        let to_pt = |x: f64, y: f64| ((x * b.size.width) as i32, (y * b.size.height) as i32);
        match i {
            Input::Click { x, y } => {
                let (px, py) = to_pt(x, y);
                let _ = en.move_mouse(px, py, Coordinate::Abs);
                let _ = en.button(Button::Left, Direction::Click);
            }
            Input::Dbl { x, y } => {
                let (px, py) = to_pt(x, y);
                let _ = en.move_mouse(px, py, Coordinate::Abs);
                let _ = en.button(Button::Left, Direction::Click);
                let _ = en.button(Button::Left, Direction::Click);
            }
            Input::Text { s } => {
                let _ = en.text(&s);
            }
            Input::Key { k } => {
                if let Some(key) = key_of(&k) {
                    let _ = en.key(key, Direction::Click);
                }
            }
            Input::Scroll { dy } => {
                let _ = en.scroll(dy, Axis::Vertical);
            }
            Input::Front => {
                let _ = std::process::Command::new("osascript")
                    .args(["-e", r#"tell application "System Events" to set frontmost of (first process whose name contains "Playwright" or name contains "billo_browser" or name contains "Billo") to true"#])
                    .status();
            }
        }
    }
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::args().nth(1).and_then(|p| p.parse().ok()).unwrap_or(8651);
    let token = std::env::var("BILLO_REMOTE_TOKEN").unwrap_or_else(|_| {
        rand::thread_rng().sample_iter(&Alphanumeric).take(24).map(char::from).collect()
    });
    let (tx, rx) = mpsc::channel::<Input>();
    thread::spawn(move || input_thread(rx));
    let app = App { token: Arc::new(token.clone()), input: tx };
    let r = Router::new()
        .route("/", get(page))
        .route("/frame", get(frame))
        .route("/input", post(input))
        .with_state(app);
    let addr = format!("127.0.0.1:{port}");
    println!("billo_remote on http://{addr}/?k={token}");
    let l = tokio::net::TcpListener::bind(&addr).await.expect("bind");
    axum::serve(l, r).await.unwrap();
}
