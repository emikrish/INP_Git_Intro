"""Tests for the auto-merge gate.

Every case is built from the shape the GitHub API actually returns for
``GET /repos/{repo}/pulls/{pr}/files``, so the gate is exercised against real
payloads rather than a simplified stand-in.
"""

from __future__ import annotations

import json

import pytest

from check_photo_pr import (
    MAX_PHOTO_BYTES,
    MAX_PHOTOS_PER_PR,
    ChangedFile,
    is_valid_person_name,
    parse_changed_files,
    render_comment,
    validate,
)

MB = 1024 * 1024


def api_entry(
    filename: str, status: str = "added", sha: str = "a" * 40
) -> dict[str, object]:
    """Build one `pulls/{pr}/files` entry as GitHub returns it for an image.

    Binary files come back with no ``patch`` and zero additions, which is why
    the gate resolves sizes through the blob API instead.
    """
    return {
        "sha": sha,
        "filename": filename,
        "status": status,
        "additions": 0,
        "deletions": 0,
        "changes": 0,
        "blob_url": f"https://github.com/josueortc/INP_Git_Intro/blob/abc/{filename}",
        "raw_url": f"https://github.com/josueortc/INP_Git_Intro/raw/abc/{filename}",
        "contents_url": (
            "https://api.github.com/repos/josueortc/INP_Git_Intro/contents/"
            f"{filename}?ref=abc"
        ),
    }


def photo(filename: str, status: str = "added", size_bytes: int = 512 * 1024):
    """Build a :class:`ChangedFile` with a plausible photo size."""
    return ChangedFile(
        filename=filename, status=status, sha="b" * 40, size_bytes=size_bytes
    )


class TestParseChangedFiles:
    def test_parses_a_single_page(self):
        payload = json.dumps([api_entry("photos/Ada_Lovelace.jpg")])
        files = parse_changed_files(payload)
        assert len(files) == 1
        assert files[0].filename == "photos/Ada_Lovelace.jpg"
        assert files[0].status == "added"
        assert files[0].sha == "a" * 40

    def test_parses_concatenated_pages_from_gh_paginate(self):
        # `gh api --paginate` concatenates one JSON array per page.
        payload = (
            json.dumps([api_entry("photos/Ada_Lovelace.jpg")])
            + "\n"
            + json.dumps([api_entry("photos/Eve_Marder.jpg")])
        )
        files = parse_changed_files(payload)
        assert [f.filename for f in files] == [
            "photos/Ada_Lovelace.jpg",
            "photos/Eve_Marder.jpg",
        ]

    def test_empty_array_is_no_files(self):
        assert parse_changed_files("[]") == []

    def test_rejects_a_non_array_payload(self):
        with pytest.raises(ValueError):
            parse_changed_files('{"message": "Not Found"}')


class TestPersonName:
    @pytest.mark.parametrize(
        "stem",
        [
            "Ada_Lovelace",
            "May-Britt_Moser",
            "Santiago_Ramon-y-Cajal",
            "Maria_Del_Carmen",
            "O'Brien_Fiona",
            "José_García",
        ],
    )
    def test_accepts_real_names(self, stem):
        assert is_valid_person_name(stem)

    @pytest.mark.parametrize(
        "stem",
        [
            "Ada",
            "IMG_2024",
            "photo_1",
            "_Lovelace",
            "Ada_",
            "Ada__Lovelace",
            "Ada Lovelace",
            "",
            "-Ada_Lovelace",
        ],
    )
    def test_rejects_everything_else(self, stem):
        assert not is_valid_person_name(stem)


class TestValidateAccepts:
    def test_one_new_jpg(self):
        verdict = validate([photo("photos/Ada_Lovelace.jpg")])
        assert verdict.ok
        assert verdict.problems == []
        assert verdict.photos == ["photos/Ada_Lovelace.jpg"]

    @pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".JPG", ".PNG"])
    def test_every_allowed_extension(self, extension):
        verdict = validate([photo(f"photos/Ada_Lovelace{extension}")])
        assert verdict.ok, verdict.problems

    def test_a_couple_of_photos_at_once(self):
        verdict = validate(
            [photo("photos/Ada_Lovelace.jpg"), photo("photos/Eve_Marder.png")]
        )
        assert verdict.ok, verdict.problems
        assert len(verdict.photos) == 2

    def test_a_photo_just_under_the_size_limit(self):
        verdict = validate(
            [photo("photos/Ada_Lovelace.jpg", size_bytes=MAX_PHOTO_BYTES)]
        )
        assert verdict.ok, verdict.problems

    def test_unresolved_size_does_not_block_the_student(self):
        # An API hiccup while reading blob metadata should not fail a good PR.
        verdict = validate(
            [ChangedFile("photos/Ada_Lovelace.jpg", "added", sha=None, size_bytes=None)]
        )
        assert verdict.ok, verdict.problems


class TestValidateDeclines:
    def test_an_empty_pull_request(self):
        verdict = validate([])
        assert not verdict.ok
        assert "does not change any files" in verdict.problems[0]

    def test_editing_an_existing_photo(self):
        verdict = validate([photo("photos/Ada_Lovelace.jpg", status="modified")])
        assert not verdict.ok
        assert "not newly added" in verdict.problems[0]

    def test_deleting_someone_elses_photo(self):
        verdict = validate([photo("photos/Eve_Marder.jpg", status="removed")])
        assert not verdict.ok
        assert "not newly added" in verdict.problems[0]

    def test_renaming_a_photo(self):
        verdict = validate([photo("photos/Eve_Marder.jpg", status="renamed")])
        assert not verdict.ok

    def test_a_photo_in_a_subfolder(self):
        verdict = validate([photo("photos/2026/Ada_Lovelace.jpg")])
        assert not verdict.ok
        assert "subfolder" in verdict.problems[0]

    def test_a_photo_outside_the_photos_folder(self):
        verdict = validate([photo("images/Ada_Lovelace.jpg")])
        assert not verdict.ok
        assert "outside" in verdict.problems[0]

    def test_a_badly_named_photo(self):
        verdict = validate([photo("photos/IMG_2024.jpg")])
        assert not verdict.ok
        assert "Firstname_Lastname" in verdict.problems[0]

    @pytest.mark.parametrize(
        "filename",
        [
            # Every one of these is a real filename from a past cohort's pull
            # requests, which is where the naming rule actually gets tested.
            "photos/5ACA4E9A-D94E-44DA-9518-E9F9C840827D_1_105_c.jpeg",
            "photos/Hector Haddock's dog.JPG",
            "photos/DSC05224.JPG",
            "photos/Mountain.jpg",
            "photos/ZimoLi.jpeg",
        ],
    )
    def test_the_decline_hands_over_a_ready_to_run_rename(self, filename):
        verdict = validate([photo(filename)])
        assert not verdict.ok
        problem = verdict.problems[0]
        # Quoted, so a filename containing spaces or an apostrophe still gives
        # the student a command they can paste as-is.
        assert f'git mv "{filename}"' in problem
        assert "photos/Firstname_Lastname" in problem

    @pytest.mark.parametrize(
        "filename",
        [
            # Also real: uppercase extensions straight off a camera or phone.
            "photos/melissa_meng.JPG",
            "photos/Shi_Tang.JPEG",
            "photos/Andy_Ahn.jpeg",
            "photos/Alyssa_Stainton.jpg",
        ],
    )
    def test_real_submissions_that_should_have_merged(self, filename):
        assert validate([photo(filename)]).ok

    def test_an_extensionless_file_is_not_a_photo(self):
        # A past student created `photos/melani` through the GitHub web UI.
        verdict = validate([photo("photos/melani")])
        assert not verdict.ok
        assert "not an image" in verdict.problems[0]

    def test_one_stray_file_blocks_an_otherwise_good_photo(self):
        # Real case: a correctly named photo alongside a camera-named one. The
        # pull request cannot merge partially, so it has to be refused whole.
        verdict = validate(
            [photo("photos/Kunyun_Wang.jpg"), photo("photos/DSC05224.JPG")]
        )
        assert not verdict.ok
        assert len(verdict.problems) == 1
        assert "DSC05224" in verdict.problems[0]

    def test_a_non_image_file_in_photos(self):
        verdict = validate([photo("photos/Ada_Lovelace.pdf")])
        assert not verdict.ok
        assert "not an image" in verdict.problems[0]

    def test_an_oversized_photo(self):
        verdict = validate(
            [photo("photos/Ada_Lovelace.jpg", size_bytes=MAX_PHOTO_BYTES + 1)]
        )
        assert not verdict.ok
        assert "over the 5 MB limit" in verdict.problems[0]
        assert verdict.photos == []

    def test_a_readme_edit_alongside_a_valid_photo(self):
        verdict = validate([photo("photos/Ada_Lovelace.jpg"), photo("README.md")])
        assert not verdict.ok
        assert any("README.md" in problem for problem in verdict.problems)

    def test_tampering_with_the_workflow_itself(self):
        # The attack this gate exists to stop: a fork editing the privileged
        # workflow, or the script the workflow trusts.
        for path in (
            ".github/workflows/auto-merge-photo.yml",
            ".github/scripts/check_photo_pr.py",
            "code/make_collage.py",
        ):
            verdict = validate([photo("photos/Ada_Lovelace.jpg"), photo(path)])
            assert not verdict.ok, path
            assert any(path in problem for problem in verdict.problems)

    def test_a_dotfile_disguised_as_a_photo(self):
        verdict = validate([photo("photos/.hidden.jpg")])
        assert not verdict.ok

    def test_too_many_photos_at_once(self):
        # Digits are not valid in a name, so distinguish them with letters and
        # isolate the count rule from the naming rule.
        files = [
            photo(f"photos/Student_{'X' * (index + 1)}.jpg")
            for index in range(MAX_PHOTOS_PER_PR + 1)
        ]
        verdict = validate(files)
        assert not verdict.ok
        assert "more than the" in verdict.problems[0]

    def test_a_path_traversal_attempt(self):
        verdict = validate([photo("photos/../.github/workflows/evil.jpg")])
        assert not verdict.ok


class TestRenderComment:
    def test_the_success_comment_names_the_photo(self):
        body = render_comment(validate([photo("photos/Ada_Lovelace.jpg")]))
        assert "Merged automatically" in body
        assert "photos/Ada_Lovelace.jpg" in body

    def test_the_decline_comment_explains_and_reassures(self):
        body = render_comment(validate([photo("photos/IMG_2024.jpg")]))
        assert "Not merged yet" in body
        assert "Nothing is broken" in body
        assert "Firstname_Lastname" in body
        assert "git push" in body

    def test_a_hostile_filename_cannot_break_out_of_the_comment(self):
        # Filenames reach the comment body verbatim, so confirm nothing here
        # builds a shell command out of one.
        nasty = "photos/$(whoami)_`id`.jpg"
        body = render_comment(validate([photo(nasty)]))
        assert nasty in body
        assert "Not merged yet" in body


class TestEndToEndPayload:
    def test_a_realistic_good_pull_request(self):
        payload = json.dumps([api_entry("photos/Ada_Lovelace.jpg")])
        files = parse_changed_files(payload)
        sized = [
            ChangedFile(f.filename, f.status, f.sha, size_bytes=900 * 1024)
            for f in files
        ]
        assert validate(sized).ok

    def test_a_realistic_hostile_pull_request(self):
        payload = json.dumps(
            [
                api_entry("photos/Ada_Lovelace.jpg"),
                api_entry(".github/workflows/auto-merge-photo.yml", status="modified"),
            ]
        )
        files = parse_changed_files(payload)
        sized = [
            ChangedFile(f.filename, f.status, f.sha, size_bytes=1024) for f in files
        ]
        verdict = validate(sized)
        assert not verdict.ok
