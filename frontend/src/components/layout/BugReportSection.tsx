import { GITHUB_NEW_ISSUE_URL, GITHUB_REPO, SUPPORT_MAILTO } from "../../lib/support";

/**
 * Persistent, visible call-to-action for reporting bugs and product issues.
 */
export function BugReportSection() {
  return (
    <section className="bug-report" aria-labelledby="bug-report-heading">
      <div className="bug-report__inner">
        <div className="bug-report__icon" aria-hidden>
          ⚑
        </div>
        <div className="bug-report__copy">
          <h2 id="bug-report-heading" className="bug-report__title">
            Report a bug or issue
          </h2>
          <p className="bug-report__desc">
            Something broken, confusing, or missing? Open a GitHub issue or email us — include
            what you expected, what happened, and which page you were on.
          </p>
        </div>
        <div className="bug-report__actions">
          <a
            className="btn btn--primary"
            href={GITHUB_NEW_ISSUE_URL}
            target="_blank"
            rel="noreferrer"
          >
            File on GitHub
          </a>
          <a className="btn btn--secondary" href={SUPPORT_MAILTO}>
            Email report
          </a>
          <a
            className="bug-report__link"
            href={`${GITHUB_REPO}/issues`}
            target="_blank"
            rel="noreferrer"
          >
            View open issues
          </a>
        </div>
      </div>
    </section>
  );
}
