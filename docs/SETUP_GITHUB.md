# Putting this on GitHub (for the person who owns the repo, once)

Takes about 15 minutes. Needs `git` and Python 3.10+. Replace the bits in CAPITALS.

## 1. Check it works on your machine first

```bash
cd leastpriv                       # the folder you unzipped
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -t .      # expect: OK
python -m leastpriv demo                       # expect: 5 numbered steps, no errors
```

(If PowerShell refuses to activate the venv: `Set-ExecutionPolicy -Scope Process RemoteSigned`, then try again.
You can also skip the venv and just run `pip install PyYAML`.)

## 2. Create the empty repository

GitHub, top right "+", "New repository": name it as you like, choose Private, and **do not** tick "Add a README",
".gitignore" or "license" (this folder already has what it needs). Copy the repository URL.

## 3. Push the first release

```bash
git config --global user.name  "YOUR NAME"        # only if git has never been set up on this machine
git config --global user.email "YOUR GITHUB EMAIL"

git init -b main
git add .
git status                                         # glance: no .venv, no demo folders should be listed
git commit -m "v0.1.0: walking skeleton (log engine, hash chain, contract, watcher, demo)"
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
git tag -a v0.1.0 -m "v0.1.0 walking skeleton"
git push origin v0.1.0
```

Then on GitHub: Releases, "Draft a new release", pick tag `v0.1.0`, paste the 0.1.0 section of `CHANGELOG.md`, publish.
Actions tab: the CI run for this push should turn green within a few minutes (the Windows job is informational;
if only that one is red, tell the team but you can still demo).

Put the repository URL into the paper wherever it says `[github link]`.

## 4. Add the other five

Settings, Collaborators, "Add people" (they need GitHub accounts; each must accept the emailed invitation).
Give them **Write** access.

## 5. Protect `main`

Settings, Branches (or Rules, Rulesets), add a rule for `main`: require a pull request before merging, require
1 approval, require the CI checks to pass. If those options are greyed out (private repositories on a free plan
do not always get branch protection), the same rule still applies by agreement: nobody pushes to `main` directly.

## 6. Labels, milestones, starter issues (optional, saves an hour)

```bash
gh auth login                    # once; needs the GitHub CLI: https://cli.github.com
bash scripts/create_issues.sh    # run inside the repo folder; creates labels, milestones v0.2.0 to v1.0.0, issues
```

Not tested against a live GitHub account (it was written without one), so if a line fails, read the error; it is plain
`gh` commands you can run by hand. On Windows use Git Bash for `bash`.

## 7. Last bits

- Uncomment and fill `.github/CODEOWNERS` with the team's GitHub usernames (optional).
- Decide on a `LICENSE` (none is included on purpose; for coursework many teams leave the repository private
  and unlicensed).
- Share `docs/TASKS.md` with the team: it says who starts where and what each person's first pull request is.
