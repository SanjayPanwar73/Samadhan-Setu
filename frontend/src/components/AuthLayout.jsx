import Brand from "./Brand";
import Icon from "./Icon";

export default function AuthLayout({ children, register = false }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f3f6f3] p-4 sm:p-8 lg:p-12">
      <div className="grid w-full max-w-[1080px] overflow-hidden rounded-2xl border border-[#dde6de] bg-white shadow-[0_20px_70px_-35px_#244d3840] lg:grid-cols-[.95fr_1.05fr]">
        <aside className="relative hidden flex-col overflow-hidden bg-brand-900 p-10 text-white lg:flex xl:p-12">
          <div className="[&_.brand]:text-white [&_.brand-subtitle]:text-brand-200 [&_.brand-mark]:bg-white/10">
            <Brand />
          </div>
          <div className="relative z-10 my-auto py-16">
            <p className="text-[10px] font-semibold uppercase tracking-[.2em] text-brand-300">
              A community that listens
            </p>
            <h2 className="mt-5 text-[38px] font-medium leading-[1.17] tracking-[-.045em]">
              {register ? (
                <>
                  Your voice.
                  <br />A better tomorrow.
                </>
              ) : (
                <>
                  Every concern.
                  <br />A way forward.
                </>
              )}
            </h2>
            <p className="mt-6 max-w-xs text-[13px] leading-7 text-brand-200/90">
              A clear path from raising an issue to finding a resolution. Stay
              informed, stay connected, and make a difference.
            </p>
            <div className="mt-9 space-y-5">
              {[
                ["file", "Raise a concern", "Share what needs attention."],
                [
                  "clock",
                  "Follow every step",
                  "Keep track of your complaint’s status.",
                ],
                [
                  "checkCircle",
                  "Help close the loop",
                  "Share feedback on the resolution.",
                ],
              ].map(([icon, title, description]) => (
                <div key={title} className="flex items-start gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/5 text-brand-200">
                    <Icon name={icon} size={17} />
                  </span>
                  <div>
                    <p className="text-xs font-medium text-white/90">{title}</p>
                    <p className="mt-1 text-[11px] text-brand-200/75">
                      {description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-brand-200/70">
            <Icon name="shield" size={14} />
            Built for clarity. Designed around people.
          </div>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-36 -right-44 h-96 w-96 rounded-full border-[40px] border-white/[.025]"
          />
        </aside>
        <div className="px-6 py-9 sm:px-12 sm:py-12 lg:px-14">
          <div className="mb-9 lg:hidden">
            <Brand />
          </div>
          {children}
          <p className="mt-9 flex items-center justify-center gap-1.5 text-[10px] text-slate-500">
            <Icon name="shield" size={13} />
            Your workspace. Your progress. One place.
          </p>
        </div>
      </div>
    </main>
  );
}
