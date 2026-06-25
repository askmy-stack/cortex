import type { ReactNode } from "react";
import { IconEmpty } from "./icons";

type Props = {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "error";
};

/** Empty / error / informational state shared across views. */
export function StateView({ icon, title, children, action, tone = "neutral" }: Props) {
  const glyph = icon ?? <IconEmpty size={28} />;
  return (
    <section
      className={`state-view ${tone === "error" ? "state-view--error" : ""}`}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <span className="state-view__icon" aria-hidden>
        {glyph}
      </span>
      <h3 className="state-view__title">{title}</h3>
      {children ? <div className="state-view__body">{children}</div> : null}
      {action ? <div className="state-view__action">{action}</div> : null}
    </section>
  );
}
