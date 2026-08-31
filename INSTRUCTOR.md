# Running this workshop

Students fork the repo, add `photos/Firstname_Lastname.jpg`, and open a pull
request. A workflow checks it and merges it for them. You do not approve
anything.

## How the no-approval part works

`.github/workflows/auto-merge-photo.yml` runs on **`pull_request_target`**
rather than `pull_request`. That choice is the whole trick, for two reasons:

- On `pull_request`, a pull request from a fork gets a read-only `GITHUB_TOKEN`
  no matter what the workflow's `permissions:` block says, so the merge would
  fail with a 403.
- `pull_request` runs from forks are also held by GitHub's "require approval for
  first-time contributors" policy. Every student is a first-time contributor, so
  you would be clicking *Approve and run* thirty times — exactly what we are
  trying to avoid. `pull_request_target` is not subject to that policy.

The tradeoff is that `pull_request_target` runs with a write-scoped token, so it
must never execute anything from the pull request. The workflow therefore checks
out only this repository's default branch and looks at file metadata through the
GitHub API. If you ever edit it, do not add `actions/checkout` with a `ref:`
pointing at the pull request — that is the "pwn request" vulnerability, and
`actions/checkout` v7 refuses it by default for this reason.

`.github/scripts/check_photo_pr.py` holds the rules. A pull request merges only
if **every** file in it is a brand new image directly inside `photos/`, named
`Firstname_Lastname` with an allowed extension, under 5 MB, with at most 5 per
pull request. Anything else gets a comment explaining what to fix and stays
open. That means a student cannot reach the workflows, the collage script, the
README, or anyone else's photo.

After a merge, `.github/workflows/update-collage.yml` rebuilds `collage.jpg`
from `photos/` and commits it, so the README picture stays current.

## One-time setup

1. **Enable Actions.** This repository is a fork of `ahof1704/INP_Git_Intro`,
   and GitHub disables workflows on forks by default. Open the **Actions** tab
   and click *I understand my workflows, go ahead and enable them*. Nothing works
   until you do this.
2. **Allow the token to write.** Settings > Actions > General > Workflow
   permissions, choose **Read and write permissions**.
3. **Do not require reviews on `master`.** Check Settings > Branches and
   Settings > Rules for anything demanding an approving review or a status check
   on `master`, and remove it. A review from `github-actions[bot]` does not
   satisfy a required-review rule, so such a rule would block every automatic
   merge.
4. **If you rename the default branch,** update it in three places, or the
   automation silently stops firing: `branches:` in
   `.github/workflows/auto-merge-photo.yml`, and `branches:` plus the
   `HEAD:master` push refspec in `.github/workflows/update-collage.yml`. Both
   currently assume `master`.
5. **Consider leaving the fork network.** Because this repository is a fork, a
   student's fork is a sibling of Antonio's copy, and GitHub's pull request page
   sometimes offers `ahof1704/INP_Git_Intro` as the base repository. The README
   tells students to check that box, but asking GitHub Support to detach this
   repository from the fork network removes the trap for good. A second, smaller
   consequence: anyone who already forked `ahof1704/INP_Git_Intro` cannot fork
   this one too, since GitHub allows one fork per network per account. They can
   still contribute by adding this repo as a second remote.

### The same setup from the terminal

Steps 1 to 3 are also doable with the GitHub CLI, which is quicker to verify:

```bash
REPO=josueortc/INP_Git_Intro

# 1. Enable Actions on the fork.
gh api -X PUT "repos/$REPO/actions/permissions" -F enabled=true -f allowed_actions=all

# 2. Give GITHUB_TOKEN write access.
gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write -F can_approve_pull_request_reviews=false

# 3. Confirm nothing on master demands a review. A 404 and an empty list are
#    the answers you want.
gh api "repos/$REPO/branches/master/protection"
gh api "repos/$REPO/rulesets"

# Read the first two back.
gh api "repos/$REPO/actions/permissions"
gh api "repos/$REPO/actions/permissions/workflow"
```

Pushing anything under `.github/workflows/` needs the `workflow` scope on your
token, which `gh auth login` does not always request. If a push is rejected with
*refusing to allow an OAuth App to create or update workflow*, that is why:

```bash
gh auth refresh -h github.com -s workflow
```

## Publishing this version to GitHub

One-time, from a clone of `josueortc/INP_Git_Intro`. Delete this section
afterwards.

```bash
git clone https://github.com/josueortc/INP_Git_Intro.git
cd INP_Git_Intro
git checkout -b simplify

# Drop what is no longer used (see the table at the bottom). --ignore-unmatch
# keeps this from stopping half way if a path has already gone.
git rm -r --quiet --ignore-unmatch slides code/make_collage.ipynb \
  code/.ipynb_checkpoints code/.gitignore code/FreeMono.ttf photos/collage.jpg

# Bring in the new version, replacing anything with the same path.
git remote add newversion <URL of the repo holding the new version>
git fetch newversion
git checkout newversion/main -- .

git commit -am "Simplify the repo so students merge their own photo"
```

Check it before you push. The tests should pass and the collage script should
run, since a mistake here breaks the workshop rather than a build:

```bash
pip install -r requirements.txt pytest PyYAML
python -m pytest tests/ -q
python code/make_collage.py
git push -u origin simplify
```

Then merge `simplify` into `master`. The automation only takes effect once it is
on the default branch, because `pull_request_target` always runs the workflow
from there, so nothing happens until then — which makes this safe to review at
your own pace.

## The pull requests already open

There are open pull requests from previous cohorts whose photos were never
merged. Turning on the automation does **not** process them, because the
workflow fires on `opened`, `reopened` and `synchronize` — not on pull requests
that were already sitting there.

To run the check against one, close and immediately reopen it. Those that pass
merge themselves; the rest get a comment explaining what to fix.

A dry run against them, at the time this was written, is a fair preview of what
a live cohort looks like:

| Outcome | Pull requests | Why |
| ------- | ------------- | --- |
| Merges | 4 | Correctly named, including `.JPG` and `.JPEG` in capitals |
| Camera or phone filename | 4 | `DSC05224.JPG`, `5ACA4E9A-...jpeg`, `Mountain.jpg`, `ZimoLi.jpeg` |
| Extra file outside `photos/` | 2 | A notebook, and photos put in `images/` instead |
| Not an image | 1 | An extensionless file created through the web UI |

So expect roughly half of a cohort to trip the naming rule on the first try.
That is the point rather than a problem: previously those pull requests simply
sat unmerged with no feedback, whereas now each student gets an immediate
comment containing the exact `git mv` command to fix it, and the check re-runs
when they push. If you would rather nobody hit it at all, walk through the
naming convention on a slide before they start.

## Before each cohort

- Empty `photos/` (keep `photos/README.md`), then run
  `python code/make_collage.py` and commit, so the collage starts fresh.
- Move the previous collage to `images/collage_previous_year.jpg` if you want to
  keep showing it in the README.
- Rehearse once from a second GitHub account: fork, add a photo, open the pull
  request, and watch it merge itself. This catches a missed setting before
  thirty students hit it at once.

## Rebuilding the collage by hand

```bash
pip install -r requirements.txt
python code/make_collage.py
```

Or from the Actions tab, run **Update collage** via *Run workflow*. The script
is deterministic, so identical photos produce an identical `collage.jpg` and the
workflow commits nothing when nothing changed. With no photos at all it writes a
placeholder, so the README image is never broken.

## Tests

```bash
pip install -r requirements.txt pytest PyYAML
python -m pytest tests/ -v
```

These cover the merge rules (including pull requests that try to touch the
workflows) and the collage builder (grid sizing, EXIF rotation, long names,
determinism). `.github/workflows/tests.yml` runs them on changes to `code/`,
`tests/`, or `.github/`, and its path filter keeps it off student photo pull
requests.

## What changed from the 2025 version

Removed, all of it unused or accidental:

| Path | Why |
| ---- | --- |
| `slides/GitHubIntro_2025.pptx` | Not needed in the repo students clone; keep slides wherever you present from |
| `slides/~$GitHubIntro_2025.pptx` | A stale PowerPoint lock file, committed by accident. `.gitignore` now excludes `~$*` |
| `code/make_collage.ipynb` | Duplicated `make_collage.py` |
| `code/.ipynb_checkpoints/` | Jupyter scratch files, now gitignored |
| `code/.gitignore` | Empty file |
| `code/FreeMono.ttf` | 344 KB font the script never loaded |
| `photos/collage.jpg` | Byte-identical duplicate of the root `collage.jpg` |

`code/make_collage.py` was rewritten because it could not run on current Pillow:
`Image.ANTIALIAS` was removed in Pillow 10, the `../photos` paths only worked
when invoked from inside `code/`, and the caption logic assumed every filename
ended in exactly `.jpeg`. It now also honours EXIF rotation, so photos taken on
a phone are not sideways, and shrinks long names to fit their cell.

The student flow itself is unchanged in shape — fork, clone, add, commit, push,
pull request — because that is the part worth teaching. The only difference is
that nobody has to be watching for the pull request to land.
