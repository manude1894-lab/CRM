import React, { useEffect, useId, useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { PASSWORD_HINT, passwordProblem } from "../components/ChangePasswordModal";
import { IDLE_MINUTES } from "../components/IdleSignOut";

// Opened in a new tab from another of the person's logins: that login's email is handed over through
// local storage (read once, within a minute) so it never appears in the address bar.
const handedOverEmail = (() => {
  try {
    const raw = localStorage.getItem("triam-switch");
    localStorage.removeItem("triam-switch");
    const { email, at } = JSON.parse(raw || "{}");
    return email && Date.now() - at < 60000 ? email : "";
  } catch { return ""; }
})();

// "Remember my email": only the email is kept on this device. The login itself stays per tab (store/auth.js).
const REMEMBER_KEY = "triam-remember-email";
const rememberedEmail = (() => { try { return localStorage.getItem(REMEMBER_KEY) || ""; } catch { return ""; } })();

// The emailed reset link (/reset-password?token=…): the token is read once and taken out of the address bar.
let resetToken = (() => {
  if (window.location.pathname !== "/reset-password") return "";
  const token = new URLSearchParams(window.location.search).get("token") || "";
  window.history.replaceState(null, "", "/");
  return token;
})();

// Why the person is on the sign-in page, said once: inactivity (IdleSignOut) or an expired session (api/client.js).
const takeNotice = () => {
  try {
    const idle = sessionStorage.getItem("triam-idle-signout");
    const expired = sessionStorage.getItem("triam-session-expired");
    if (idle) return `For your security, you were signed out after ${IDLE_MINUTES} minutes without activity.`;
    if (expired) return "Your session has expired. Please sign in again.";
  } catch { /* storage unavailable */ }
  return "";
};

// Footer links, set on the server at run time (docker-entrypoint.sh); a link not set isn't shown.
const site = (typeof window !== "undefined" && window.__SITE__) || {};
const VERSION = [typeof __APP_VERSION__ !== "undefined" ? `v${__APP_VERSION__}` : "", (site.build || "").slice(0, 7)]
  .filter(Boolean).join(" · ");

const EMAIL_RE = /^\S+@\S+\.\S+$/;

// ── Small pieces, one style for every field, button and message on the page ─────────────────────────────────
const Svg = ({ children, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);
const MailIcon = () => <Svg><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6.5 8.5 6 8.5-6" /></Svg>;
const LockIcon = () => <Svg><rect x="4.5" y="10.5" width="15" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></Svg>;
const EyeIcon = ({ off }) => (
  <Svg>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" />
    {off && <path d="M4 4l16 16" />}
  </Svg>
);
const InfoIcon = () => <Svg size={16}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></Svg>;
const AlertIcon = () => <Svg size={16}><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5h.01" /></Svg>;
const CheckIcon = () => <Svg size={16}><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.5 2.5 4.5-5" /></Svg>;

const TONES = {
  error: { box: "bg-red-50 border-red-200 text-red-700", icon: <AlertIcon />, role: "alert" },
  info: { box: "bg-brand-50 border-brand-100 text-brand-700", icon: <InfoIcon />, role: "status" },
  success: { box: "bg-emerald-50 border-emerald-200 text-emerald-700", icon: <CheckIcon />, role: "status" },
};
const Message = ({ tone, children }) => {
  const t = TONES[tone];
  return (
    <div role={t.role} className={`login-fade flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm ${t.box}`}>
      <span className="mt-0.5 flex-shrink-0">{t.icon}</span><span>{children}</span>
    </div>
  );
};

// A labelled field with a leading icon, an optional control on the right and its own error under it.
function TextField({ label, icon, error, aside, trailing, hint, ...input }) {
  const id = useId();
  const described = [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label htmlFor={id} className="text-sm font-medium text-gray-700">{label}</label>
        {aside}
      </div>
      <div className="relative">
        {icon && <span className={`pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 ${error ? "text-red-400" : "text-gray-400"}`}>{icon}</span>}
        <input id={id} aria-invalid={error ? true : undefined} aria-describedby={described} {...input}
          className={`w-full rounded-lg border bg-white py-2.5 text-sm text-gray-900 placeholder:text-gray-400 shadow-sm
            transition-[border-color,box-shadow] duration-150 focus:outline-none focus:ring-4
            ${icon ? "pl-10" : "pl-3.5"} ${trailing ? "pr-11" : "pr-3.5"}
            ${error ? "border-red-300 focus:border-red-400 focus:ring-red-100" : "border-gray-300 hover:border-gray-400 focus:border-brand-500 focus:ring-brand-100"}`} />
        {trailing && <span className="absolute right-1.5 top-1/2 -translate-y-1/2">{trailing}</span>}
      </div>
      {hint && <p id={`${id}-hint`} className="mt-1.5 text-xs text-gray-500">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1.5 text-xs text-red-600">{error}</p>}
    </div>
  );
}

function PasswordField({ label, value, onChange, error, aside, hint, autoComplete = "current-password", autoFocus }) {
  const [visible, setVisible] = useState(false);
  return (
    <TextField label={label} icon={<LockIcon />} error={error} aside={aside} hint={hint} type={visible ? "text" : "password"}
      value={value} onChange={onChange} autoComplete={autoComplete} autoFocus={autoFocus} spellCheck={false}
      trailing={(
        <button type="button" onClick={() => setVisible((v) => !v)} aria-pressed={visible}
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400">
          <EyeIcon off={visible} />
        </button>
      )} />
  );
}

const PrimaryButton = ({ busy, busyText, children }) => (
  <button type="submit" disabled={busy}
    className="relative w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm transition-all duration-150
      hover:bg-brand-700 hover:shadow-md active:translate-y-px focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200
      disabled:cursor-not-allowed disabled:opacity-70">
    {busy ? (
      <span className="inline-flex items-center gap-2">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />
        {busyText}
      </span>
    ) : children}
  </button>
);

const LinkButton = ({ onClick, children, className = "" }) => (
  <button type="button" onClick={onClick}
    className={`rounded text-sm font-medium text-brand-600 transition-colors hover:text-brand-800 hover:underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${className}`}>
    {children}
  </button>
);

// The navy panel: a quiet line pattern and two soft glows behind the logo and tagline.
function BrandPanel() {
  return (
    <aside className="relative hidden md:flex md:w-[42%] lg:w-1/2 flex-col justify-between overflow-hidden p-10 lg:p-14 text-white"
      style={{ background: "linear-gradient(150deg, #0f2033 0%, #1a3a5c 55%, #0f2033 100%)" }}>
      <svg className="absolute inset-0 h-full w-full opacity-[0.07]" aria-hidden="true">
        <defs>
          <pattern id="login-grid" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M44 0H0v44" fill="none" stroke="white" strokeWidth="0.8" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#login-grid)" />
      </svg>
      <div className="absolute -top-48 -right-40 h-[30rem] w-[30rem] rounded-full bg-brand-300 opacity-[0.10] blur-3xl" aria-hidden="true" />
      <div className="absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-brand-400 opacity-[0.15] blur-3xl" aria-hidden="true" />

      <div className="relative">
        <div className="inline-flex items-center justify-center rounded-2xl bg-white p-4 lg:p-5 shadow-xl shadow-black/20">
          <img src="/triam-logo.png" alt="Triam" className="h-16 lg:h-20 w-auto" />
        </div>
      </div>

      <div className="relative max-w-md">
        <div className="mb-6 h-1 w-12 rounded-full bg-gold" aria-hidden="true" />
        <h1 className="text-3xl lg:text-[2.6rem] font-semibold leading-[1.15] tracking-tight">
          One platform.<br />Complete client management.
        </h1>
        <p className="mt-5 text-base leading-relaxed text-brand-200">
          Onboarding, compliance, servicing and reporting for the Triam group, in one place.
        </p>
      </div>

      <p className="relative text-xs text-brand-300">© {new Date().getFullYear()} Triam Management Services</p>
    </aside>
  );
}

function Footer() {
  const links = [
    site.privacyUrl && { label: "Privacy Policy", href: site.privacyUrl },
    site.termsUrl && { label: "Terms of Use", href: site.termsUrl },
    site.supportEmail && { label: "Contact Support", href: `mailto:${site.supportEmail}` },
  ].filter(Boolean);
  return (
    <footer className="mt-10 flex flex-col items-center gap-2 text-center text-xs text-gray-500">
      {links.length > 0 && (
        <nav aria-label="Legal and support" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          {links.map((l) => (
            <a key={l.label} href={l.href} target={l.href.startsWith("mailto:") ? undefined : "_blank"} rel="noopener noreferrer"
              className="rounded transition-colors hover:text-brand-700 hover:underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
              {l.label}
            </a>
          ))}
        </nav>
      )}
      <span className="md:hidden">© {new Date().getFullYear()} Triam Management Services</span>
      {VERSION && <span className="tabular-nums text-gray-400">Version {VERSION}</span>}
    </footer>
  );
}

export default function LoginPage() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [view, setView] = useState(resetToken ? "reset" : "signin"); // "signin" | "forgot" | "reset"
  const [email, setEmail] = useState(handedOverEmail || rememberedEmail);
  const [remember, setRemember] = useState(!!rememberedEmail);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [notice, setNotice] = useState(takeNotice); // why the session ended, shown once, on the sign-in page
  useEffect(() => {
    try { sessionStorage.removeItem("triam-idle-signout"); sessionStorage.removeItem("triam-session-expired"); }
    catch { /* storage unavailable */ }
  }, []);
  const [success, setSuccess] = useState("");
  // The reset link's token belongs to this sign-in page only: after a later sign-out the page opens on Sign in.
  const [token] = useState(resetToken);
  useEffect(() => { resetToken = ""; }, []);
  const [loading, setLoading] = useState(false);

  const show = (next) => { setView(next); setError(""); setFieldErrors({}); setNotice(""); setSuccess(""); setPassword(""); setRepeat(""); };

  // Each action: clear the error, show progress, and show the server's message if it fails.
  const run = async (fallback, action) => {
    setError("");
    setLoading(true);
    try { await action(); }
    catch (e) { setError(e.response?.data?.detail || fallback); }
    finally { setLoading(false); }
  };

  const checkEmail = () => (!email.trim() ? "Enter your email address" : !EMAIL_RE.test(email) ? "Enter a valid email address" : "");

  const submit = (e) => {
    e.preventDefault();
    const errs = { email: checkEmail(), password: password ? "" : "Enter your password" };
    setFieldErrors(errs);
    if (errs.email || errs.password) return;
    run("Login failed. Please check your credentials.", async () => {
      const address = email.trim().toLowerCase();
      const data = await authApi.login(address, password);
      try { if (remember) localStorage.setItem(REMEMBER_KEY, address); else localStorage.removeItem(REMEMBER_KEY); }
      catch { /* storage unavailable */ }
      setTokens(data.access_token, data.refresh_token, data.user, !!data.password_change_recommended);
    });
  };

  const sendLink = (e) => {
    e.preventDefault();
    const problem = checkEmail();
    setFieldErrors({ email: problem });
    if (problem) return;
    run("Could not send the reset link. Please try again.", async () => {
      const { data } = await authApi.forgotPassword(email.trim().toLowerCase());
      setSuccess(data?.email_sent
        ? "If the email is registered, a reset link is on its way. Your administrator has also been notified."
        : "Your administrator has been notified and will reset your password.");
    });
  };

  const savePassword = (e) => {
    e.preventDefault();
    const errs = { password: passwordProblem(password) || "", repeat: password !== repeat ? "The passwords don't match" : "" };
    setFieldErrors(errs);
    if (errs.password || errs.repeat) return;
    run("Could not change the password.", async () => {
      await authApi.resetPassword(token, password);
      show("signin");
      setSuccess("Password changed. Sign in with your new password.");
    });
  };

  const onEmail = (ev) => { setEmail(ev.target.value.replace(/\s/g, "")); if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: "" })); };
  const emailField = (props) => (
    <TextField label="Email" icon={<MailIcon />} type="email" name="email" autoComplete="username" inputMode="email"
      placeholder="name@company.com" value={email} onChange={onEmail} error={fieldErrors.email}
      autoCapitalize="none" autoCorrect="off" spellCheck={false} {...props} />
  );

  const heading = {
    signin: ["Welcome back", "Sign in to your Triam CRM account to continue."],
    forgot: ["Reset your password", "Enter your work email and we'll help you get back in."],
    reset: ["Choose a new password", "Pick a strong password you haven't used here before."],
  }[view];

  return (
    <div className="flex min-h-screen bg-white">
      <BrandPanel />

      <main className="flex flex-1 flex-col bg-gray-50 md:bg-white">
        {/* Phones: the logo on a navy band in place of the panel */}
        <div className="md:hidden flex items-center justify-center px-6 py-7"
          style={{ background: "linear-gradient(150deg, #0f2033 0%, #1a3a5c 100%)" }}>
          <div className="rounded-xl bg-white p-3 shadow-lg shadow-black/20">
            <img src="/triam-logo.png" alt="Triam" className="h-12 w-auto" />
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-start px-5 py-8 sm:justify-center sm:px-10 lg:px-16">
          <div className="mx-auto w-full max-w-[400px]">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8 md:border-0 md:p-0 md:shadow-none">
              <div className="mb-7">
                <h2 className="text-[1.65rem] font-semibold tracking-tight text-gray-900">{heading[0]}</h2>
                <p className="mt-1.5 text-sm text-gray-500">{heading[1]}</p>
              </div>

              {(error || notice || success) && (
                <div className="mb-5 space-y-3">
                  {notice && <Message tone="info">{notice}</Message>}
                  {success && <Message tone="success">{success}</Message>}
                  {error && <Message tone="error">{error}</Message>}
                </div>
              )}

              {view === "signin" && (
                <form onSubmit={submit} noValidate className="space-y-5">
                  {emailField({ autoFocus: !handedOverEmail && !rememberedEmail })}
                  <PasswordField label="Password" value={password} error={fieldErrors.password}
                    autoFocus={!!(handedOverEmail || rememberedEmail)}
                    onChange={(ev) => { setPassword(ev.target.value); if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: "" })); }}
                    aside={<LinkButton onClick={() => show("forgot")}>Forgot password?</LinkButton>} />
                  <label className="flex w-fit cursor-pointer select-none items-center gap-2.5 text-sm text-gray-600">
                    <input type="checkbox" checked={remember} onChange={(ev) => setRemember(ev.target.checked)}
                      className="h-4 w-4 cursor-pointer rounded border-gray-300 text-brand-600 accent-brand-600 focus:ring-2 focus:ring-brand-200" />
                    Remember my email
                  </label>
                  <PrimaryButton busy={loading} busyText="Signing in…">Sign in</PrimaryButton>
                </form>
              )}

              {view === "forgot" && (
                <form onSubmit={sendLink} noValidate className="space-y-5">
                  {emailField({ autoFocus: true, readOnly: !!success })}
                  {!success && <PrimaryButton busy={loading} busyText="Sending…">Send reset link</PrimaryButton>}
                  <div className="text-center"><LinkButton onClick={() => show("signin")}>← Back to sign in</LinkButton></div>
                </form>
              )}

              {view === "reset" && (
                <form onSubmit={savePassword} noValidate className="space-y-5">
                  <PasswordField label="New password" autoComplete="new-password" autoFocus value={password} hint={PASSWORD_HINT}
                    error={fieldErrors.password} onChange={(ev) => setPassword(ev.target.value)} />
                  <PasswordField label="Repeat new password" autoComplete="new-password" value={repeat}
                    error={fieldErrors.repeat} onChange={(ev) => setRepeat(ev.target.value)} />
                  <PrimaryButton busy={loading} busyText="Saving…">Save password</PrimaryButton>
                  <div className="text-center"><LinkButton onClick={() => show("signin")}>← Back to sign in</LinkButton></div>
                </form>
              )}
            </div>

            <Footer />
          </div>
        </div>
      </main>
    </div>
  );
}
