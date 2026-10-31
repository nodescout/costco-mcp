"""Failures this fork can explain, written for the agent calling the server.

The agent using this server does not know that Costco keeps moving its sign-in
policy or how this fork is maintained. Each error here says what broke and what
to tell the operator, so the agent stops retrying and reports it.
"""

import re

FORK_PROCESS_DOC = "https://github.com/nodescout/costco-mcp/blob/nodescout/main/FORK_MAINTENANCE.md"

_NEW_TOKEN = (
    "The Costco MCP needs a new refresh token for this membership. Follow the Token section "
    "of docs/COSTCO_MCP.md in your Claude Code configuration repository."
)


class CostcoServiceError(RuntimeError):
    """A failure the calling agent cannot fix, with what to tell the operator."""

    def __init__(self, status: str, detail: str, tell_operator: str) -> None:
        super().__init__(f"{status}: {detail} Stop retrying and tell the operator: {tell_operator}")
        self.status = status
        self.detail = detail
        self.tell_operator = tell_operator


def token_failure(status_code: int, body: str, policy: str) -> CostcoServiceError:
    """Classify a failed token refresh. Only matched values leave this function, never the body."""
    match = re.search(r"AADB2C\d+", body)
    code = match.group(0) if match else f"HTTP {status_code}"
    expected = re.search(r"Expected Value\s*:\s*(B2C_1A_\w+)", body)

    if code == "AADB2C90088" and expected and expected.group(1).lower() != policy:
        needed = expected.group(1).lower()
        return CostcoServiceError(
            "needs_fork_update",
            f"Costco's sign-in policy moved. This build uses {policy}, and this account's token "
            f"needs {needed}. A new token will not fix this.",
            f"The Costco MCP needs a fork update. Set POLICY_NAME to {needed} in the "
            f"nodescout/costco-mcp fork, following 'Updating the sign-in policy' in {FORK_PROCESS_DOC}",
        )
    if 400 <= status_code < 500:
        return CostcoServiceError("needs_new_token", f"Costco rejected the saved refresh token ({code}).", _NEW_TOKEN)
    return CostcoServiceError(
        "costco_unavailable",
        f"Costco's sign-in service returned {code}.",
        "Costco's sign-in service is failing, which is usually temporary. Try again later.",
    )


def no_token(account: str) -> CostcoServiceError:
    return CostcoServiceError("needs_new_token", f"Account '{account}' has no saved refresh token.", _NEW_TOKEN)


def api_failure(status_code: int) -> CostcoServiceError:
    """Classify a failed call to Costco's API, made after sign-in succeeded."""
    if status_code == 401:
        return CostcoServiceError(
            "needs_fork_update",
            "Costco's API rejected a freshly issued sign-in token, so a value Costco requires has probably changed.",
            f"The Costco MCP needs a fork update. Check CLIENT_IDENTIFIER in api.py against the "
            f"client-identifier header costco.com sends now. {FORK_PROCESS_DOC}",
        )
    if status_code in (403, 429):
        return CostcoServiceError(
            "blocked_by_costco",
            f"Costco's API refused the request with HTTP {status_code}.",
            "Costco is blocking the MCP's requests. Stop using it for now, because repeated attempts "
            f"can put the membership at risk. The browser fingerprint may need updating. {FORK_PROCESS_DOC}",
        )
    return CostcoServiceError(
        "costco_unavailable",
        f"Costco's API returned HTTP {status_code}.",
        "Costco's API is failing, which is usually temporary. Try again later.",
    )


def graphql_failure(errors: list) -> CostcoServiceError:
    """Classify a GraphQL error in an otherwise successful response."""
    first = errors[0] if errors else {}
    message = first.get("message", "") if isinstance(first, dict) else str(first)
    return CostcoServiceError(
        "needs_fork_update",
        f"Costco's API rejected the server's query: {message[:200]}",
        f"Costco may have changed its API, so the Costco MCP probably needs a fork update. {FORK_PROCESS_DOC}",
    )
