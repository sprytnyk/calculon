"""Reading GitHub's latest-release reply."""

import json

import pytest

from calculon.updates import Newer, read_latest, version_key


def reply(tag: object) -> bytes:
    return json.dumps({"tag_name": tag}).encode()


@pytest.mark.parametrize(
    ("latest", "current", "result"),
    [
        ("v0.4.0", "0.3.0", Newer("0.4.0")),
        ("v0.4.0", "0.4.0", "up_to_date"),
        ("v0.4.0", "0.5.0", "up_to_date"),  # running a build newer than the release
        ("v0.10.0", "0.9.0", Newer("0.10.0")),  # numbers, not text
        ("v0.4.0", "0.0.0.dev0+v0.4.0.3.g71d4a69", Newer("0.4.0")),  # untagged build
    ],
)
def test_compares_versions(latest: str, current: str, result: object) -> None:
    assert read_latest(reply(latest), current) == result


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"<html>rate limited</html>",
        b"[]",
        b'{"message": "Not Found"}',  # no releases yet
        reply(None),
        reply("nightly"),
    ],
)
def test_anything_odd_is_a_failed_check(body: bytes) -> None:
    assert read_latest(body, "0.4.0") == "failed"


def test_newer_links_to_its_release_page() -> None:
    assert Newer("0.5.0").url == "https://github.com/sprytnyk/calculon/releases/tag/v0.5.0"


def test_version_key() -> None:
    assert version_key("v1.2.3") == (1, 2, 3)
    assert version_key("1.2") is None
