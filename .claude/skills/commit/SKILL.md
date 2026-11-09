---
name: commit
description: >
  Creates git commits using Conventional Commits with emoji (team standard).
  Use when the user asks to commit, write a commit message, or apply semantic
  commits. Handles the full flow from unstaged changes through commit.
allowed-tools: Bash, Read, Grep, Glob
---

# Commit

## When to use

Only when the user asks to commit (or for a commit message) and there are
relevant changes. Do **not** commit automatically.

## Workflow

1. Inspect the repository:
   - `git status`
   - `git diff` and `git diff --cached`
   - `git log -5 --oneline` for tone/style
2. Stage the relevant files for this commit (`git add ...`).
   Never stage secrets (`.env`, credentials, tokens, private keys).
3. Build the message in the team format below.
4. Commit with a heredoc — no `--no-verify`, no `--trailer`, no amend unless
   the user asks and amend rules are safe. Never append agent co-author lines.
5. Run `git status` afterward and report the hash/message.

If there is nothing to commit, say so and stop.

## Message format

```text
:emoji: type: short description

optional body (why / impact)

optional footer (Reviewed-by / Refs #id)
```

Rules:

- **Emoji + type** are required (except the initial commit `:tada:` without a type).
- First-line description after the type: concise — **at most 4 words**.
- Put details in the **body**, not the first line.
- Use authentic links only (no shorteners / affiliate links).
- Do **not** include `Co-authored-by` (Cursor/agent or otherwise) unless the
  user explicitly asks.
- Pick **one** dominant type. If docs and code both changed, prefer the code
  type and mention docs in the body, or split into two commits if the user wants.

### Types

| Type       | Use                                       |
| ---------- | ----------------------------------------- |
| `feat`     | new feature                               |
| `fix`      | bug fix                                   |
| `docs`     | documentation only                        |
| `test`     | tests only                                |
| `build`    | build / dependencies                      |
| `perf`     | performance                               |
| `style`    | formatting / lint (no logic change)       |
| `refactor` | refactor with no behavior change          |
| `chore`    | maintenance / config without product code |
| `ci`       | continuous integration                    |
| `raw`      | configs, data, parameters, fixtures       |

### Main emojis by intent

| Situation       | Emoji                                                    |
| --------------- | -------------------------------------------------------- |
| New feature     | `:sparkles:`                                             |
| Bug fix         | `:bug:`                                                  |
| Documentation   | `:books:`                                                |
| Test            | `:test_tube:` / `:white_check_mark:`                     |
| Refactor        | `:recycle:`                                              |
| Performance     | `:zap:`                                                  |
| Build / package | `:package:` / `:heavy_plus_sign:` / `:heavy_minus_sign:` |
| CI / infra      | `:bricks:` / `:wrench:`                                  |
| Security        | `:lock:`                                                 |
| Initial commit  | `:tada:`                                                 |
| Revert          | `:boom:`                                                 |
| Data / raw      | `:card_file_box:`                                        |

Full emoji table: [reference.md](reference.md).

## Examples

```bash
git commit -m "$(cat <<'EOF'
:sparkles: feat: Login page

EOF
)"
```

```bash
git commit -m "$(cat <<'EOF'
:bug: fix: Infinite list loop

Fix stop condition when the page payload is empty.

Refs #133
EOF
)"
```

```bash
git commit -m "$(cat <<'EOF'
:books: docs: README update

EOF
)"
```

## Safety

- Do not commit secrets (`.env`, credentials, tokens).
- Do not use `git commit --amend` unless the user asks and amend is safe.
- Do not force-push.
- Do not change git config.
- Do **not** add `Co-authored-by`, `Signed-off-by`, or any Cursor/agent
  attribution trailer (e.g. `Co-authored-by: Cursor <cursoragent@cursor.com>`).
- Do **not** pass `--trailer` on `git commit`.
- Commit message = emoji + type + description (+ optional body/Refs only).
  Nothing else in the footer unless the user asks.

## Full material

Types, recommendations, body/footer rules, and emoji table:
[reference.md](reference.md).
