# 🏋️‍♀️ Huppa CLI

A CLI tool and [MCP](https://modelcontextprotocol.io/) server for [Huppa](https://huppa.app) — browse gym classes, book them, and manage bookings from the command line or through AI assistants like Claude.

<p align="center">
  <img src="docs/claude.png" alt="Claude screenshot" width="600" />
</p>

> **Disclaimer:** This is an unofficial, community-built project and is **not affiliated with, endorsed by, or approved by Huppa**. It interacts with Huppa's public API using your personal credentials. Use at your own risk — the author is not responsible for any account restrictions, data loss, or other consequences. Huppa may change their API at any time, which could break this tool without notice.

## ⚙️ Installation

**Prerequisites:** [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just), and the [GitHub CLI](https://cli.github.com/)

### User installation

Install the latest released wheel as a regular uv tool:

```bash
gh release download -R maxzw/huppa-cli -p '*.whl' -D /tmp/huppa-wheel
uv tool install --force /tmp/huppa-wheel/*.whl
huppa auth setup
```

Upgrade a user installation with:

```bash
huppa update
```

The updater downloads the wheel from the latest GitHub Release and installs it
through uv.

Check the installed version and troubleshoot credential or API configuration:

```bash
huppa version
huppa status
huppa status --json
```

### Development installation

To work from a source checkout instead, use an editable installation:

```bash
git clone https://github.com/maxzw/huppa-cli.git
cd huppa-cli
uv sync

# Install this checkout as the global `huppa` command
just deploy

# Run one-time interactive setup (stores credentials in OS keychain)
huppa auth setup
```

To remove a global installation:

```bash
uv tool uninstall huppa-cli
```

### 🔑 Authentication

The setup command prompts for email/password/subdomain and stores them securely in your system keychain.

To find your subdomain, open your Huppa gym page URL and use the first part before `.huppa.app`.

Example: `https://mygym.huppa.app/me` → subdomain is `mygym`

```bash
huppa auth setup   # interactive credential setup
huppa auth whoami  # show current authenticated user
huppa auth logout  # clear stored credentials
```

Status output shows credential sources and whether the API is reachable. Passwords
are never printed.

Profile-specific authentication:

```bash
HUPPA_PROFILE=work-gym huppa auth setup
HUPPA_PROFILE=work-gym huppa auth whoami
```

Environment-variable authentication:

```bash
HUPPA_EMAIL="you@example.com" \
HUPPA_PASSWORD="your-password" \
HUPPA_SUBDOMAIN="mygym" \
huppa classes 2026-03-08
```

## 🛠️ CLI Usage

All commands output structured JSON.

```bash
# List classes for a date
huppa classes 2026-03-08

# List classes for multiple dates
huppa classes 2026-03-08 2026-03-09

# Show upcoming bookings
huppa bookings
huppa bookings --filter past --per-page 10

# Show memberships
huppa memberships

# Book a class (use organization_id and occurrence_id from `huppa classes`)
huppa book <organization_id> <occurrence_id>

# Cancel a booking
huppa cancel <organization_id> <occurrence_id>

# Waitlist management
huppa waitlist join <organization_id> <occurrence_id>
huppa waitlist leave <organization_id> <occurrence_id>

# Show all available commands
huppa --help
```

## 🤖 MCP Server

The CLI includes a built-in MCP server for AI assistants:

```bash
huppa mcp
```

### Connecting to Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "huppa": {
      "command": "/full/path/to/uv",
      "args": ["--directory", "/absolute/path/to/huppa-cli", "run", "huppa", "mcp"]
    }
  }
}
```

Find uv path with `which uv`. Use full paths (not `"uv"`) because Claude Desktop starts MCP servers with limited `PATH`.

### MCP Tools

| Tool | Description |
|---|---|
| `get_classes(date)` | List available gym classes for a given date (`YYYY-MM-DD`). |
| `get_classes_multiple_dates(list_of_dates)` | Get classes for multiple dates at once. |
| `book_class(organization_id, occurrence_id)` | Book a class. |
| `cancel_booking(organization_id, occurrence_id)` | Cancel an existing booking. |
| `join_waitlist(organization_id, occurrence_id)` | Join the waitlist for a full class. |
| `leave_waitlist(organization_id, occurrence_id)` | Leave the waitlist. |
| `get_my_bookings(filter, per_page, page)` | List bookings and waitlists. |
| `get_memberships()` | Get memberships with credit balance and payment dates. |

## 📋 License

[MIT](LICENSE)
