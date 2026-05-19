import type { ReactNode } from "react";

type Props = {
  icon?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "error";
};

/** Empty / error / informational state shared across views. */
export function StateView({ icon = "◇", title, children, action, tone = "neutral" }: Props) {
  return (
    <section
      className="state-view"
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <span className="state-view__icon" aria-hidden>
        {icon}
      </span>
      <h3 className="state-view__title">{title}</h3>
      {children ? <p className="state-view__body">{children}</p> : null}
      {action ? <div style={{ marginTop: "0.75rem" }}>{action}</div> : null}
    </section>
  );
}
