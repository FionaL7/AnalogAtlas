# AGENTS.md

How we work. For humans and AI agents.

## Team

- 2 people: Fiona and Rishabh.
- 3 devices, each running a coding agent:
  - `fiona-mac`: Fiona's Mac
  - `rishabh-win`: Rishabh's Windows laptop
  - `device-3-mac`: a Mac shared by both

### Which device am I?

- Each device has an untracked `CLAUDE.local.md` in the repo root that names the device, e.g. `This device is fiona-mac.`
- No such file? Follow [New device setup](#new-device-setup).
- On `device-3-mac`, also ask which person you're working for at the start of each session.

### New device setup

On a device with no `CLAUDE.local.md` in the repo root:

1. Ask the human which device this is: `fiona-mac`, `rishabh-win` or `device-3-mac`.
2. Create `CLAUDE.local.md` in the repo root. It's gitignored; never commit it. Contents:
   ```
   This device is <device>. Sign issue comments with [<device>] and use the device:<device> label.
   ```
3. Check that `gh auth status` works. If it doesn't, ask the human to run `gh auth login`.
4. Set up Python with the steps in [docs/PLAN.md](docs/PLAN.md#setup-on-a-new-machine).

## Start of every session

1. Read the pinned **Team log** issue.
2. Check open issues: `gh issue list`.
3. Read the docs you need:
   - `docs/PLAN.md`: status and decisions
   - `docs/REQUIREMENTS.md`: what we must deliver
   - `docs/BRIEF.md`: the challenge text
   - `docs/RESOURCES.md`: data and tools

## Communication

- **GitHub Issues is the only channel between agents.** Read and write it with `gh`.
- Work on a task → comment on that task's issue.
- News for everyone → comment on the pinned Team log issue.
- Commit messages record what changed. They're not for messages to other agents.

## Requests between people

- Need something from a person (an env value, a file, a decision)? Comment on the relevant issue and @mention them (`@FionaL7` or `@RishabhSpark`). Add the label `needs:fiona` or `needs:rishabh`.
- The label names a person, not a device.
- Whoever fulfills the request removes the label and replies "done".
- To get phone notifications: install GitHub Mobile and set Watch → All activity on this repo.

## Tasks are GitHub Issues

- **One issue per task.** The body has the goal and a "Done when" list.
- **Assignee is optional** when an issue is created.
- **Claim before starting:** assign the person you're working for, and add the labels `in-progress` and your device (`device:fiona-mac`, `device:rishabh-win` or `device:device-3-mac`). Don't start an issue that's already `in-progress`.
- **Post progress as comments on the task's issue:** started, decisions, blockers, done. Start each comment with your device, e.g. `[device-3-mac]`.
- **Blocked:** add the `blocked` label and say what you need.
- **To close:** comment what was done, a link to the commit or PR, and how to use it. Then close the issue.

## Team log (pinned issue)

For news other agents need: API changes, where data lives, decisions, setup gotchas. One comment per item, signed with your device.

## Writing docs and issues

- Keep it very short, simple and to the point.
- Easy for both humans and AI to read.
- Put the point first. Use bullets rather than paragraphs. No filler.
- Link to a doc instead of repeating what it says.

## Skills for repeated tasks

- When a task will happen again and again (e.g. deploying, uploading data, rebuilding the index), make it a Claude Code skill.
- Put skills in the repo at `.claude/skills/<name>/SKILL.md`, so all three devices get them.
- Keep each skill short: when to use it, the steps, and how to check it worked.
- Before creating one, tell the human what it will do.

## Ask when unsure

If a task, requirement or decision is unclear, ask a human before acting. If others depend on the answer, ask in the issue or the Team log.

## Git

- Work on a branch per task, or push small changes straight to `main`.
- No large pushes to `main`. Pull before you push.
- `data/` and `.venv/` are not in git.

## Data

Large data files aren't in git. How to share them is **not decided yet**; see [docs/PLAN.md](docs/PLAN.md#open-decisions).
