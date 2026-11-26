import React, { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

/**
 * Review 22-11-2026 (package 5): a row of the client form's sections, kept at the top while scrolling. Each
 * section shows whether mandatory fields are still missing there (from the completeness check) or its last save
 * failed; a click opens the section and scrolls to it.
 */
export const SectionIndexContext = createContext(null);

// The completeness check names some sections differently from the form.
const ALIASES = { "client info": "Client info", "triam assignment": "Client info", "profile status & engagement": "Engagement",
  "documents": "documents", "tax": "tax" };
const norm = (s) => String(s || "").toLowerCase().trim();

export function sectionFor(serverSection, titles) {
  const want = norm(ALIASES[norm(serverSection)] || serverSection);
  return titles.find((t) => norm(t) === want)
    || titles.find((t) => norm(t).startsWith(want) || want.startsWith(norm(t)) || norm(t).endsWith(want))
    || (want === "tax" ? titles.find((t) => norm(t) === "financial year") : undefined)
    || null;
}

export function SectionIndexProvider({ children }) {
  const [sections, setSections] = useState([]); // [{ title, el, open, failed }]
  const register = useCallback((entry) => {
    setSections((list) => [...list.filter((s) => s.title !== entry.title), entry]);
    return () => setSections((list) => list.filter((s) => s.el !== entry.el));
  }, []);
  const value = useMemo(() => ({ sections, register }), [sections, register]);
  return <SectionIndexContext.Provider value={value}>{children}</SectionIndexContext.Provider>;
}

/** Used by a form section: registers its title, element and a way to open it. */
export function useSectionIndex(title, ref, open, failed) {
  const ctx = useContext(SectionIndexContext);
  const register = ctx?.register;
  const openRef = useRef(open);
  openRef.current = open;
  useEffect(() => {
    if (!register || !ref.current) return undefined;
    return register({ title, el: ref.current, open: () => openRef.current(), failed: !!failed });
  }, [register, title, failed]);
}

export default function SectionIndex({ missing = [], topRef, jumpToFirst = false }) {
  const ctx = useContext(SectionIndexContext);
  // Triam UAT 25-11-2026 row 186: reopening a client being prepared, go to the first missing mandatory field.
  const jumped = useRef(false);
  useEffect(() => {
    if (!jumpToFirst || jumped.current || !missing.length || !ctx?.sections.length) return;
    jumped.current = true;
    const titles = ["Client info", ...ctx.sections.map((s) => s.title)];
    const first = sectionFor(missing[0].section, titles);
    const section = ctx.sections.find((s) => s.title === first);
    if (section) section.open();
    setTimeout(() => {
      const root = topRef?.current?.closest("[class*='overflow']") || document;
      const field = (section?.el || root).querySelector("[data-invalid='true']") || root.querySelector("[data-invalid='true']");
      const target = field || section?.el || topRef?.current;
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
      field?.querySelector("input, select, textarea, button")?.focus({ preventScroll: true });
    }, 250);
  }, [jumpToFirst, missing, ctx?.sections.length]);
  // Stick to the very top of whatever scrolls the form (the pop-up, or the page with its padding).
  const navRef = useRef(null);
  const [top, setTop] = useState(0);
  useLayoutEffect(() => {
    let el = navRef.current?.parentElement;
    while (el && !/(auto|scroll)/.test(getComputedStyle(el).overflowY)) el = el.parentElement;
    if (el) setTop(-parseFloat(getComputedStyle(el).paddingTop || "0"));
  });
  if (!ctx) return null;
  // In the order the sections appear on the form.
  const sections = [...ctx.sections].filter((s) => s.el?.isConnected)
    .sort((a, b) => (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  if (sections.length < 2) return null;
  const titles = ["Client info", ...sections.map((s) => s.title)];
  const counts = {};
  missing.forEach((m) => { const t = sectionFor(m.section, titles); if (t) counts[t] = (counts[t] || 0) + 1; });

  const jump = (s) => {
    if (s) s.open();
    const el = s ? s.el : topRef?.current;
    setTimeout(() => el?.scrollIntoView({ behavior: "smooth", block: "start" }), 30);
  };
  const chip = (title, s) => {
    const n = counts[title] || 0;
    const bad = s?.failed;
    const look = bad ? "border-red-300 bg-red-50 text-red-700" : n ? "border-amber-300 bg-amber-50 text-amber-800"
      : "border-gray-200 bg-white text-gray-700 hover:border-brand-300";
    const what = bad ? "last save failed" : n ? `${n} mandatory field${n !== 1 ? "s" : ""} missing` : "";
    return (
      <button key={title} type="button" onClick={() => jump(s)} title={what || undefined}
        aria-label={what ? `${title}: ${what}` : title}
        className={`flex-shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium transition-colors ${look}`}>
        {title}
        {bad ? <span aria-hidden="true">!</span> : n ? <span aria-hidden="true" className="min-w-[16px] h-4 px-1 rounded-full bg-amber-500 text-white text-[10px] leading-4 text-center">{n}</span> : null}
      </button>
    );
  };
  return (
    <nav ref={navRef} style={{ top }} aria-label="Form sections" className="sticky z-10 -mx-6 px-6 py-2 bg-white/95 backdrop-blur border-b border-gray-100">
      <div className="flex gap-1.5 overflow-x-auto pb-0.5">
        {chip("Client info", null)}
        {sections.map((s) => chip(s.title, s))}
      </div>
    </nav>
  );
}
