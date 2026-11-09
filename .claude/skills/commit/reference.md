# Commit standards

According to **Conventional Commits**, semantic commits are a simple
convention for commit messages. The convention defines rules that produce an
explicit commit history and make automated tooling easier.

These commits help you and your team understand what changed in the committed
code.

Identification uses a type word and an emoji that marks whether the commit is
a code change, package update, documentation change, visual change, test, and
so on.

## Type and description

Semantic commits use the structural types below. They tell consumers of the
code what the commit intends.

- `feat` — adds a **new feature** (related to MINOR in semantic versioning).
- `fix` — **fixes a problem** / bug fix (PATCH).
- `docs` — **documentation only** (e.g. README). Does not include code changes.
- `test` — **test changes** (create, update, or remove). Does not include
  production code changes.
- `build` — changes to **build files and dependencies**.
- `perf` — code changes related to **performance**.
- `style` — **code formatting**, semicolons, trailing spaces, lint... No logic
  change.
- `refactor` — **refactors that do not change behavior**.
- `chore` — **maintenance tasks** such as build/admin config or packages (e.g.
  adding an entry to `.gitignore`). No product code change.
- `ci` — **continuous integration** changes.
- `raw` — configuration files, data, feature flags, parameters.

## Recommendations

- Use a type consistent with the change.
- Keep the first-line description to **at most 4 words**.
- Put richer detail in the commit **body**.
- Start the message with an **emoji** that matches the commit.
- Use authentic links only: no shorteners and no affiliate links.

## Commit complements

- **Description:** short summary of the change. Example:
  `correct minor typos in code`
- **Body:** impact, rationale, and notes for the future. Example:
  `see the issue for details on typos fixed.`
- **Footer:** reviewer and Trello/Jira card. Example:
  `Reviewed-by: Elisandro Mello Refs #133`

## Emoji standards

| Commit kind                | Emoji                   |
| -------------------------- | ----------------------- |
| Accessibility              | ♿ `:wheelchair:`       |
| Adding a test              | ✅ `:white_check_mark:` |
| Bumping a submodule        | ⬆️ `:arrow_up:`         |
| Downgrading a submodule    | ⬇️ `:arrow_down:`       |
| Adding a dependency        | ➕ `:heavy_plus_sign:`  |
| Code review changes        | 👌 `:ok_hand:`          |
| Animations and transitions | 💫 `:dizzy:`            |
| Bugfix                     | 🐛 `:bug:`              |
| Comments                   | 💡 `:bulb:`             |
| Initial commit             | 🎉 `:tada:`             |
| Configuration              | 🔧 `:wrench:`           |
| Deploy                     | 🚀 `:rocket:`           |
| Documentation              | 📚 `:books:`            |
| Work in progress           | 🚧 `:construction:`     |
| UI styling                 | 💄 `:lipstick:`         |
| Infrastructure             | 🧱 `:bricks:`           |
| Idea / task list           | 🔜 `:soon:`             |
| Move / rename              | 🚚 `:truck:`            |
| New feature                | ✨ `:sparkles:`         |
| JS package.json            | 📦 `:package:`          |
| Performance                | ⚡ `:zap:`              |
| Refactor                   | ♻️ `:recycle:`          |
| Removing a file            | 🔥 `:fire:`             |
| Removing a dependency      | ➖ `:heavy_minus_sign:` |
| Responsiveness             | 📱 `:iphone:`           |
| Reverting changes          | 💥 `:boom:`             |
| Security                   | 🔒 `:lock:`             |
| SEO                        | 🔍 `:mag:`              |
| Version tag                | 🔖 `:bookmark:`         |
| Approval test              | ✔️ `:heavy_check_mark:` |
| Tests                      | 🧪 `:test_tube:`        |
| Text                       | 📝 `:pencil:`           |
| Typing                     | 🏷️ `:label:`            |
| Error handling             | 🥅 `:goal_net:`         |
| Data                       | 🗃️ `:card_file_box:`    |

## Examples

| Git command                                                     | Result on GitHub                       |
| --------------------------------------------------------------- | -------------------------------------- |
| `git commit -m ":tada: Initial commit"`                         | 🎉 Initial commit                      |
| `git commit -m ":books: docs: README update"`                   | 📚 docs: README update                 |
| `git commit -m ":bug: fix: Infinite loop on line 50"`           | 🐛 fix: Infinite loop on line 50       |
| `git commit -m ":sparkles: feat: Login page"`                   | ✨ feat: Login page                    |
| `git commit -m ":bricks: ci: Dockerfile change"`                | 🧱 ci: Dockerfile change               |
| `git commit -m ":recycle: refactor: Switch to arrow functions"` | ♻️ refactor: Switch to arrow functions |
| `git commit -m ":zap: perf: Faster response time"`              | ⚡ perf: Faster response time          |
| `git commit -m ":boom: fix: Revert inefficient changes"`        | 💥 fix: Revert inefficient changes     |
| `git commit -m ":lipstick: feat: Form CSS styling"`             | 💄 feat: Form CSS styling              |
| `git commit -m ":test_tube: test: Add new test"`                | 🧪 test: Add new test                  |
| `git commit -m ":bulb: docs: Notes on LoremIpsum()"`            | 💡 docs: Notes on LoremIpsum()         |
| `git commit -m ":card_file_box: raw: RAW data for year yyyy"`   | 🗃️ raw: RAW data for year yyyy         |

## Canonical format for this project

```text
:emoji_code: type: short description

optional body

Reviewed-by: Name Refs #123
```
