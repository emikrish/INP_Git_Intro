# How do I use GitHub?

![confused](images/huh-confused.gif)

Welcome to the INP GitHub intro. By the end of this page you will have made a
real contribution to a real repository: **a photo of yourself, merged into this
repo by you.** No one has to approve it. A bot checks your change and merges it
for you, usually within a minute.

Then your face shows up in the collage at the bottom of this page.

---

## Before you start

- Create a GitHub account: [github.com/join](https://github.com/join)
- Install git for your operating system: [installation guide](https://github.com/git-guides/install-git)
- Create a personal access token: [how to](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
  When git asks you for a *password*, paste the token instead. Your GitHub
  account password will not work.

## The commands you will use today

| Command | What it does |
| ------- | ------------ |
| `git clone <url>` | Download a copy of a repository onto your computer |
| `git status` | Show which files you have changed |
| `git add -A` | Stage all your changes, so git knows what to save |
| `git commit -m "message"` | Save the staged changes, with a note about why |
| `git push` | Send your saved changes up to GitHub |
| `git pull` | Bring down changes other people made |

That is genuinely most of what daily git looks like. For everything else, keep
[this cheat sheet](https://education.github.com/git-cheat-sheet-education.pdf)
open.

---

## Add yourself to the collage

### 1. Fork this repository

A **fork** is your own copy of someone else's repository. You can do whatever
you like in your fork without affecting the original.

Click **Fork** at the top right of this page, then **Create fork**.

![fork button](images/fork_button.jpeg)

### 2. Clone your fork

Cloning downloads your fork onto your laptop. On **your fork's** page (the URL
should have *your* username in it), click the green **Code** button and copy the
HTTPS URL.

![code button](images/code-button.png)

![clone url](images/https-url-clone.png)

Then in a terminal:

```bash
git clone https://github.com/YOUR-USERNAME/INP_Git_Intro.git
cd INP_Git_Intro
```

**Check you cloned the right one before going further.** This is the single most
common thing to get wrong, and it is much easier to catch now than after you
have made your commit:

```bash
git remote -v
```

Both lines must contain **your** GitHub username. If they say `josueortc`, you
cloned this repository rather than your fork — see
[Permission denied when pushing](#permission-denied-when-pushing) at the bottom.
It is a one-line fix and you will not lose any work.

### 3. Add your photo

Put one photo of yourself into the `photos/` folder. The filename matters,
because the bot uses it to label your photo in the collage:

```
photos/Firstname_Lastname.jpg
```

For example, `photos/Ada_Lovelace.jpg`. Rules:

- **One photo**, directly inside `photos/` — not in a subfolder
- Named `Firstname_Lastname` with a single underscore between the two names
- Ending in `.jpg`, `.jpeg`, or `.png`
- Smaller than 5 MB
- Change nothing else in the repository

### 4. Check what you changed

```bash
git status
```

You should see your photo listed as an untracked file. If you see other files
listed too, the bot will not merge your change, so undo those first.

### 5. Save and upload it

```bash
git add -A
git commit -m "Add photo of Firstname Lastname"
git push
```

### 6. Open a pull request

A **pull request** asks a repository to take your changes. Go to your fork on
GitHub and click **Contribute**, then **Open pull request**.

> **Check the boxes at the top of the page before you submit.** The left one
> (`base repository`) must say **`josueortc/INP_Git_Intro`**. If it says
> anything else, click it and pick `josueortc/INP_Git_Intro` from the list. This
> repository has relatives on GitHub, and the page sometimes guesses the wrong one.

![open a pull request](images/pull-request-start-review-button.png)

Click **Create pull request**.

### 7. Watch it merge itself

Within about a minute a bot will check your pull request. If you followed the
rules above, it merges your photo and says so in a comment. **You are done —
you have contributed to a shared repository.**

If something was off, the bot comments explaining exactly what, and leaves your
pull request open. Fix it on your laptop, then `git add -A`, `git commit`, and
`git push` again. The bot rechecks every time you push. Nothing is broken and
nothing is lost.

---

## If the bot did not merge your pull request

It only merges pull requests that do nothing except add new photos. The usual
reasons it declines:

| Bot says | What happened | Fix |
| -------- | ------------- | --- |
| Not a new file | You edited or replaced an existing photo | Use a filename nobody has used yet |
| Wrong folder | Your photo is not directly inside `photos/` | Move it to `photos/Firstname_Lastname.jpg` |
| Bad filename | Missing the underscore, has spaces, or the wrong extension | Rename to `Firstname_Lastname.jpg` |
| Too large | The photo is over 5 MB | Export a smaller version |
| Other files changed | You also changed the README, workflows, or anything else | Undo those changes and push again |

None of these are a problem, and asking for help is not cheating. That is what
the workshop is for.

## Permission denied when pushing

If `git push` fails with something like:

```
remote: Permission to josueortc/INP_Git_Intro.git denied to your-username.
fatal: unable to access '...': The requested URL returned error: 403
```

you cloned **this** repository instead of your own fork. Nobody but the
instructor can push here, which is the whole reason you fork first: the fork is
yours to push to, and the pull request is how you offer it back.

Your commit is safe. Point the repository at your fork and push again:

```bash
# 1. Make sure you have a fork. Click Fork at the top of this page if not.

# 2. Check what you are currently pointed at.
git remote -v

# 3. Repoint it at your fork, using your own username.
git remote set-url origin https://github.com/YOUR-USERNAME/INP_Git_Intro.git

# 4. Confirm it changed, then push.
git remote -v
git push -u origin HEAD
```

Then continue from [step 6](#6-open-a-pull-request) and open your pull request.

### A different error: authentication

If instead you see `Support for password authentication was removed` or you are
asked for a username and password over and over, the repository is fine but your
credentials are not. Your GitHub account password will not work; you need a
[personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
pasted in place of the password. The
[GitHub CLI](https://cli.github.com/) handles this for you if you would rather
not manage tokens:

```bash
gh auth login
```

## The collage

This rebuilds itself every time a photo is merged. Refresh the page a minute
after your pull request goes in and look for yourself.

![collage](collage.jpg)

Last year's cohort:

![previous collage](images/collage_previous_year.jpg)

---

## For instructors

Setup and maintenance notes live in [INSTRUCTOR.md](INSTRUCTOR.md).
