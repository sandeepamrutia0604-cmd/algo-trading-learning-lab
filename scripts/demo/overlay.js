// Injected into the page while recording (see record.mjs): captions, title cards, a gliding mouse
// cursor with click ripples, and highlight boxes. Nothing here is part of the app itself.
(() => {
  if (window.__demo) return;

  const style = document.createElement("style");
  style.textContent = `
    html, html * { cursor: none !important; }
    #demo-caption { position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%) translateY(18px);
      max-width: 80%; padding: 13px 26px; border-radius: 14px; background: rgba(8, 12, 20, 0.93); color: #fff;
      font: 600 22px/1.38 "Segoe UI", system-ui, sans-serif; text-align: center; border: 1px solid rgba(255, 255, 255, 0.14);
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5); opacity: 0; transition: opacity 0.35s, transform 0.35s;
      z-index: 2147483000; pointer-events: none; }
    #demo-caption.on { opacity: 1; transform: translateX(-50%) translateY(0); }
    #demo-caption.top { bottom: auto; top: 96px; transform: translateX(-50%) translateY(-18px); }
    #demo-caption.top.on { transform: translateX(-50%) translateY(0); }
    #demo-caption small { display: block; margin-top: 4px; font-size: 16px; font-weight: 400; opacity: 0.82; }
    #demo-card { position: fixed; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 16px; padding: 40px; background: radial-gradient(ellipse at 50% 40%, #17253f, #070b13 72%); color: #fff;
      font-family: "Segoe UI", system-ui, sans-serif; text-align: center; opacity: 0; transition: opacity 0.7s;
      z-index: 2147483500; pointer-events: none; }
    #demo-card.on { opacity: 1; }
    #demo-card h1 { margin: 0; font-size: 54px; letter-spacing: 0.4px; }
    #demo-card p { margin: 0; max-width: 900px; font-size: 24px; line-height: 1.45; opacity: 0.88; }
    #demo-card .foot { margin-top: 14px; font-size: 18px; opacity: 0.62; }
    #demo-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 2147483600; pointer-events: none;
      transform: translate(640px, 700px); transition: transform 0.7s cubic-bezier(0.3, 0.1, 0.2, 1);
      filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.65)); }
    #demo-ripple { position: fixed; left: 0; top: 0; width: 16px; height: 16px; margin: -8px 0 0 -8px; border-radius: 50%;
      border: 3px solid #4c8dff; z-index: 2147483550; pointer-events: none; opacity: 0; }
    #demo-ripple.go { animation: demoRipple 0.55s ease-out; }
    @keyframes demoRipple { from { opacity: 0.95; transform: scale(0.4); } to { opacity: 0; transform: scale(4.2); } }
    .demo-spot { position: fixed; border: 3px solid #f5a524; border-radius: 10px; box-shadow: 0 0 20px 3px rgba(245, 165, 36, 0.6);
      z-index: 2147483400; pointer-events: none; opacity: 0; transition: opacity 0.3s; }
    .demo-spot.on { opacity: 1; }
  `;
  document.head.append(style);

  const make = (tag, id, html = "") => {
    const el = document.createElement(tag);
    if (id) el.id = id;
    el.innerHTML = html;
    document.body.append(el);
    return el;
  };
  const caption = make("div", "demo-caption");
  const card = make("div", "demo-card");
  const cursor = make(
    "div",
    "demo-cursor",
    `<svg viewBox="0 0 24 24"><path d="M3 2l7 18 2.6-7.4L20 10z" fill="#fff" stroke="#000" stroke-width="1.4" stroke-linejoin="round"/></svg>`,
  );
  const ripple = make("div", "demo-ripple");
  let spots = [];

  window.__demo = {
    caption(html, top = false) {
      caption.classList.toggle("top", top);
      caption.innerHTML = html;
      caption.classList.add("on");
    },
    clearCaption() {
      caption.classList.remove("on");
    },
    card(title, sub, foot) {
      card.innerHTML = `<h1>${title}</h1><p>${sub}</p>${foot ? `<div class="foot">${foot}</div>` : ""}`;
      card.classList.add("on");
    },
    clearCard() {
      card.classList.remove("on");
    },
    moveTo(x, y) {
      cursor.style.transform = `translate(${x - 3}px, ${y - 2}px)`;
    },
    click(x, y) {
      ripple.style.left = `${x}px`;
      ripple.style.top = `${y}px`;
      ripple.classList.remove("go");
      void ripple.offsetWidth; // restart the animation
      ripple.classList.add("go");
    },
    spot(rect) {
      const box = document.createElement("div");
      box.className = "demo-spot";
      Object.assign(box.style, { left: `${rect.x - 6}px`, top: `${rect.y - 6}px`, width: `${rect.w + 12}px`, height: `${rect.h + 12}px` });
      document.body.append(box);
      requestAnimationFrame(() => box.classList.add("on"));
      spots.push(box);
    },
    clearSpots() {
      spots.forEach((box) => {
        box.classList.remove("on");
        setTimeout(() => box.remove(), 350);
      });
      spots = [];
    },
  };
})();
