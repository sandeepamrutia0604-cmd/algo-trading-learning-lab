// The Feedback page is static text, a link to the feedback form and a UPI QR code (see index.html). The only
// behaviour is the Copy button for the UPI ID. Nothing here talks to a server: the form link opens in the browser
// when you click it, and that is the only time anything leaves your computer.
import { $, toast } from "../util.js";

export function initFeedback() {
  $("fb-copy").addEventListener("click", async () => {
    const id = $("fb-upi-id").textContent.trim();
    try {
      await navigator.clipboard.writeText(id);
      toast("UPI ID copied");
    } catch (err) {
      const range = document.createRange(); // no clipboard permission: select it so Ctrl+C works
      range.selectNodeContents($("fb-upi-id"));
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      toast("Press Ctrl+C to copy the selected UPI ID");
    }
  });
}
