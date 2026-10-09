import React, { useEffect, useState } from "react";
import { auditApi } from "../../api/endpoints";
import { Modal } from "../ui";
import AuditTrail from "../AuditTrail";
import { toast } from "../../store/toast";

// BRD §13 — "the change remains visible in the audit trail": a client's full history
// (its own fields, parties and documents), newest first.
export default function AccountHistoryModal({ account, onClose }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auditApi.forAccount(account.id)
      .then((r) => setEntries(r.items))
      .catch((e) => toast.error(e.response?.data?.detail || "Failed to load history"))
      .finally(() => setLoading(false));
  }, [account.id]);

  return (
    <Modal title={`History — ${account.company_name}`} onClose={onClose}>
      <div className="max-h-[60vh] overflow-y-auto pr-1">
        <AuditTrail entries={entries} loading={loading} emptyText="No changes recorded yet." />
      </div>
    </Modal>
  );
}
