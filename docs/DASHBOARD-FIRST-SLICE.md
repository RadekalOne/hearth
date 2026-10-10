# Dashboard Now / Work / Memory

This draft preserves the deployed Project Hub source before extending it. GitHub main was at d92fd92, while the live service reported `project-hub-a1ce2a28de34-human-token-20261008`. The baseline app.py/work.py hashes were recovered and compared over read-only SSH with the running container. Their upstream reconciliation is a separate first commit. The first slice at `69a8c47` was subsequently deployed with approval. Claude's round-one changes in this PR remain undeployed and unmerged, pending renewed approval.

The Now landing view places the approval/blocker inbox before watcher evidence. Failed watchers and work queued for strictly more than three days also enter Waiting on you. Checkpoint receipt fields take precedence over subsequent chat activity. Watchers are evaluated separately, so another monitor on the same agent/surface cannot conceal an old failed receipt. Strict thresholds are late above 1.5 times cadence and stalled above 3 times cadence; event-driven listeners have no cadence judgment. Healthy rows are collapsed. Each row links to its event, checkpoint, or explicit declaration.

## Watcher declarations

`mcp/memory/dashboard-watchers.json` is the explicit registry for this Hearth installation. The API reads it at startup; an installation can supply another JSON file with `HEARTH_WATCHER_REGISTRY_PATH`. Maintain it when schedules or identities change, and restart only through the normal approved deployment process. Checkpoints and signed posts never register watchers implicitly.

Each declaration supplies `id`, `agent`, `surface`, `monitor`, `active`, `kind`, `cadence_minutes`, `receipt_monitors`, and a human-readable `source`. Only `active: true` declarations with `kind: recurring` and a finite positive cadence are judged for lateness. `kind: event-driven` declarations are visible without elapsed-time judgments. Inactive, probe, one-shot, undeclared, and retired identities are excluded. Matching uses the exact declared agent/surface/monitor identity, with no cadence inference from names. A missing checkpoint remains Unconfirmed and links to the declaration id.

Explicit `receipt_monitors` attach runner checkpoints to their parent monitor. They appear as one row with all evidence ids preserved. The newest runner determines its receipt/state; a newer parent or chat post cannot clear a failed runner. A newer successful runner can clear it. Receipt fields are restricted to process exit and closeout verification. The evidence panel distinguishes the selected evidence id from the effective receipt source.

Work is a read-only projection of the existing work store and durable relays. Ready displays as Queued. The deployed work store calls a newly claimed task `running`; the dashboard displays it as Claimed because that transaction supplies ownership rather than a process-start receipt. Actual execution is unverified. Proposed tasks remain visible without being presented as authorized. Work-state ages come from the full transition audit, independent of the bounded activity feed and later comments or memory captures. Relay ages use their last state update; no heuristic title matching merges independent sources.

Memory health counts knowledge by default, including superseded knowledge in the class count. Noise is all nonknowledge records divided by all records. Supersession counts records with a structural `superseded_by` reference. Near-duplicate pairs use the existing cosine-distance threshold and require matching wing/room. The scan is deterministic, capped at 250 knowledge drawers and cached for five minutes. Partial pair counts are explicitly labelled a lower bound; embedding failures display Unavailable, never zero. Counts link to drawer evidence. Search retains the existing knowledge-only default and opt-in history classes.

Work shows per-stage counts, open items first, and completed items in a collapsed section. Handoff titles use the request summary, with the relay id as a fallback when no request is available. Counts and every row retain source inspection.

The existing Projects, Communication, Agents, Relays, detail panels and human Matrix actions remain under Workspace tools. Round one changes no schema, authentication, spend feed, push/SSE, schedules, credentials, production service or npm release.

## Validation

```sh
npm ci
npm ci --prefix mcp/matrix
npm run check
npm test
python -m unittest discover -s test -p "test_*.py"
npx playwright install chromium
npm run test:dashboard
```

The browser test serves real static assets against synthetic API fixtures and checks the three routes at 400px and 1280px, collapsed ordinary watchers, event-driven labels, queued wording, stage counts, collapsed completed work, keyboard tab navigation, empty/error states, page overflow and script errors. It also checks delayed route registration, selected receipt evidence, Matrix event room provenance, keyboard access after search/filter updates, and duplicate-pair sources. The dashboard CI job installs Chromium and runs this suite. Set `SCREENSHOT_DIR` to save screenshots and audit reports; no live tokens or real records enter the fixtures. The Python API fixtures additionally enforce authentication, agent write denial, complete relay coverage and static CSP.

The light-theme browser suite runs axe-core against all three tabs at both widths using WCAG 2 A/AA, 2.1 AA and 2.2 AA rules, including target size. It checks normal text palette contrast at 4.5:1 and input borders at 3:1 against the card background; the accent also provides the visible focus indicator. Keyboard navigation and inspector operations are tested separately. These automated and focused manual checks cover the fixture views, not a full accessibility certification of every legacy tool or assistive-technology combination. Standards: [text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).

Selected checkpoint evidence uses the same receipt calculation as its Now row; aggregate surface activity is available separately. A shared Matrix thread or title is insufficient to establish task/relay identity, so records remain separate until an explicit identity link is available.

Screenshots in `dashboard-first-slice/screenshots/` are synthetic fixtures, not evidence of production execution.
