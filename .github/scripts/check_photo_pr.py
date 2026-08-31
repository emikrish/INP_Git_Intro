"""Decide whether a pull request may be merged without human review.

A pull request qualifies only if it does nothing except add new photos under
``photos/``. That single rule is what makes unattended merging safe: a student
cannot reach the workflows, the README, the collage script, or anyone else's
photo, so the worst a bad actor achieves is an unwanted picture that an
instructor can revert.

This script is invoked by ``.github/workflows/auto-merge-photo.yml``, which runs
on ``pull_request_target``. It therefore runs with a write-scoped token, and it
must treat everything it reads about the pull request as untrusted **data**. It
only ever inspects file metadata through the GitHub API; it never checks out,
reads, or executes anything the pull request contains.

Usage:

    python3 .github/scripts/check_photo_pr.py \
        --repo owner/name --pr 42 --comment-file /tmp/comment.md
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath

PHOTOS_DIR = "photos"
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
ALLOWED_NAME_PUNCTUATION = "-'"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTOS_PER_PR = 5

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangedFile:
    """One entry from the ``GET /repos/{repo}/pulls/{pr}/files`` response.

    Attributes:
        filename: Path within the repository, using forward slashes.
        status: One of ``added``, ``modified``, ``removed``, ``renamed``,
            ``copied``, ``changed``, ``unchanged``.
        sha: Blob SHA of the new content, used to look up the file size.
        size_bytes: Size of the blob, or ``None`` when it could not be resolved.
    """

    filename: str
    status: str
    sha: str | None = None
    size_bytes: int | None = None


@dataclass
class Verdict:
    """The outcome of validating a pull request.

    Attributes:
        ok: True when the pull request may be merged unattended.
        problems: Human-readable reasons it cannot be, in the order found.
        photos: Paths of the photos that would be added.
    """

    ok: bool
    problems: list[str] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)


def parse_changed_files(payload: str) -> list[ChangedFile]:
    """Parse a ``pulls/{pr}/files`` response into :class:`ChangedFile` records.

    Accepts either a single JSON array or several concatenated arrays, which is
    what ``gh api --paginate`` emits for a multi-page response.

    Args:
        payload: Raw JSON text from the GitHub API.

    Returns:
        The changed files, in the order the API listed them.
    """
    decoder = json.JSONDecoder()
    entries: list[dict[str, object]] = []
    index = 0
    text = payload.strip()

    while index < len(text):
        chunk, offset = decoder.raw_decode(text, index)
        if not isinstance(chunk, list):
            raise ValueError(f"expected a JSON array of files, got {type(chunk)}")
        entries.extend(chunk)
        index = offset
        while index < len(text) and text[index].isspace():
            index += 1

    return [
        ChangedFile(
            filename=str(entry.get("filename", "")),
            status=str(entry.get("status", "")),
            sha=str(entry["sha"]) if entry.get("sha") else None,
        )
        for entry in entries
    ]


def is_valid_person_name(stem: str) -> bool:
    """Check a filename stem looks like ``Firstname_Lastname``.

    Letters from any alphabet are accepted, so ``Jose_Garcia``, ``Jose_García``
    and ``Maria_Del_Carmen`` all pass, while ``photo``, ``my photo`` and
    ``IMG_2024`` do not.

    Args:
        stem: Filename with the extension removed.

    Returns:
        True when the stem is two or more name parts joined by underscores.
    """
    parts = stem.split("_")
    if len(parts) < 2:
        return False

    for part in parts:
        if not part or not part[0].isalpha():
            return False
        if not all(ch.isalpha() or ch in ALLOWED_NAME_PUNCTUATION for ch in part):
            return False

    return True


def describe_photo_rules() -> str:
    """Return the markdown reminder appended to every decline comment."""
    return (
        f"A pull request merges itself when **every** file in it is a brand new "
        f"image added directly to `{PHOTOS_DIR}/`:\n\n"
        f"- named `Firstname_Lastname.jpg` (an underscore between your names, no spaces)\n"
        f"- ending in {', '.join(f'`{ext}`' for ext in ALLOWED_EXTENSIONS)}\n"
        f"- under {MAX_PHOTO_BYTES // (1024 * 1024)} MB\n"
        f"- and nothing else in the repository touched\n"
    )


def validate(files: list[ChangedFile]) -> Verdict:
    """Apply the auto-merge rules to a pull request's changed files.

    Args:
        files: Changed files as reported by the GitHub API, with ``size_bytes``
            filled in where known.

    Returns:
        A verdict whose ``problems`` are phrased for a student reading them on
        their own pull request.
    """
    if not files:
        return Verdict(
            ok=False,
            problems=["This pull request does not change any files, so there is nothing to merge."],
        )

    problems: list[str] = []
    photos: list[str] = []

    for changed in files:
        path = PurePosixPath(changed.filename)
        quoted = f"`{changed.filename}`"

        if changed.status != "added":
            problems.append(
                f"{quoted} is **{changed.status}**, not newly added. "
                f"Only brand new files can be merged automatically, so nothing "
                f"already in the repository gets overwritten."
            )
            continue

        if path.parts[:1] != (PHOTOS_DIR,):
            problems.append(
                f"{quoted} is outside `{PHOTOS_DIR}/`. Only photos can be merged "
                f"automatically."
            )
            continue

        if len(path.parts) != 2:
            problems.append(
                f"{quoted} is in a subfolder. Put your photo directly in "
                f"`{PHOTOS_DIR}/`, for example `{PHOTOS_DIR}/Ada_Lovelace.jpg`."
            )
            continue

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(f"`{ext}`" for ext in ALLOWED_EXTENSIONS)
            problems.append(
                f"{quoted} is not an image this repo accepts. Use one of {allowed}."
            )
            continue

        if not is_valid_person_name(path.stem):
            # Renaming is by far the most common fix, so hand over the exact
            # command rather than describing it.
            problems.append(
                f"{quoted} is not named `Firstname_Lastname`. The collage uses "
                f"the filename as your caption, so rename it: "
                f'`git mv "{changed.filename}" '
                f"{PHOTOS_DIR}/Firstname_Lastname{path.suffix.lower()}`"
            )
            continue

        if changed.size_bytes is not None and changed.size_bytes > MAX_PHOTO_BYTES:
            actual = changed.size_bytes / (1024 * 1024)
            limit = MAX_PHOTO_BYTES // (1024 * 1024)
            problems.append(
                f"{quoted} is {actual:.1f} MB, over the {limit} MB limit. "
                f"Export a smaller version and push again."
            )
            continue

        photos.append(changed.filename)

    if not problems and len(photos) > MAX_PHOTOS_PER_PR:
        problems.append(
            f"This pull request adds {len(photos)} photos, more than the "
            f"{MAX_PHOTOS_PER_PR} a single pull request may add automatically."
        )

    if problems:
        return Verdict(ok=False, problems=problems, photos=photos)

    return Verdict(ok=True, photos=photos)


def render_comment(verdict: Verdict) -> str:
    """Render the verdict as the markdown body of a pull request comment.

    Args:
        verdict: Result of :func:`validate`.

    Returns:
        Markdown text addressed to the student who opened the pull request.
    """
    if verdict.ok:
        listed = "\n".join(f"- `{photo}`" for photo in verdict.photos)
        return (
            "## Merged automatically\n\n"
            "Nice work — you just contributed to a shared repository, and nobody "
            "had to approve it.\n\n"
            f"{listed}\n\n"
            "The collage in the README rebuilds itself in a minute or two. "
            "Refresh the front page and look for yourself.\n"
        )

    listed = "\n".join(f"- {problem}" for problem in verdict.problems)
    return (
        "## Not merged yet\n\n"
        "Nothing is broken and nothing is lost. Here is what stopped the merge:\n\n"
        f"{listed}\n\n"
        "---\n\n"
        f"{describe_photo_rules()}\n"
        "Fix it on your laptop, then `git add -A`, `git commit -m \"...\"` and "
        "`git push`. This check runs again on every push. If you are stuck, ask "
        "during the workshop — that is what it is for.\n"
    )


def run_gh(args: list[str]) -> str:
    """Run a ``gh`` command and return its stdout.

    Args:
        args: Arguments following ``gh``.

    Returns:
        Captured stdout.

    Raises:
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    result = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=120
    )
    return result.stdout


def fetch_changed_files(repo: str, pr: int) -> list[ChangedFile]:
    """List the files a pull request changes, via the GitHub API.

    Args:
        repo: ``owner/name`` of the base repository.
        pr: Pull request number.

    Returns:
        The changed files, without sizes resolved yet.
    """
    payload = run_gh(["api", "--paginate", f"repos/{repo}/pulls/{pr}/files"])
    files = parse_changed_files(payload)
    logger.info("Pull request #%d changes %d file(s)", pr, len(files))
    return files


def resolve_sizes(repo: str, files: list[ChangedFile]) -> list[ChangedFile]:
    """Fill in ``size_bytes`` for each file using the git blob API.

    Only called once every other rule has already passed, so at most
    ``MAX_PHOTOS_PER_PR`` blobs are ever looked up and a pull request full of
    junk costs no API calls at all. A blob that cannot be resolved is left as
    ``None``, which :func:`validate` treats as "size unknown" rather than
    failing the student for an API hiccup.

    Args:
        repo: ``owner/name`` of the base repository. Fork pull request blobs are
            reachable here because a fork shares object storage with its parent.
        files: Files to resolve.

    Returns:
        New :class:`ChangedFile` records with sizes attached where available.
    """
    resolved: list[ChangedFile] = []

    for changed in files:
        size: int | None = None
        if changed.sha:
            try:
                raw = run_gh(
                    ["api", f"repos/{repo}/git/blobs/{changed.sha}", "--jq", ".size"]
                )
                size = int(raw.strip())
            except (subprocess.CalledProcessError, ValueError) as error:
                logger.warning(
                    "Could not resolve the size of %s, skipping the size check: %s",
                    changed.filename,
                    error,
                )
        resolved.append(
            ChangedFile(
                filename=changed.filename,
                status=changed.status,
                sha=changed.sha,
                size_bytes=size,
            )
        )

    return resolved


def write_github_output(verdict: Verdict) -> None:
    """Publish the verdict to ``$GITHUB_OUTPUT`` for later workflow steps."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        logger.debug("GITHUB_OUTPUT is unset, skipping step output")
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"verdict={'merge' if verdict.ok else 'decline'}\n")
        handle.write(f"photo_count={len(verdict.photos)}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="base repository, as owner/name")
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument(
        "--comment-file",
        required=True,
        help="path to write the markdown comment body to",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on a successful check of either outcome."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    files = fetch_changed_files(args.repo, args.pr)

    # Validate on metadata alone first. Sizes cost an API call each, so they are
    # only worth resolving once the pull request is otherwise acceptable.
    verdict = validate(files)
    if verdict.ok:
        verdict = validate(resolve_sizes(args.repo, files))

    with open(args.comment_file, "w", encoding="utf-8") as handle:
        handle.write(render_comment(verdict))

    write_github_output(verdict)
    logger.info(
        "Verdict: %s (%d photo(s))",
        "merge" if verdict.ok else "decline",
        len(verdict.photos),
    )
    for problem in verdict.problems:
        logger.info("Problem: %s", problem)

    return 0


if __name__ == "__main__":
    sys.exit(main())
