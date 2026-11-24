// Saves a file the server sent, under the name the server gave it (Content-Disposition), e.g.
// "triam-call-report-ACT-0036-acme-ltd-20261124.pdf"; `fallback` only if the server named none.
export function fileNameOf(headers, fallback) {
  const cd = headers?.["content-disposition"] || "";
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (star) return decodeURIComponent(star[1]);
  return /filename="?([^";]+)"?/i.exec(cd)?.[1] || fallback;
}

export function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const saveResponse = (res, fallback) => saveBlob(res.data, fileNameOf(res.headers, fallback));
