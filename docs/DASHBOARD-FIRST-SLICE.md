# Dashboard Now / Work / Memory

This draft preserves the deployed Project Hub source before extending it. GitHub main was at d92fd92, while the live service reported `project-hub-a1ce2a28de34-human-token-20261008`. The baseline app.py/work.py hashes were recovered and compared over read-only SSH with the running container. Their upstream reconciliation is a separate first commit. No production service, schedule, identity, credential or data was changed.

The Now landing view places the approval/blocker inbox before watcher evidence. Checkpoint receipt fields take precedence over subsequent chat activity. Watchers are evaluated separately, so another monitor on the same agent/surface cannot conceal an old failed receipt. Strict thresholds are late above 1.5 times cadence and stalled above 3 times cadence; event-driven listeners have no cadence judgment. Healthy rows are collapsed. Each row links to its event or checkpoint.

Work is a read-only projection of the existing work store and durable relays. Ready displays as Queued. The deployed work store calls a newly claimed task `running`; the dashboard displays it as Claimed because that transaction supplies ownership rather than a process-start receipt. Actual execution is unverified. Proposed tasks remain visible without being presented as authorized. Work-state ages come from the full transition audit, independent of the bounded activity feed and later comments or memory captures. Relay ages use their last state update; no heuristic title matching merges independent sources.

Memory health counts knowledge by default, including superseded knowledge in the class count. Noise is all nonknowledge records divided by all records. Supersession counts records with a structural `superseded_by` reference. Near-duplicate pairs use the existing cosine-distance threshold and require matching wing/room. The scan is deterministic, capped at 250 knowledge drawers and cached for five minutes. Partial pair counts are explicitly labelled a lower bound; embedding failures display Unavailable, never zero. Counts link to drawer evidence. Search retains the existing knowledge-only default and opt-in history classes.

The existing Projects, Communication, Agents, Relays, detail panels and human Matrix actions remain under Workspace tools. There are no schema, authentication, spend-feed, push/SSE, deployment or npm release changes.

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

The browser test serves real static assets against synthetic API fixtures and checks the three routes at 400px and 1280px, collapsed ordinary watchers, event-driven labels, queued wording, keyboard tab navigation, empty/error states, page overflow and script errors. Set `SCREENSHOT_DIR` to save the screenshots; no live tokens or real records enter the fixtures. The Python API fixtures additionally enforce authentication, agent write denial and static CSP.

Screenshots in `dashboard-first-slice/screenshots/` are synthetic fixtures, not evidence of production execution.
