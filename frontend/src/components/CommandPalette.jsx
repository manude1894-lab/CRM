import React, { useEffect, useRef, useState } from "react";
import { accountsApi, casesApi } from "../api/endpoints";
import { Icon } from "./ui";

export default function CommandPalette({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [clients, setClients] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      setClients([]);
      setCases([]);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setClients([]);
      setCases([]);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const [accRes, caseRes] = await Promise.all([
          accountsApi.list({ search: q.trim(), limit: 6 }),
          casesApi.list({ search: q.trim(), limit: 6 }),
        ]);
        setClients(accRes.items || []);
        setCases(caseRes.items || []);
      } catch {
        setClients([]);
        setCases([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [q, open]);

  const goToClient = (a) => {
    onNavigate({ page: "accounts", accountId: a.id });
    setOpen(false);
  };
  const goToCase = (c) => {
    onNavigate({ page: "cases", caseId: c.id });
    setOpen(false);
  };

  return (
    <>
      <button onClick={() => setOpen(true)}
        className="flex items-center gap-2 text-xs text-gray-400 bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-lg transition-colors">
        <Icon name="search" size={14} />
        <span className="hidden sm:inline">Search…</span>
        <span className="hidden sm:inline text-gray-400 border border-gray-300 rounded px-1 text-[10px]">Ctrl K</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-24" style={{ background: "rgba(0,0,0,0.4)" }} onClick={() => setOpen(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
              <Icon name="search" size={16} className="text-gray-400 flex-shrink-0" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search clients or cases by name or UID…"
                className="flex-1 text-sm outline-none"
              />
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
                <Icon name="close" size={16} />
              </button>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {q.trim().length < 2 && (
                <p className="text-xs text-gray-400 text-center py-8">Type at least 2 characters to search.</p>
              )}
              {q.trim().length >= 2 && !loading && clients.length === 0 && cases.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-8">No matches found.</p>
              )}

              {clients.length > 0 && (
                <div className="py-1.5">
                  <p className="px-4 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Clients</p>
                  {clients.map((a) => (
                    <button key={a.id} onClick={() => goToClient(a)}
                      className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center justify-between">
                      <span className="text-sm text-gray-800">{a.company_name}</span>
                      <span className="text-xs text-gray-400">{a.account_uid}</span>
                    </button>
                  ))}
                </div>
              )}

              {cases.length > 0 && (
                <div className="py-1.5 border-t border-gray-50">
                  <p className="px-4 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Cases</p>
                  {cases.map((c) => (
                    <button key={c.id} onClick={() => goToCase(c)}
                      className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center justify-between">
                      <span className="text-sm text-gray-800">{c.company_name}</span>
                      <span className="text-xs text-gray-400">{c.case_uid}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
