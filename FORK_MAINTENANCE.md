# Fork maintenance: sign-in policy updates and upstream changes

This repository is the `nodescout` fork of [thehesiod/costco-mcp](https://github.com/thehesiod/costco-mcp). The fork exists because Costco keeps changing its sign-in policy, and upstream's fixes for that have sat unmerged, so the server breaks until someone changes one value. Working from a fork lets the operator make that change the same day. Upstream's `README.md` describes the project itself.

These steps are manual. Nothing here is automated yet.

## Branches and tags

- `main` mirrors upstream `main`. Nobody commits to it.
- `nodescout/main` is the default branch. It is based on upstream's `0.1.2` release, and it carries this file and every fork change. Other fork branches also take the `nodescout/` prefix.
- Runtime tags have the form `nodescout-<upstream version>-<policy number>`, for example `nodescout-0.1.2-219`. A later fork change at the same policy adds a revision, such as `nodescout-0.1.2-219.1`. The operator's machine runs a tagged commit on `nodescout/main`.
- Do not copy upstream's bare version tags, such as `0.1.2`, into this fork. `.github/workflows/publish.yml` would run on tags of that form if Actions were on.

## How the server reports a failure

An agent using this server does not know any of this history, so the server tells it what to do. The fork adds three things, and the failure messages are in `src/costco_mcp_server/diagnostics.py`:

1. The MCP server instructions, which every session receives, say that if a tool fails the agent should call `doctor` once, stop retrying, and pass on the `tell_operator` text.
2. Every failed tool call returns an error that names the problem and what to tell the operator.
3. The `doctor` tool does a real sign-in and a small receipt read, then reports one of these statuses:

| Status | Meaning | What happens next |
| --- | --- | --- |
| `ok` | Sign-in and a read both worked. | Nothing. |
| `needs_fork_update` | Costco moved its sign-in policy or changed its API. | Follow the steps below. The report names the policy value to use. |
| `needs_new_token` | The saved token is missing, expired, or revoked. | Save a new token. |
| `blocked_by_costco` | Costco's API refused the requests with HTTP 403 or 429. | Stop using the server for now, then look at the browser fingerprint (`chrome131`). |
| `costco_unavailable` | Costco returned a server error. | Try again later. |
| `unknown_failure` | Anything else, including a timeout, which can mean Costco is blocking requests. | Read the report's `detail`. |

When Costco makes a failure mode visible that these do not cover, add it to `diagnostics.py`.

## Updating the sign-in policy

A refresh token is bound to the Azure AD B2C policy of the login that issued it, and the server has that policy hard-coded as `POLICY_NAME` in `src/costco_mcp_server/auth.py`. When they stop matching, every data call fails, even though `check_auth_status` still looks healthy, because it only reads the saved file. `doctor` reports `needs_fork_update` with the value to use. It reads that value from Costco's response:

```
AADB2C90088: The provided grant has not been issued for this endpoint.
Actual Value : B2C_1A_SSO_WCS_signup_signin_201
Expected Value : B2C_1A_SSO_WCS_signup_signin_219
```

Saving another token does not fix this. Follow these steps, where `NNN` is the number from `Expected Value`:

1. On `nodescout/main`, set `POLICY_NAME` to the lowercase value, `b2c_1a_sso_wcs_signup_signin_NNN`.
2. Commit it with the message `fix(auth): update Azure AD B2C policy to _NNN`.
3. Close every Claude Code session running the server. Windows will not replace a running executable, and the install fails with "os error 32" otherwise.
4. Run `uv sync --frozen --no-editable --no-dev --reinstall-package costco-mcp-server --refresh-package costco-mcp-server` from the repository root. The two package flags are required, because the package version does not change and a plain sync would keep the old code.
5. Start a new session and run `doctor`, which should report `ok`. `check_auth_status` does not prove the fix.
6. Tag and push with `git tag -a nodescout-0.1.2-NNN -m "Sign-in policy NNN"` and `git push origin nodescout/main nodescout-0.1.2-NNN`.
7. Save a new token for any other account, from a fresh login. `POLICY_NAME` applies to every account, so a token from an older login now fails the same way, with the older number as `Expected Value`.

## Taking upstream changes

Check upstream by hand with `git fetch upstream --no-tags`, and sync this fork's `main` with GitHub's Sync fork button.

To take an upstream release, review the diff of `src/`, `pyproject.toml`, `uv.lock`, and `.github/workflows/`, merge it into `nodescout/main`, keep the newer of the two policy values, and tag it with the new upstream version. Check the review for new outbound hosts and for anything that writes to Costco.

Upstream's open pull request for mcp 2.x changes the server's imports. This fork is locked to mcp 1.26.0 by `uv.lock`, so the mcp 2.x change is not needed yet.

## GitHub Actions in this fork

GitHub Actions is turned off for this repository, because nothing here needs it and `.github/workflows/publish.yml` publishes to PyPI and the MCP Registry, which this fork does not do. If a later automation needs Actions, turn it back on and disable `publish.yml` first.
