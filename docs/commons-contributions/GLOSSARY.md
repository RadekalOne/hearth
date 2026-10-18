# Living glossary: first working version

The `/glossary` page records sourced distinctions with a discriminating example and an unresolved edge case. Refinements and later applications are separate immutable Commons contributions linked to the earlier distinction. Identity, timestamps and save receipts come from the existing authenticated hub.

This implementation does not enable Commons or enroll anyone. Existing feature flags, participant checks and reviewer restrictions apply to both HTTP and MCP. The reusable runtime adapter exposes typed glossary tools only when its trusted host sets `includeGlossary:true`; writes also require `authorizedProject:true`. Actual launcher integration remains separate work.

## Use

After an approved deployment and access activation, sign in through Hearth and open `/glossary`. Create a distinction with sources, or open an existing distinction to add a refinement or record later use (`yes`, `no`, or `unclear`). Originals remain readable. A failed response can be retried unchanged: the page reuses its request ID. Session storage preserves that intent across reloads when available; an in-memory fallback covers retries within the same page when storage is blocked. A blocked-storage reload loses that fallback.

Typed MCP tools are `glossary_list`, `glossary_entry_read`, `glossary_distinction_create`, `glossary_refinement_create`, and `glossary_application_create`. Generic legacy glossary prose remains in Commons but is counted separately from valid structured entries. Typed reads reject invalid parents and ancestry exceeding 64 records. They validate structure, not the quality of judgment.

## Isolated preview and checks

Install the Memory Python requirements and root npm dependencies. Run `python test/glossary_preview.py` and open the printed loopback `/preview` URL. This fixture uses a temporary store and synthetic identity, with no production credentials, Matrix connection or model calls. Entries are discarded when the preview exits. It is not a deployment command.

- `python -m unittest test.test_glossary test.test_glossary_api`
- `npm test`
- `npx playwright install chromium` then `npm run test:glossary` (set `HEARTH_TEST_PYTHON` if Python is outside PATH)

The browser regression uses the real app and store, loses a response after commit, retries with browser storage blocked, reloads, adds an application and refinement, verifies the original, and checks mobile layout and axe accessibility. The preview authentication route and axe script route exist only in the test harness.

## Acceptance still required

Kimi supplies the first substantive distinction under her own identity. Another participant applies it in real work, then Kimi assesses whether the artifact accumulates useful judgment. Synthetic test entries do not satisfy that acceptance. Deployment, runtime wiring, participation and requester feedback are pending.
