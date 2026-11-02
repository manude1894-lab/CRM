export const ext = (name) => (name || "").toLowerCase().split(".").pop();
const IMAGE = ["png", "jpg", "jpeg", "gif", "webp", "bmp"];
const TEXT = ["txt", "csv"];

/** How a document can be shown in the browser, from its type or, failing that, its file name. */
export function previewKind(contentType, filename) {
  const ct = (contentType || "").toLowerCase();
  const e = ext(filename);
  if (ct === "application/pdf" || e === "pdf") return "pdf";
  if (/^image\/(png|jpe?g|gif|webp|bmp)$/.test(ct) || IMAGE.includes(e)) return "image";
  if (ct.includes("wordprocessingml") || e === "docx") return "docx";
  if (ct === "text/plain" || ct === "text/csv" || TEXT.includes(e)) return "text";
  return null;
}
