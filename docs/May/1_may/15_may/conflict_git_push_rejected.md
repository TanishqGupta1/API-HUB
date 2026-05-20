# Conflict — Git Push Rejected (Remote Branch Diverged)

**Date:** 2026-05-14 (previous session)
**Type:** Git conflict
**Status:** ✅ Resolved
**Resolution:** `git pull origin Vidhi --no-rebase`, then `git push`

---

## What happened?

After completing work in the previous session, running `git push` was rejected:

```
! [rejected]        Vidhi -> Vidhi (non-fast-forward)
error: failed to push some refs to 'origin'
hint: Updates were rejected because the tip of your current branch is behind
hint: its remote counterpart. Integrate the remote changes (e.g.
hint: 'git pull ...') before pushing again.
```

The local `Vidhi` branch had commits that the remote `origin/Vidhi` didn't have. But the remote also had commits that the local branch didn't have. The two had diverged — they shared a common ancestor but had different commit histories from that point onward.

---

## Why did this happen?

### Someone force-pushed to `origin/Vidhi`

The most likely cause is that `origin/Vidhi` was force-pushed at some point — either by the developer from a different machine, or through a Git GUI or tool that rewrote history. A normal (non-force) push can only reject your push if you're behind, meaning the remote has commits you don't have. But if the remote was force-pushed, it could have different commits at the same positions, making the branches incompatible even if you're "up to date" in terms of count.

When `git push` is rejected with "non-fast-forward," the standard advice is to pull first. But pulling with the default `--rebase` or merge behavior would apply remote changes on top of local ones, or vice versa, and require resolving conflicts.

### Why the branches were different

The developer was working on the `Vidhi` branch on a local machine. The remote `origin/Vidhi` was updated separately — possibly through a different machine, a rebase-and-force-push, or a squash operation in a PR tool. When local commits don't match remote commits at the same point in history, git considers them non-fast-forward and rejects the push.

---

## How does this connect to the project?

The API-HUB project uses a branch-per-developer model: each developer works on their own named branch (`Vidhi`, `Urvashi`, `Shinchana`) and PRs to `main`. These personal branches are long-lived — work accumulates on them across many sessions. 

Because these branches aren't short-lived feature branches, they can diverge in several ways:
- Work from another machine
- A rebase or amend that was force-pushed
- An accidental commit from a GitHub web editor
- A branch reset done through a Git GUI

Any of these produces the "non-fast-forward" rejection.

---

## The fix

```bash
git pull origin Vidhi --no-rebase
```

`--no-rebase` tells git to merge the remote branch into the local branch instead of rebasing. This creates a merge commit that joins both histories. It's less clean than a rebase (it adds a merge commit to the log), but it's safe — it preserves all local commits and all remote commits without rewriting history.

After the merge commit was created and any conflicts resolved, `git push` succeeded normally.

---

## How can this be prevented in the future?

### Option 1: Always pull before starting work

Before starting any new work on `Vidhi`, run:
```bash
git pull origin Vidhi
```

This ensures the local branch is up to date before adding new commits. If the remote was force-pushed since the last pull, you catch it early (before adding more work on top) rather than at push time.

### Option 2: Avoid force-pushing to personal branches

If you need to rebase, squash, or amend commits, do it locally and don't push until you're ready to push the final version. If you've already pushed and want to rewrite history, coordinate with anyone else who might have a copy of that branch.

A better practice for personal branches is: push regularly (at least once per session) and only rebase/amend commits that haven't been pushed yet. Once a commit is on the remote, treat it as immutable.

### Option 3: Use `--force-with-lease` instead of `--force`

If you must force-push (e.g., after a rebase), use:
```bash
git push --force-with-lease
```

This is safer than `git push --force` because it checks that the remote branch is still at the commit you based your rebase on. If someone else pushed to the remote since you last pulled, `--force-with-lease` refuses — preventing you from accidentally wiping their commits.

For now, the `git pull --no-rebase` approach is the right recovery. The merge commit is a small price to pay for a safe, non-destructive resolution.
