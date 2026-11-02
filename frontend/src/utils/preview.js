export const ext = (name) => (name || "").toLowerCase().split(".").pop();
const IMAGE = ["png", "jpg", "jpeg", "gif", "webp", "bmp"];
export const IMAGE_MIME = /^image\/(png|jpe?g|gif|webp|bmp)$/;
const TEXT = ["txt", "csv"];

/** How a document can be shown in the browser, from its type or, failing that, its file name. */
export function previewKind(contentType, filename) {
  const ct = (contentType || "").toLowerCase();
  const e = ext(filename);
  if (ct === "application/pdf" || e === "pdf") return "pdf";
  if (IMAGE_MIME.test(ct) || IMAGE.includes(e)) return "image";
  if (ct.includes("wordprocessingml") || e === "docx") return "docx";
  if (ct === "text/plain" || ct === "text/csv" || TEXT.includes(e)) return "text";
  return null;
}

/** After a Word document is drawn: links keep only web, mail and in-document targets (they open in a new
 *  tab), and nothing that could run or load other content is left in it. */
export function neutralizeDocument(root) {
  root.querySelectorAll("script, iframe, object, embed, frame, frameset, form, base, meta, link").forEach((el) => el.remove());
  root.querySelectorAll("*").forEach((el) => {
    [...el.attributes].forEach((a) => { if (/^on/i.test(a.name)) el.removeAttribute(a.name); });
  });
  root.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) return;
    if (/^(https?:|mailto:)/i.test(href)) { a.setAttribute("target", "_blank"); a.setAttribute("rel", "noopener noreferrer"); }
    else a.removeAttribute("href");
  });
}
