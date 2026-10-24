import React, { useEffect, useState } from "react";
import { accountsApi } from "../api/endpoints";
import { Badge, Button, Embedded, ErrorBanner, FactList, PageHeader, Panel, Spinner, Tabs } from "../components/ui";
import AccountFormModal from "../components/accounts/AccountFormModal";
import AccountPartyModal from "../components/AccountPartyModal";
import ClientDocumentsFolder from "../components/accounts/ClientDocumentsFolder";
import ClientServicingModal from "../components/accounts/ClientServicingModal";
import AccountHistoryModal from "../components/accounts/AccountHistoryModal";
import WorkflowBar from "../components/accounts/WorkflowBar";
import CompletenessChecklist from "../components/accounts/CompletenessChecklist";
import { accountToForm } from "../components/accounts/accountForm";
import { useAuthStore } from "../store/auth";
import { toast } from "../store/toast";
import { fmtDate } from "../utils/constants";
import { fmtFYE } from "../utils/fye";

const yesNo = (v) => (v === true ? "Yes" : v === false ? "No" : null);
const list = (v) => (Array.isArray(v) && v.length ? v.join(", ") : null);

/**
 * One client on its own page: header with status and actions, then tabs for everything about the
 * client. The tabs reuse the existing screens (profile form, parties, documents, servicing, history).
 */
export default function ClientProfilePage({ accountId, initialTab = "overview", users, countries, onBack, onChanged, backLabel = "Clients" }) {
  const [account, setAccount] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState(initialTab);
  const [version, setVersion] = useState(0); // remounts the tabs after a status change or save
  const [wfVersion, setWfVersion] = useState(0); // reloads the status bar after a profile save (e.g. the CDD section)
  const [tabStart, setTabStart] = useState(null); // "request" opens a new service request on the Reports & Requests tab
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const readOnly = useAuthStore((s) => !s.isAdmin() && (s.user?.permissions || []).includes("read_only"));

  const load = () => accountsApi.get(accountId).then((a) => { setAccount(a); setError(null); })
    .catch((e) => setError(e.response?.data?.detail || "Failed to load the client"));
  useEffect(() => { load(); }, [accountId]);
  const refresh = () => { load(); setVersion((v) => v + 1); onChanged?.(); };

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!account) return <Spinner />;

  const a = account;
  const userName = (id) => users.find((u) => u.id === id)?.name || null;
  const individual = a.account_type === "Individual";
  const onboarding = ["New", "WIP"].includes(a.profile_status);
  const existing = ["Approved", "Active", "Inactive", "Marked for Exit", "Exited"].includes(a.profile_status);
  const [servicingStart, setServicingStart] = [tabStart, setTabStart];

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "profile", label: "Profile" },
    { key: "parties", label: individual ? "Joint Holders" : "Shareholders & Directors" },
    { key: "documents", label: "Documents" },
    { key: "servicing", label: "Reports & Requests" },
    { key: "history", label: "History" },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        back={{ label: backLabel, onClick: onBack }}
        title={a.company_name}
        subtitle={[a.client_id || `Temporary ID ${a.temp_id || a.account_uid}`, individual ? "Individual" : "Corporate", a.anchor_entity, userName(a.spoc_id) && `Anchor RM: ${userName(a.spoc_id)}`].filter(Boolean).join(" · ")}
        actions={!readOnly && <>
          {["Approved", "Active"].includes(a.profile_status) && (
            <Button onClick={() => { setServicingStart("request"); setTab("servicing"); }}>New service request</Button>
          )}
          <Button onClick={() => setTab("profile")}>Edit profile</Button>
        </>}
      />
      <div className="flex flex-wrap gap-1.5 items-center">
        {/* BRD §11: existing relationships show status + date + Risk Level + Next AML Review on top. */}
        {existing && a.next_aml_review_date && (
          <span className={`text-[11px] px-2 py-0.5 rounded ${new Date(a.next_aml_review_date) < new Date() ? "bg-red-50 text-red-700" : "bg-gray-100 text-gray-600"}`}>
            Next AML review {fmtDate(a.next_aml_review_date)}
          </span>
        )}
        {a.risk_rating && <Badge text={`${a.risk_rating} Risk`} />}
        {a.is_pep && <Badge text="PEP" />}
        {(a.tags || "").split(",").map((t) => t.trim()).filter(Boolean).map((t) => <Badge key={t} text={t} />)}
      </div>

      {/* Status, approval actions and review history — the same on every tab. */}
      <WorkflowBar key={`wf-${version}-${wfVersion}`} accountId={a.id} onChanged={refresh} />

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      <div key={`${tab}-${version}`}>
        {tab === "overview" && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {onboarding && <div className="xl:col-span-2"><CompletenessChecklist accountId={a.id} /></div>}
            <Panel title={individual ? "Individual" : "Company"}>
              <FactList items={individual ? [
                ["Date of birth", fmtDate(a.date_of_birth)], ["Nationality", a.nationality], ["Country of birth", a.country_of_birth],
                ["Country of residence", a.country_of_residence], ["Passport expiry", fmtDate(a.passport_expiry_date)],
                ["Email", a.individual_email], ["Profession / business", a.nature_of_business],
              ] : [
                ["Unique search name", a.search_name], ["New client category", a.client_category], ["Country of incorporation", a.country],
                ["Contact", [a.contact_mobile_country_code && a.contact_mobile_number ? `${a.contact_mobile_country_code} ${a.contact_mobile_number}` : null, a.contact_email].filter(Boolean).join(" · ") || null],
                ["LEI", a.lei_number ? `${a.lei_number}${a.lei_expiry_date ? ` (expires ${fmtDate(a.lei_expiry_date)})` : ""}` : null],
                ["Incorporation date", fmtDate(a.incorporation_date)], ["Incorporation cert. no.", a.registration_number],
              ]} />
            </Panel>
            <Panel title="Triam assignment">
              <FactList items={[
                ["Anchor entity", a.anchor_entity], ["Non-anchor entities", list(a.non_anchor_entities)],
                ["Anchor RM", userName(a.spoc_id)], ["Non-anchor RMs", list((a.non_anchor_rm_ids || []).map(userName).filter(Boolean))],
                ["Services", list(a.services_obtained)], ["Nature of services sought", list(a.nature_of_services_sought)],
                ["One-time service", yesNo(a.is_one_time_service)],
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
                ["CDD/AML risk level", a.risk_rating], ["Reason for EDD", a.edd_reason], ["KYC verified by", a.kyc_verified_by],
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
                hideWorkflow hideDocuments onClose={refresh} onChanged={() => { load(); setWfVersion((v) => v + 1); onChanged?.(); }} />
            </Embedded>
          </Panel>
        )}
        {tab === "parties" && <Panel><Embedded><AccountPartyModal account={a} onClose={refresh} /></Embedded></Panel>}
        {tab === "documents" && <Panel><ClientDocumentsFolder accountId={a.id} onboarding={onboarding} /></Panel>}
        {tab === "servicing" && <Panel><Embedded><ClientServicingModal account={a} startWith={servicingStart} onClose={() => {}} /></Embedded></Panel>}
        {tab === "history" && <Panel><Embedded><AccountHistoryModal account={a} onClose={() => {}} /></Embedded></Panel>}
      </div>

    </div>
  );
}
