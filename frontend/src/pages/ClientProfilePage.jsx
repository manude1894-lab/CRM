import React, { useEffect, useState } from "react";
import { accountsApi } from "../api/endpoints";
import { Badge, Button, Embedded, ErrorBanner, FactList, MoreMenu, PageHeader, Panel, Spinner, Tabs, EmptyState } from "../components/ui";
import AccountFormModal from "../components/accounts/AccountFormModal";
import AccountPartyModal from "../components/AccountPartyModal";
import ClientDocumentsFolder from "../components/accounts/ClientDocumentsFolder";
import ClientServicingModal from "../components/accounts/ClientServicingModal";
import AccountHistoryModal from "../components/accounts/AccountHistoryModal";
import TrackRecordModal from "../components/TrackRecordModal";
import WorkflowBar from "../components/accounts/WorkflowBar";
import CompletenessChecklist from "../components/accounts/CompletenessChecklist";
import { accountToForm } from "../components/accounts/accountForm";
import { useAuthStore } from "../store/auth";
import { confirmDialog } from "../store/confirm";
import { toast } from "../store/toast";
import { fmt, fmtDate } from "../utils/constants";
import { fmtFYE } from "../utils/fye";

const yesNo = (v) => (v === true ? "Yes" : v === false ? "No" : null);
const list = (v) => (Array.isArray(v) && v.length ? v.join(", ") : null);

/**
 * One client on its own page: header with status and actions, then tabs for everything about the
 * client. The tabs reuse the existing screens (profile form, parties, documents, servicing, history).
 */
export default function ClientProfilePage({ accountId, initialTab = "overview", users, countries, cases, onBack, onChanged, onOpenCase }) {
  const [account, setAccount] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState(initialTab);
  const [version, setVersion] = useState(0); // remounts the tabs after a status change or save
  const [trackRecord, setTrackRecord] = useState(false);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  const load = () => accountsApi.get(accountId).then((a) => { setAccount(a); setError(null); })
    .catch((e) => setError(e.response?.data?.detail || "Failed to load the client"));
  useEffect(() => { load(); }, [accountId]);
  const refresh = () => { load(); setVersion((v) => v + 1); onChanged?.(); };

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!account) return <Spinner />;

  const a = account;
  const userName = (id) => users.find((u) => u.id === id)?.name || null;
  const clientCases = cases.filter((c) => c.account_id === a.id);
  const individual = a.account_type === "Individual";
  const onboarding = ["New", "WIP"].includes(a.profile_status);

  const remove = async () => {
    if (!(await confirmDialog(`Delete ${a.company_name}? This cannot be undone.`))) return;
    try { await accountsApi.delete(a.id); onChanged?.(); onBack(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to delete client"); }
  };

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "profile", label: "Profile" },
    ...(individual ? [] : [{ key: "parties", label: "Shareholders & Directors" }]),
    { key: "documents", label: "Documents" },
    { key: "servicing", label: "Reports & Requests" },
    { key: "cases", label: "Cases", count: clientCases.length },
    { key: "history", label: "History" },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        back={{ label: "Clients", onClick: onBack }}
        title={a.company_name}
        subtitle={[a.client_id, individual ? "Individual" : "Corporate", a.anchor_entity, userName(a.spoc_id) && `Anchor RM: ${userName(a.spoc_id)}`].filter(Boolean).join(" · ")}
        actions={<>
          <Button onClick={() => setTab("profile")}>Edit profile</Button>
          <MoreMenu items={[
            { label: "Track record", onClick: () => setTrackRecord(true) },
            { label: "Delete client", onClick: remove, danger: true, hidden: !isAdmin },
          ]} />
        </>}
      />
      <div className="flex flex-wrap gap-1.5">
        {a.risk_rating && <Badge text={`${a.risk_rating} Risk`} />}
        {a.aml_classification && <Badge text={a.aml_classification} />}
        {a.is_pep && <Badge text="PEP" />}
        {(a.tags || "").split(",").map((t) => t.trim()).filter(Boolean).map((t) => <Badge key={t} text={t} />)}
      </div>

      {/* Status, approval actions and review history — the same on every tab. */}
      <WorkflowBar key={`wf-${version}`} accountId={a.id} onChanged={refresh} />

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      <div key={`${tab}-${version}`}>
        {tab === "overview" && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {onboarding && <div className="xl:col-span-2"><CompletenessChecklist accountId={a.id} /></div>}
            <Panel title={individual ? "Individual" : "Company"}>
              <FactList items={individual ? [
                ["Date of birth", fmtDate(a.date_of_birth)], ["Nationality", a.nationality], ["Country of birth", a.country_of_birth],
                ["Country of residence", a.country_of_residence], ["Passport expiry", fmtDate(a.passport_expiry_date)],
                ["Occupation", a.occupation], ["Email", a.individual_email],
              ] : [
                ["Unique search name", a.search_name], ["Industry", a.industry], ["Country of incorporation", a.country],
                ["Incorporation date", fmtDate(a.incorporation_date)], ["Incorporation cert. no.", a.registration_number],
                ["Website", a.website], ["Key contacts", a.key_contacts],
              ]} />
            </Panel>
            <Panel title="Triam assignment">
              <FactList items={[
                ["Anchor entity", a.anchor_entity], ["Non-anchor entities", list(a.non_anchor_entities)],
                ["Anchor RM", userName(a.spoc_id)], ["Non-anchor RMs", list((a.non_anchor_rm_ids || []).map(userName).filter(Boolean))],
                ["Services", list(a.services_obtained)], ["Invoiced to date", fmt(a.total_invoiced_amount)],
              ]} />
            </Panel>
            {!individual && (
              <Panel title="Licensing & regulatory">
                <FactList items={[
                  ["Licensing authority", a.licensing_authority === "Other" ? a.licensing_authority_other : a.licensing_authority],
                  ["Licence number", a.license_number], ["Licence valid", a.license_start_date ? `${fmtDate(a.license_start_date)} – ${fmtDate(a.license_expiry_date)}` : null],
                  ["Regulated", yesNo(a.is_regulated)],
                  ...(a.is_regulated ? [["Regulator", a.regulator_name === "Other" ? a.regulator_other : a.regulator_name],
                    ["Regulatory licence expiry", fmtDate(a.regulatory_license_expiry_date)]] : []),
                ]} />
              </Panel>
            )}
            <Panel title="KYC / AML">
              <FactList items={[
                ["Risk level", a.risk_rating], ["AML classification", a.aml_classification], ["KYC verified by", a.kyc_verified_by],
                ["CDD completed", fmtDate(a.cdd_completion_date)], ["Next AML review", fmtDate(a.next_aml_review_date)], ["PEP", a.is_pep ? "Yes" : "No"],
              ]} />
            </Panel>
            {!individual && (
              <Panel title="Tax & engagement">
                <FactList items={[
                  ["TRN / VAT", a.trn_vat_number], ["Financial year end", a.financial_year_end ? fmtFYE(a.financial_year_end) : null],
                  ["Corporate tax registered", yesNo(a.corp_tax_registered)], ["Corp tax no.", a.corp_tax_registration_number],
                  ["Engagement letter", a.engagement_letter_signed ? `Signed, valid until ${fmtDate(a.engagement_letter_valid_until) || "—"}` : "Not signed"],
                ]} />
              </Panel>
            )}
          </div>
        )}

        {tab === "profile" && (
          <Panel>
            <Embedded>
              <AccountFormModal initialForm={accountToForm(a)} users={users} countries={countries}
                hideWorkflow hideDocuments onClose={refresh} onChanged={() => { load(); onChanged?.(); }} />
            </Embedded>
          </Panel>
        )}
        {tab === "parties" && <Panel><Embedded><AccountPartyModal account={a} onClose={refresh} /></Embedded></Panel>}
        {tab === "documents" && <Panel><ClientDocumentsFolder accountId={a.id} onboarding={onboarding} /></Panel>}
        {tab === "servicing" && <Panel><Embedded><ClientServicingModal account={a} cases={cases} onClose={() => {}} /></Embedded></Panel>}
        {tab === "history" && <Panel><Embedded><AccountHistoryModal account={a} onClose={() => {}} /></Embedded></Panel>}
        {tab === "cases" && (clientCases.length === 0
          ? <EmptyState title="No cases for this client yet" text="Create one from the Cases page and link it to this client." />
          : (
            <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                  <th className="text-left py-2.5 px-4 font-semibold">Case</th><th className="text-left py-2.5 px-4 font-semibold">Company</th>
                  <th className="text-left py-2.5 px-4 font-semibold">Route</th><th className="text-left py-2.5 px-4 font-semibold">Stage</th>
                  <th className="text-left py-2.5 px-4 font-semibold">Compliance</th><th className="text-right py-2.5 px-4 font-semibold">Invoice</th>
                </tr></thead>
                <tbody>
                  {clientCases.map((c) => (
                    <tr key={c.id} onClick={() => onOpenCase?.(c.id)} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer">
                      <td className="py-2.5 px-4 font-mono text-xs">{c.case_uid}</td>
                      <td className="py-2.5 px-4">{c.company_name}</td>
                      <td className="py-2.5 px-4 text-xs text-gray-500">{c.engagement_route}</td>
                      <td className="py-2.5 px-4"><Badge text={c.stage} /></td>
                      <td className="py-2.5 px-4 text-xs text-gray-500">{c.compliance_status}</td>
                      <td className="py-2.5 px-4 text-right">{fmt(c.invoice_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
      </div>

      {trackRecord && <TrackRecordModal account={a} onClose={() => setTrackRecord(false)} />}
    </div>
  );
}
