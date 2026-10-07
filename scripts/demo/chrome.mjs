// A tiny driver for recording the app in Chrome, with no packages to install: it starts Chrome
// with a separate throwaway profile (your own Chrome and its logins are never touched), talks to
// it over the DevTools protocol (Node's built-in WebSocket), and records the page with Chrome's own
// recorder, saving a .webm that YouTube accepts.
//
// Used by scripts/demo/record.mjs. Needs Node 22+ and Chrome or Edge.

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const BROWSERS = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

export function findBrowser() {
  const found = BROWSERS.find((path) => existsSync(path));
  if (!found) throw new Error("Couldn't find Chrome or Edge. Install one, or set CHROME_PATH.");
  return process.env.CHROME_PATH || found;
}

export class Browser {
  /** Start Chrome on `url` in an app-style window `width` x `height` (the page area, not the window frame). */
  static async launch(url, { width = 1600, height = 900, port = 9333 } = {}) {
    const profile = mkdtempSync(join(tmpdir(), "algo-demo-profile-"));
    const child = spawn(
      findBrowser(),
      [
        `--user-data-dir=${profile}`,
        `--remote-debugging-port=${port}`,
        `--app=${url}`,
        `--window-size=${width},${height + 40}`,
        "--window-position=0,0",
        "--auto-accept-this-tab-capture",
        "--autoplay-policy=no-user-gesture-required",
        "--force-device-scale-factor=1",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--disable-infobars",
        // Keep the page rendering at full speed even when other windows sit on top of it.
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
        "--disable-features=Translate,MediaRouter,CalculateNativeWinOcclusion",
      ],
      { stdio: "ignore", detached: false },
    );
    const browser = new Browser(child, profile, port, { width, height });
    await browser.connect();
    return browser;
  }

  constructor(child, profile, port, size) {
    Object.assign(this, { child, profile, port, size, nextId: 1, pending: new Map(), upload: null });
  }

  async connect() {
    let target;
    for (let i = 0; i < 60 && !target; i++) {
      try {
        const list = await (await fetch(`http://127.0.0.1:${this.port}/json/list`)).json();
        target = list.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      } catch {
        // Chrome is still starting
      }
      if (!target) await sleep(250);
    }
    if (!target) throw new Error("Chrome didn't start in time.");
    this.socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      this.socket.onopen = resolve;
      this.socket.onerror = reject;
    });
    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const waiter = message.id && this.pending.get(message.id);
      if (!waiter) return;
      this.pending.delete(message.id);
      if (message.error) waiter.reject(new Error(`${waiter.method}: ${message.error.message}`));
      else waiter.resolve(message.result);
    };
    await this.send("Page.enable");
    await this.send("Runtime.enable");
    await this.fitWindow();
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  /** Run JavaScript in the page and return its value. */
  async eval(expression) {
    const { result, exceptionDetails } = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || exceptionDetails.text);
    return result.value;
  }

  /** Make the page area exactly the requested size, whatever the window frame takes up. */
  async fitWindow() {
    const { windowId } = await this.send("Browser.getWindowForTarget");
    for (let i = 0; i < 4; i++) {
      const { w, h } = await this.eval("({ w: innerWidth, h: innerHeight })");
      if (w === this.size.width && h === this.size.height) return;
      const { bounds } = await this.send("Browser.getWindowBounds", { windowId });
      await this.send("Browser.setWindowBounds", {
        windowId,
        bounds: { width: bounds.width + this.size.width - w, height: bounds.height + this.size.height - h },
      });
      await sleep(300);
    }
  }

  async waitFor(condition, { timeout = 20000, what = condition } = {}) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if (await this.eval(`Boolean(${condition})`)) return;
      await sleep(150);
    }
    throw new Error(`Timed out waiting for: ${what}`);
  }

  async screenshot(path) {
    const { data } = await this.send("Page.captureScreenshot", { format: "png" });
    writeFileSync(path, Buffer.from(data, "base64"));
  }

  /** Get ready to mix narration into the recording: clips are loaded with loadAudio() and played with playAudio().
   *  They go only into the recording, not to your speakers. Call this before startRecording(). */
  async prepareAudio() {
    await this.eval(`(async () => {
      const ctx = new AudioContext();
      await ctx.resume();
      const dest = ctx.createMediaStreamDestination();
      // Chrome records nothing while no sound is playing, so the audio would run ahead of the picture
      // by the length of every silent gap. A constant, inaudible tone (a 30 Hz hum at about -66 dB)
      // keeps the audio stream flowing so the narration stays in step with the video.
      const hum = ctx.createOscillator();
      const quiet = ctx.createGain();
      hum.frequency.value = 30;
      quiet.gain.value = 0.0005;
      hum.connect(quiet);
      quiet.connect(dest);
      hum.start();
      window.__audio = {
        ctx,
        dest,
        clips: {},
        async load(key, base64) {
          const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
          this.clips[key] = await ctx.decodeAudioData(bytes.buffer);
        },
        // Returns the state the audio engine was in; anything but "running" means it had been suspended.
        async play(key) {
          const was = ctx.state;
          if (was !== "running") await ctx.resume();
          const source = ctx.createBufferSource();
          source.buffer = this.clips[key];
          source.connect(dest);
          source.start();
          return was;
        },
      };
      return true;
    })()`);
  }

  async loadAudio(key, wav) {
    await this.eval(`__audio.load(${JSON.stringify(key)}, ${JSON.stringify(wav.toString("base64"))})`);
  }

  async playAudio(key) {
    return this.eval(`__audio.play(${JSON.stringify(key)})`);
  }

  /** Start recording the page. The video is saved to `path` by stopRecording(). */
  async startRecording(path) {
    mkdirSync(join(path, ".."), { recursive: true });
    this.videoPath = path;
    this.upload = new Promise((resolve) => {
      this.uploadServer = createServer((req, res) => {
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.setHeader("Access-Control-Allow-Headers", "*");
        if (req.method === "OPTIONS") return res.end();
        const chunks = [];
        req.on("data", (c) => chunks.push(c));
        req.on("end", () => {
          writeFileSync(path, Buffer.concat(chunks));
          res.end("ok");
          resolve(path);
        });
      }).listen(this.port + 111, "127.0.0.1");
    });
    await this.eval(`(async () => {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 30 }, audio: false, preferCurrentTab: true });
      const voice = window.__audio ? window.__audio.dest.stream.getAudioTracks() : [];
      const stream = new MediaStream([...display.getVideoTracks(), ...voice]);
      const wanted = voice.length ? "video/webm;codecs=vp9,opus" : "video/webm;codecs=vp9";
      const mime = MediaRecorder.isTypeSupported(wanted) ? wanted : "video/webm";
      const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8000000, audioBitsPerSecond: 128000 });
      window.__rec = { chunks: [], recorder, stream: display };
      recorder.ondataavailable = (e) => e.data.size && window.__rec.chunks.push(e.data);
      recorder.start(1000);
      return true;
    })()`);
  }

  async stopRecording() {
    await this.eval(`(async () => {
      const { recorder, chunks, stream } = window.__rec;
      await new Promise((resolve) => { recorder.onstop = resolve; recorder.stop(); });
      stream.getTracks().forEach((t) => t.stop());
      await fetch("http://127.0.0.1:${this.port + 111}/video", { method: "POST", body: new Blob(chunks, { type: "video/webm" }) });
      return true;
    })()`);
    const path = await this.upload;
    this.uploadServer.close();
    return path;
  }

  async close() {
    try {
      await this.send("Browser.close");
    } catch {
      // already gone
    }
    this.child.kill();
    await sleep(500);
    try {
      rmSync(this.profile, { recursive: true, force: true });
    } catch {
      // Chrome may still be releasing the profile folder; the system temp cleanup gets it later
    }
  }
}
