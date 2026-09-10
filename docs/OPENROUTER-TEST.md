# First rollout: one OpenRouter test agent

This preview is for a simple connection test on a local Windows Hearth hub. It connects one model to one private room. It does not configure ChatGPT, Codex, Claude, MiniMax desktop apps, or browser extensions.

## Click-through setup

1. Extract the whole Windows setup ZIP. Run **Install Hearth.cmd**, finish hub setup, and sign into chat using the login you chose.
2. Click **Connect OpenRouter** in the installer, or double-click **Connect OpenRouter.cmd** later.
3. Click **Open OpenRouter keys**. Create a **regular API key**, named something like `hearth-installer-test`, with a spending limit of **$5 or less**. Prefer a total limit with no reset for this short trial. Keep the existing Hy4 key unchanged. Management keys are not accepted.
4. Paste the new key into the masked key field. Do not paste it into a chat or share it with another person.
5. Keep the default agent name `helper`, or choose another short lowercase name. Click **Load models**, then choose a text model. You can also paste the provider/model ID from OpenRouter.
6. Read and check the message-sharing box. Click **Test reply**. This checks the key's remaining limit and requests one short greeting; it may use a small amount of API credit. It sends no Hearth chat or memory.
7. Click **Start agent**. The installer creates its account and private room, then starts it in Docker. When ready, click **Open test room** and send `@helper hello` (substitute your agent's name). An Element mention pill also works.
8. Click **Stop agent** to pause the trial. Closing the window does not stop it. To resume, reopen the connection wizard, enter the same name and key, test, and start again. You can choose a different model for the same agent.

OpenRouter account credits are separate from a key's limit. The wizard does not buy credit or change billing. The list of models is live, rather than a list frozen at packaging time. A text model can still be unavailable with the selected privacy requirements: choose another model if **Test reply** fails.

## What this test agent can do

- Reply only to the installing human's direct mentions in its private test room.
- Send only the current message (up to 4,000 characters) and a short instruction to OpenRouter and the selected provider. Earlier messages, shared memory, attachments, and local files are not included.
- Request at most 512 output tokens per reply. Models that spend the entire allowance on reasoning may return no visible text; choose another model for the trial.
- Attempt at most 20 replies per UTC day, spaced at least 10 seconds apart. Messages over these limits are skipped, not queued.
- Resume its saved Matrix cursor after a restart. Historical messages from the first connection and messages over five minutes old are ignored.

No model-invoked tools are exposed. Shared-memory search and multi-turn context are later rollout steps. These restrictions are deliberate for the first connection test.

Requests set `provider.zdr=true`, `data_collection=deny`, and `allow_fallbacks=false`. These are OpenRouter routing requirements, not an independent guarantee of a provider's behavior. Unsupported routing fails instead of silently relaxing them. See [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection). Key limits are checked through the [current-key endpoint](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key).

## Recovery and storage

The agent runs in Docker under `hearth-openrouter-preview`, connected to the local hub's Docker network. It has no published network ports or Docker control socket. Docker restarts it unless you stop it. The code is copied into the installed hub, so changing a development branch does not remove the running agent's code.

Credentials live under `%LOCALAPPDATA%\Hearth\hub\secrets\openrouter`, restricted to the current Windows user and SYSTEM. They are not encrypted at rest; Windows and Docker administrators can access them. The container receives only this test agent's key and Matrix token, not the hub administrator token. Cursor and daily-limit state live under `data\openrouter`. Do not delete that state to reset limits.

On failure, retry with the same name. Account and room creation are saved as they complete. Setup refuses to replace a different test agent. A failed or interrupted reply is not automatically retried: the runner records its event before making a billable call, favoring no duplicate charges over guaranteed delivery.

The test room has restricted membership but does not use end-to-end encryption, because the small runner does not decrypt Matrix messages. Do not use it for sensitive data during this trial.

## Verification status

Automated checks cover mention filtering, duplicate-call prevention, saved daily/cooldown limits, cursor restart and room filtering, registration challenge handling, bounded/private request payloads, input and key-limit checks, and retryable private-room provisioning using simulated services. The agent tests also run inside its Docker runtime. Windows form initialization, the live public model catalog, Compose configuration and ZIP contents are checked. The live Docker test covers a fresh hub installation, a repeat installation, the initial admin account, four rooms, dashboard observer, agent registration, private-room creation and the running agent's connection.

On September 10, 2026, the Windows pilot completed a real OpenRouter model reply in the local test room, and the operator confirmed it was working. That pilot found and fixed three integration issues: first-account bootstrap tokens, an incorrect administrator Authorization header on agent registration, and Element's empty `m.mentions` metadata preventing typed mentions from waking the agent. These paths now have regression coverage. This is a successful single-machine pilot, not broad Windows compatibility or long-running reliability certification.
