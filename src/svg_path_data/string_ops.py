"""Join and append SVG path data strings.

:author: Shay Hill
:created: 2025-09-01
"""

from __future__ import annotations

import dataclasses
import itertools as it
import re
from operator import attrgetter
from typing import TYPE_CHECKING

from paragraphs import par

if TYPE_CHECKING:
    from collections.abc import Iterator

# Match an svg path data string command or number.
_COMMAND_OR_NUMBER = re.compile(
    r"([MmZzLlHhVvCcSsQqTtAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)

# How many floats does each command take? For popping floats from a split SVG path
# datastring.
# fmt: off
_CMD_2_N = {
    "a": 7, "c": 6, "h": 1, "l": 2, "m": 2,
    "q": 4, "s": 4, "t": 2, "v": 1, "z": 0
}
# fmt: on

_CMDS = "MmLlHhVvCcSsQqTtAaZz"


def _is_not_cmd(part: str) -> bool:
    """Check if a part is an SVG command.

    :param part: a part of an SVG path data string
    :return: True if the part is an SVG command, False otherwise
    """
    return part not in _CMDS


def svgd_split(svgd: str) -> list[str]:
    """Split an svg data string into commands and numbers. Validate the string.

    :param svgd: An svg path element d string
    :return: a list of all commands (single letters) and numbers

    The Validation is not exhastive. For instance, the `A` command takes seven number
    parameters (this is checked), but some of those parameters can only be 0 or 1
    (this is not checked). This function checks jut enough to make sure the functions
    in this package work correctly.
    """
    matches = _COMMAND_OR_NUMBER.findall(svgd)
    unmatched = re.sub(_COMMAND_OR_NUMBER, "", svgd).strip()
    if missed_content := re.findall(r"\d|\w", unmatched):
        msg = par(
            f"""Invalid svg path data string. Unrecognized content
            {" ... ".join(missed_content)!r} in input."""
        )
        raise ValueError(msg)
    parts = [x for y in matches for x in y if x]
    if not parts:
        return []

    # validate the parts
    if parts[0] not in "Mm":
        msg = par(
            """Invalid svg path data string. SVG path data must start with a move
            command (M or m)."""
        )
        raise ValueError(msg)
    at_part = 0
    while at_part < len(parts):
        cmd = parts[at_part]
        at_part += 1

        needs_p = _CMD_2_N[cmd.lower()]
        given_p = sum(1 for _ in it.takewhile(_is_not_cmd, parts[at_part:]))
        if needs_p == 0 and given_p != 0:
            msg = par(
                f"""Invalid svg path data string. Command {cmd} takes 0 float
                parameters, got {given_p}."""
            )
            raise ValueError(msg)
        if needs_p and (given_p % needs_p != 0):
            msg = par(
                f"""Invalid svg path data string. Command {cmd} takes (some multiple
                of) {needs_p} float parameters, got {given_p}."""
            )
            raise ValueError(msg)
        at_part += given_p
    return parts


def _format_addition(current_cmd: str, addition: str) -> tuple[str, str]:
    """Format an addition command for joining.

    :param current_cmd: the last command in the existing SVG path data string
    :param addition: the command to add, E.g., "L10 10". This command is has
        presumably already been formatted by "svgd_join".
    :return: the addition command:
        - minus the command letter if it is the same as last_cmd
        - with a leading space if needed
    """
    if addition[0] != current_cmd:
        current_cmd = {"M": "L", "m": "l"}.get(addition[0], addition[0])
        return (current_cmd, addition)
    addition = addition[1:]
    if not addition:
        return (current_cmd, "")
    if addition[0] != "-" and current_cmd and current_cmd not in "Zz":
        addition = " " + addition
    return (current_cmd, addition)


def svgd_join_commands(*parts: str) -> str:
    """Join SVG commands.

    :param parts: full commands (e.g., "M0 0", "L1 1")
    :return: joined SVG path data string
    """
    cmd_list: list[str] = []
    current_cmd = ""
    for addition in parts:
        current_cmd, formatted = _format_addition(current_cmd, addition)
        cmd_list.append(formatted)
    return "".join(cmd_list)


def svgd_join(*parts: str) -> str:
    """Join SVG path data parts.

    :param parts: parts of an SVG path data string
    :return: joined SVG path data string

    Svg datastrings don't need a lot of whitespace.
    """
    joined = " ".join(parts)
    joined = re.sub(r"\s+", " ", joined)
    joined = re.sub(r" -", "-", joined)
    return re.sub(r"\s*([A-Za-z])\s*", r"\1", joined)


@dataclasses.dataclass
class _ShortestPathCandidate:
    """A candidate for the shortest SVG path data string.

    This caches the current length of the string and the last command letter. Finding
    the shortest path requires some optimization because there are giant paths
    created by matplotlib and other svg-generating software.
    """

    cmds: list[str]
    current_len: int
    current_cmd: str

    def __init__(
        self, cmds: list[str] | None = None, current_len: int = 0, current_cmd: str = ""
    ) -> None:
        """Create an empty candidate."""
        self.cmds = cmds or []
        self.current_len = current_len
        self.current_cmd = current_cmd

    def append(self, addition: str) -> None:
        """Append a command to the candidate."""
        current_cmd, formatted = _format_addition(self.current_cmd, addition)
        self.cmds.append(formatted)
        self.current_cmd = current_cmd
        self.current_len += len(formatted)

    def copy(self) -> _ShortestPathCandidate:
        """Create a copy of the candidate.

        :return: a copy of the candidate
        """
        return _ShortestPathCandidate(self.cmds[:], self.current_len, self.current_cmd)

    def tee(self, *additions: str) -> Iterator[_ShortestPathCandidate]:
        """Split the candidate into multiple candidates.

        :yield: transformed self and a copies of self
        """
        if not additions:
            msg = "At least one addition is required."
            raise ValueError(msg)
        copies = [self.copy() for _ in additions[1:]]
        self.append(additions[0])
        yield self
        for copy, addition in zip(copies, additions[1:], strict=True):
            copy.append(addition)
            yield copy


def get_shortest_svgd(*formats: list[str] | list[str | None]) -> str:
    """Get the shortest SVG path data string for a group of commands.

    :param candidates: potential candidates for the shortest SVG path data string
    :param cmds: an iterable of commands with the same command letter
    :return: an SVG path data string for the group of commands
    """
    candidates: list[_ShortestPathCandidate] = [_ShortestPathCandidate()]

    for apps in zip(*formats, strict=True):
        apps_ = [a for a in apps if a is not None]
        candidates = list(it.chain(*(x.tee(*apps_) for x in candidates)))
        # The algorithm never backtracks, so we need only retain one candidate
        # with a last absolute command and one with a last relative command.
        candidates = [
            min(candidates[x :: len(apps_)], key=attrgetter("current_len"))
            for x in range(len(apps_))
        ]
        # If one candidate is shorter, even by one character, the other can be
        # discarded, because--at worst--one character would be needed to switch
        # to the other (relative or absolute) format.
        min_len = min(x.current_len for x in candidates)
        candidates = [x for x in candidates if x.current_len == min_len]
    return "".join(candidates[0].cmds)
