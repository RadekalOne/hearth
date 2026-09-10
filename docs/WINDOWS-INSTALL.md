# Install Hearth on your Windows PC

This is the first Windows wizard preview. It sets up a local Hearth hub, with chat and shared memory accessible on this computer.

**Preview 3 fixes first-account setup.** If an earlier version failed after Docker started, close that wizard, extract the updated ZIP, and retry with the same login and password. Your installed configuration and data are preserved. The installer now handles the bundled chat server's one-time bootstrap token automatically without displaying it.

1. Download the Windows setup ZIP from a release that includes it. Extract the entire ZIP to a folder you can keep. For a source checkout, use the files in that checkout.
2. Double-click **Install Hearth.cmd** in the extracted folder.
3. If needed, use **Get Node.js** and **Get Docker Desktop**. Install Node's LTS version. Follow Docker Desktop's prompts, including any Windows restart. Open Docker Desktop and wait until it is running, then reopen the Hearth installer.
4. Click **Check again**. This checks prerequisites and protects existing Hearth installations.
5. Choose a login name and a password of at least 12 characters. Save these in your password manager, then click **Install Hearth**.
6. Keep the window open during the download and startup. Once Hearth is ready, click **Open chat** and sign in with that login and password.
7. Click **Connect OpenRouter** to add your first test agent. Follow the [OpenRouter test walkthrough](OPENROUTER-TEST.md).

No terminal commands or configuration-file editing are needed for this hub setup. Prerequisite installers may require Windows administrator permission. Hearth's wizard runs as your normal Windows user. Docker Desktop must support Linux containers on your computer; its own installer explains system requirements and any applicable subscription terms.

## Where things live

Hearth's files are in `%LOCALAPPDATA%\Hearth\hub`. Docker stores chat and memory in its persistent volumes. Keep both when moving or backing up Hearth. The wizard does not delete data, expose the hub to the internet, or turn on agent monitoring. Password input is sent privately to the setup process, without putting it in command arguments or a deployment file. Hearth saves account access tokens in its local `secrets` folder; protect this folder like a password.

Keep Docker Desktop running to use Hearth. The chat address is <http://localhost:8009>; the dashboard is <http://localhost:8010>. For the dashboard, click **Copy admin key**, then **Open dashboard** and paste the key into its login box. Keep this key private: it grants administrator access. The first guided agent connection supports [OpenRouter](OPENROUTER-TEST.md). Other applications use the separate [agent onboarding guide](AGENT-ONBOARDING.md).

## If setup stops

Check Docker Desktop and your internet connection, then click **Check again** and retry with the same login and password. A retry preserves the wizard's existing configuration and data; it does not change an account's password. If another Hearth installation or old Docker data is detected, the wizard stops rather than taking it over. Ask for help migrating it.

If a retry still fails, share the wizard's message and installation-folder location with your helper. Do not share `.env` or `secrets`. The command-line installer in that folder can provide more detailed troubleshooting.

## Preview boundaries

This ZIP is an unsigned script-based installer, not yet a signed Windows application. Download it only from a source you trust. Windows or organizational policy may block downloaded scripts; use your organization's normal approval process if needed. This preview still requires the standard Node.js and Docker Desktop installers. It does not install or configure AI agent applications for you.

Developers can build a ZIP with `powershell -NoProfile -File installer/windows/Build-Zip.ps1`. The ZIP uses an explicit public-file allowlist and excludes local credentials and runtime data. Do not distribute a ZIP of a live Hearth installation.
