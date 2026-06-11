# PR Retriever

Export **unresolved** pull-request review threads from **Azure DevOps**, **GitLab**, or **GitHub** into a structured XML file. Each thread includes file location, line numbers, and comments tagged as `me` vs `reviewer`.

Useful for feeding open review feedback into an AI assistant or tracking what still needs to be addressed.

## Installation

```bash
git clone <this-repo>
cd pr-retriever
pip install -r requirements.txt
```

**Windows (Azure DevOps Server on-prem):** `requests-negotiate-sspi` enables automatic Windows login when you are on a domain-joined machine.

## Quick start

**With a config file (recommended):**

```bash
cp pr-retriever.config.example.json pr-retriever.json
# Edit pr-retriever.json and add your tokens

python -m pr_retriever \
  --url "<PR or MR URL from your browser>" \
  --me "your.username" \
  --out review.xml
```

**Or pass a token on the command line:**

```bash
python -m pr_retriever \
  --url "<PR or MR URL from your browser>" \
  --me "your.username" \
  --token "<access token>" \
  --out review.xml
```

`python main.py` also works.

### Examples

**GitHub**
```bash
python -m pr_retriever \
  --url "https://github.com/owner/repo/pull/123" \
  --me "octocat" \
  --token "$GITHUB_TOKEN" \
  --out review.xml
```

**GitLab**
```bash
python -m pr_retriever \
  --url "https://gitlab.example.com/group/project/-/merge_requests/55" \
  --me "jane.doe" \
  --token "$GITLAB_TOKEN" \
  --out review.xml
```

**Azure DevOps**
```bash
python -m pr_retriever \
  --url "https://dev.azure.com/org/project/_git/repo/pullrequest/123" \
  --me "jane.doe" "jane.doe@company.com" \
  --token "$AZURE_DEVOPS_PAT" \
  --out review.xml
```

Copy the **exact URL** from your browser address bar. Do not use placeholder paths like `group/project`.

## Output

The tool writes XML like:

```xml
<pr_review provider="github" source_url="..." open_thread_count="3">
  <thread id="..." status="active" location="src/app.py:42" file="src/app.py" line_start="42" side="new">
    <comments>
      <reviewer author="reviewer1" username="reviewer1" created_at="...">Please rename this variable.</reviewer>
      <me author="you" username="you" created_at="...">Good point, will fix.</me>
    </comments>
    <todo />
  </thread>
</pr_review>
```

- **`reviewer`** — comments from other people (or not matching `--me`)
- **`me`** — comments authored by you (matched via `--me` aliases)
- **`location`** — `file:line`, `file:start-end`, or `overview` for general comments
- **`side`** — `new` / `old` diff side where applicable

## Config file

Store tokens once in a JSON file instead of passing them every run.

1. Copy the example:
   ```bash
   cp pr-retriever.config.example.json pr-retriever.json
   ```
2. Fill in the sections you need (`github`, `gitlab`, `azure`).
3. Run without `--token`:
   ```bash
   python -m pr_retriever --url "..." --me "your.username" --out review.xml
   ```

**Example `pr-retriever.json`:**

```json
{
  "github": {
    "token": "github_pat_xxxxxxxx"
  },
  "gitlab": {
    "token": "glpat-xxxxxxxx"
  },
  "azure": {
    "token": "xxxxxxxx",
    "username": "DOMAIN\\your.user",
    "password": "your_windows_password"
  }
}
```

Each provider section supports `token`, `username`, and `password`. Leave unused fields out or set them to `""`.

**Config file search order** (first match wins):

1. `--config /path/to/file.json`
2. `PR_RETRIEVER_CONFIG` environment variable
3. `./pr-retriever.json` in the current directory
4. `./.pr-retriever.json` in the current directory
5. `~/.config/pr-retriever/config.json`
6. `~/.pr-retriever.json`

**Credential precedence** (highest wins): `--token` / `--username` / `--password` → environment variables → config file.

`pr-retriever.json` is listed in `.gitignore` so you do not commit secrets by accident.

## CLI reference

| Flag | Description |
|------|-------------|
| `--url` | PR/MR URL (required) |
| `--me` | Your username, email, or display name — can repeat (required) |
| `--config` | Path to JSON config file (optional; auto-discovered if omitted) |
| `--token` | Access token (overrides config file) |
| `--username` / `--password` | Azure NTLM or GitLab OAuth login |
| `--provider` | `auto` (default), `azure`, `gitlab`, or `github` |
| `--out` | Output file (default: `pr_review_threads.xml`) |
| `--include-pending-azure` | Include Azure threads with `pending` status |
| `--include-non-resolvable-gitlab` | Include GitLab overview threads that cannot be resolved |
| `--include-resolved-github` | Include GitHub threads already marked resolved |

### Environment variables

| Variable | Provider | Used for |
|----------|----------|----------|
| `PR_RETRIEVER_CONFIG` | All | Path to config JSON file |
| `GITHUB_TOKEN` | GitHub | Personal Access Token |
| `GITLAB_TOKEN` | GitLab | Personal Access Token |
| `GITLAB_USERNAME` / `GITLAB_PASSWORD` | GitLab | OAuth password login |
| `AZURE_DEVOPS_PAT` | Azure | Personal Access Token |
| `AZURE_DEVOPS_USERNAME` / `AZURE_DEVOPS_PASSWORD` | Azure | NTLM login |

Prefer a config file or environment variables over passing secrets on the command line.

---

## Getting access tokens

### GitHub

GitHub uses the **GraphQL API** to fetch review threads with resolution status.

#### Fine-grained token (recommended)

1. Go to [GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/personal-access-tokens).
2. Click **Generate new token**.
3. Set **Repository access** to the repo(s) you need (or all repos).
4. Under **Permissions → Repository permissions**, set:
   - **Pull requests**: Read-only
   - **Contents**: Read-only (needed for some private repos)
5. Generate and copy the token (`github_pat_...`).

#### Classic token

1. Go to [GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens).
2. Click **Generate new token (classic)**.
3. Select scope: **`repo`** (private repos) or **`public_repo`** (public repos only).
4. Generate and copy the token (`ghp_...`).

```bash
export GITHUB_TOKEN="github_pat_..."
python -m pr_retriever --url "https://github.com/owner/repo/pull/1" --me "yourlogin" --out review.xml
```

**GitHub Enterprise Server:** use your instance URL, e.g. `https://github.mycompany.com/owner/repo/pull/123`. The tool calls `https://github.mycompany.com/api/graphql`.

---

### GitLab

#### Personal Access Token (recommended)

1. Go to **User Settings → Access Tokens** (or `/-/user_settings/personal_access_tokens`).
2. Create a token with scope **`api`** (or at minimum **`read_api`** on newer GitLab versions).
3. Copy the token (`glpat-...`).

```bash
export GITLAB_TOKEN="glpat-..."
python -m pr_retriever \
  --url "https://gitlab.example.com/group/project/-/merge_requests/55" \
  --me "your.username" \
  --out review.xml
```

#### Username + password

Some self-hosted GitLab instances allow OAuth password grant:

```bash
python -m pr_retriever \
  --url "https://gitlab.example.com/group/project/-/merge_requests/55" \
  --me "your.username" \
  --username "your.username" \
  --password "your.password" \
  --out review.xml
```

Use the **full project path** from the browser URL, not a placeholder.

---

### Azure DevOps

#### Personal Access Token (recommended)

**Azure DevOps Services (cloud — `dev.azure.com`):**

1. Click your avatar → **Personal access tokens**.
2. **+ New Token**.
3. Set scope: **Code → Read** (or **Full access**).
4. Copy the token.

**Azure DevOps Server (on-prem — e.g. `analytics.company.com`):**

1. Open your server URL → user menu → **Security** / **Personal access tokens**.
2. Create a token with **Code (Read)** scope.

```bash
export AZURE_DEVOPS_PAT="your_pat_here"
python -m pr_retriever \
  --url "https://dev.azure.com/org/project/_git/repo/pullrequest/123" \
  --me "your.name" "DOMAIN\\your.user" \
  --out review.xml
```

#### NTLM (on-prem, no PAT)

```bash
python -m pr_retriever \
  --url "https://tfs.company.com/collection/project/_git/repo/pullrequest/123" \
  --me "your.user" \
  --username "DOMAIN\\your.user" \
  --password "your_windows_password" \
  --out review.xml
```

#### Windows integrated auth (on-prem)

On a domain-joined Windows PC with VPN connected, install dependencies and run **without** `--token` or `--username`:

```bash
pip install requests-negotiate-sspi
python -m pr_retriever --url "..." --me "your.user" --out review.xml
```

The tool auto-detects supported API versions on older servers (e.g. `6.1-preview`).

---

## Supported URL formats

| Provider | Example URL |
|----------|-------------|
| GitHub | `https://github.com/owner/repo/pull/123` |
| GitHub Enterprise | `https://github.company.com/owner/repo/pull/123` |
| GitLab | `https://gitlab.example.com/group/subgroup/repo/-/merge_requests/55` |
| Azure DevOps (cloud) | `https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/{id}` |
| Azure DevOps (on-prem) | `https://server/{collection}/{project}/_git/{repo}/pullrequest/{id}` |

Provider is auto-detected from the URL. Use `--provider` to override.

## Project layout

```
pr_retriever/
  cli.py              # Argument parsing and orchestration
  config.py           # Config file loading
  models.py           # Shared data classes
  url_parser.py       # URL detection and parsing
  http.py             # HTTP helpers
  xml_writer.py       # XML output
  utils.py            # Author matching, location formatting
  providers/
    azure.py          # Azure DevOps REST API
    gitlab.py         # GitLab REST API
    github.py         # GitHub GraphQL API
main.py               # Script entry point
requirements.txt
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `404 Project Not Found` (GitLab) | Use the real project path from the browser URL |
| `REST API version ... out of range` (Azure) | Fixed automatically — update to latest version of this tool |
| `401 Unauthorized` | Check token scopes or username/password |
| `Could not detect provider` | Pass `--provider github`, `gitlab`, or `azure` |
| GitHub `GraphQL error` | Token needs **Pull requests: Read** permission |

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
