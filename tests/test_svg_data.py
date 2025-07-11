"""Test generating SVG data strings.

:author: Shay Hill
:created: 2024-12-13
"""

# pyright: reportPrivateUsage = false

from typing import TypeVar

import pytest
from paragraphs import par

from svg_path_data.svg_data import (
    PathCommand,
    PathCommands,
    _svgd_join,
    _svgd_split,
    format_svgd_absolute,
    format_svgd_relative,
    format_svgd_shortest,
    get_cpts_from_svgd,
    get_svgd_from_cpts,
)

_T = TypeVar("_T")


def test_multiple_ls_after_mid_m() -> None:
    """Merge multiple L commands after a mid M command."""
    svgd = "M1052 242H536L465 0H2L553 1466h494L1598 0H1124ZM957 559 795 1086 634 559Z"
    cpts = get_cpts_from_svgd(svgd)
    result = format_svgd_shortest(get_svgd_from_cpts(cpts))
    assert_svgd_equal(result, svgd)


def assert_svgd_equal(result: str, expect: str):
    """Assert result == expect and test helper functions.

    This is just a method for running bonus circular tests on other test data.
    """
    assert result == expect
    assert _svgd_join(*_svgd_split(expect)) == expect
    assert get_svgd_from_cpts(get_cpts_from_svgd(expect)) == format_svgd_absolute(
        expect
    )

    for fmt in (
        format_svgd_absolute,
        format_svgd_relative,
        format_svgd_shortest,
    ):
        pre_loop = fmt(expect)
        cpts = get_cpts_from_svgd(pre_loop)
        assert fmt(get_svgd_from_cpts(cpts)) == pre_loop

    shortest = format_svgd_shortest(expect)
    relative = format_svgd_relative(expect)
    absolute = format_svgd_absolute(expect)
    assert shortest == format_svgd_shortest(relative)
    assert shortest == format_svgd_shortest(absolute)
    assert len(shortest) <= len(relative)
    assert len(shortest) <= len(absolute)


class TestCptsWithMidClose:
    def test_mid_close(self):
        """Insert multiple m commands if a path is closed in the middle."""
        cpts = [
            [(0, 0), (1, 0), (2, 0)],
            [(2, 0), (3, 0), (4, 0)],
            [(4, 0), (5, 0), (0, 0)],  # Close the path
            [(0, 5), (1, 5), (2, 5)],  # Another segment starting with M
            [(2, 5), (3, 5), (4, 5)],  # another disjoint segment, but returned to M
            [(3, 9), (4, 9), (5, 9)],  # Another segment starting with M
            [(5, 9), (6, 9), (3, 9)],  # Close the path
        ]
        expect = "m0 0q1 0 2 0t2 0-4 0zm0 5q1 0 2 0t2 0m-1 4q1 0 2 0t-2 0z"
        result = format_svgd_relative(get_svgd_from_cpts(cpts))
        assert_svgd_equal(result, expect)


def test_no_leading_zero():
    """Correctly split numbers without leading zeros."""
    expect = ["M", "0", ".0", "L", "-.2", "-.5", ".3", ".4"]
    assert _svgd_split("M0 .0L-.2-.5 .3 .4") == expect


def test_exponential_notation():
    """Correctly split numbers in exponential notation."""
    assert _svgd_split("M1e-2 2E3 3.4e+5-1") == ["M", "1e-2", "2E3", "3.4e+5", "-1"]


class TestNonAdjacentCurveShorthand:
    """Test that non-adjacent curves get shorthand for equal first two points."""

    def test_t(self):
        """Test that non-adjacent curve shorthand commands are joined."""
        svgd = "M1 2Q1 2 3 4z"
        cmds = PathCommands.from_svgd(svgd)
        assert_svgd_equal(cmds.abs_svgd, "M1 2T3 4Z")

    def test_s(self):
        """Test that non-adjacent curve shorthand commands are not joined."""
        svgd = "M1 2C1 2 3 4 3 4z"
        cmds = PathCommands.from_svgd(svgd)
        assert_svgd_equal(cmds.abs_svgd, "M1 2S3 4 3 4Z")


class TestCloseCurve:
    """Explicitly close with z when a curve closes a path."""

    def test_end_with_curve(self):
        cpts = (
            ((0.5, 0.5), (1.0, 0.0), (2.0, 0.0), (2.5, 0.5)),
            ((2.5, 0.5), (3.0, 1.0), (3.0, 2.0), (2.5, 2.5)),
            ((2.5, 2.5), (2.0, 3.0), (1.0, 3.0), (0.5, 2.5)),
            ((0.5, 2.5), (0.0, 2.0), (0.0, 1.0), (0.5, 0.5)),
        )
        svgd = get_svgd_from_cpts(cpts)
        assert svgd == "M.5 .5C1 0 2 0 2.5 .5S3 2 2.5 2.5 1 3 .5 2.5 0 1 .5 .5Z"

    def test_mid_curve(self):
        """Explicitly close anywhere a curve ends at the the start of a path."""
        cpts = (
            ((0.5, 0.5), (1.0, 0.0), (2.0, 0.0), (2.5, 0.5)),
            ((2.5, 0.5), (3.0, 1.0), (3.0, 2.0), (2.5, 2.5)),
            ((2.5, 2.5), (2.0, 3.0), (1.0, 3.0), (0.5, 0.5)),
            ((0.5, 0.5), (1.0, 0.0), (2.0, 0.0), (2.5, 0.5)),
        )
        svgd = get_svgd_from_cpts(cpts)
        assert svgd == "M.5 .5C1 0 2 0 2.5 .5S3 2 2.5 2.5 1 3 .5 .5ZC1 0 2 0 2.5 .5"


def test_consecutive_l_at_start():
    """Test that consecutive L commands at the start of a path added to m."""
    svgd = "M0 0L1 1L2 2"
    cmds = PathCommands.from_svgd(svgd)
    assert_svgd_equal(cmds.abs_svgd, "M0 0 1 1 2 2")


class TestResolution:
    """Test that resolution is used in finding disjoint segments."""

    def test_resolution_from_cpts(self):
        """Test that resolution is used when generating SVG data from cpts."""
        cpts = [
            [(1 / 3, 2 / 3), (3 / 3, 4 / 3)],
            [(3 / 3, 4 / 3 + 1 / 1000), (5 / 3, 4 / 3 + 2 / 10000)],
        ]
        assert_svgd_equal(
            get_svgd_from_cpts(cpts, resolution=2), "M.33 .67 1 1.33H1.67"
        )

    def test_resolution_from_svgd(self):
        svgd = "M.333333 .67L1 1.33H1.67"
        cmds = PathCommands.from_svgd(svgd, resolution=2)
        assert_svgd_equal(cmds.abs_svgd, "M.33 .67 1 1.33H1.67")


class TestBreakCommand:
    """Test bad paths in Command and Commands."""

    def test_repr(self):
        """Test that the repr of a Command is correct."""
        cmd = PathCommand("m", [0, 0])
        assert repr(cmd) == "Command('M', [0.0, 0.0])"

    def test_empty_cpts(self):
        """Test that an empty list of control points raises a ValueError."""
        with pytest.raises(ValueError):
            _ = PathCommands.from_cpts([])

    def test_arc_command(self):
        """Test that an arc command raises a ValueError."""
        svgd = "M0 0 A 1 1 0 0 1 1 1"
        cmds = PathCommands.from_svgd(svgd)
        with pytest.raises(ValueError) as excinfo:
            _ = cmds.cpts
        assert "Arc commands cannot be converted" in str(excinfo.value)


class TestArcCommand:
    def test_error_on_cpts(self):
        """Raise a ValueError if cpts is called on an arc command."""
        svgd = "M0 0 A 1 1 0 0 1 1 1"
        cmds = PathCommands.from_svgd(svgd)
        with pytest.raises(ValueError) as excinfo:
            _ = cmds.cpts
        assert "Arc commands cannot be converted" in str(excinfo.value)

    def test_relative_cmds_not_relative(self):
        """Test that relative arc commands are not converted to absolute."""
        svgd = "m1 2a3 4 5 6 7 8 9"
        abs_result = PathCommands.from_svgd(svgd).abs_svgd
        rel_result = PathCommands.from_svgd(svgd).rel_svgd
        assert abs_result == "M1 2A3 4 5 6 7 9 11"
        assert rel_result == "m1 2a3 4 5 6 7 8 9"


def test_close():
    """Interpret Z commands when calculating cpts."""
    svgd = "M0 0 L1 1 Z"
    cpts = get_cpts_from_svgd(svgd)
    assert cpts == [[(0.0, 0.0), (1.0, 1.0)], [(1.0, 1.0), (0.0, 0.0)]]


def test_shortest_mixes_rel_and_abs():
    """Test with a shortest path that mixes relative and absolute commands."""
    svgd = "M0 0 L1111 1111L1110 1111L0 1"
    cmds = PathCommands.from_svgd(svgd)
    assert cmds.svgd == "M0 0 1111 1111h-1L0 1"


potrace_output = par(
    """M338 236 c-5 -3 -6 -6 -3 -6 1 -1 2 -2 2 -3 0 -2 1 -2 2 -2 2 0 3 0 4 -1 2 -2 2
    -2 4 -1 1 2 2 2 3 1 2 -3 6 0 6 6 1 8 -4 9 -11 3 l-3 -3 0 4 c0 3 -1 4 -4 2z M170
    235 h1v2V55l0 6c-2 0 -5 -1 -5 -1 -1 -1 -3 -1 -4 -1 -3 0 -13 -5 -14 -6 -1 -1 -2 -2
    -4 -2 -3 0 -6 -2 -4 -3 1 -1 1 -1 0 -1 -1 -1 -1 -1 -1 0 0 1 -1 1 -1 1 -2 0 -5 -4
    -4 -5 0 -1 -1 -1 -2 -2 -1 0 -4 -3 -8 -6 -4 -4 -9 -8 -11 -9 -6 -5 -15 -14 -14 -15
    1 -1 0 -1 -2 -2 -4 0 -8 -4 -11 -10 -4 -7 -1 -6 3 1 2 4 3 5 2 3 0 -2 -1 -4 -2 -5
    -1 0 -1 -1 -1 -1 1 -1 5 1 5 2 0 1 0 1 1 1 1 0 1 0 1 -1 -2 -2 2 -8 4 -8 0 1 2 1 2
    1 1 0 1 1 1 1 0 1 2 4 4 7 5 6 5 6 -2 7 l-4 1 5 0 c4 -1 5 0 7 2 2 2 4 3 4 3 1 0 0
    -1 -2 -3 -3 -3 -3 -3 -1 -5 1 -1 1 -1 0 -1 -2 1 -11 -10 -9 -12 2 -3 6 -2 9 3 3 2 5
    4 6 3 1 0 0 -1 -3 -3 -6 -5 -8 -8 -6 -10 2 -1 3 -1 4 2 3 6 9 9 12 6 2 -1 6 -2 6 0
    0 1 -6 6 -7 6 -3 0 2 5 7 8 3 1 4 6 3 9 -1 1 8 5 11 5 1 0 0 -1 -2 -2 -7 -2 -11 -9
    -7 -10 4 -2 12 5 12 10 0 2 0 2 1 1 0 -1 1 -2 0 -3 0 -1 0 -1 1 0 2 1 1 4 -2 5 -2 0
    -2 0 0 1 1 1 3 3 4 4 0 1 1 3 2 3 0 0 1 0 2 0 0 1 0 1 -1 1 0 -1 -1 -1 -1 0 0 0 2 1
    4 2 2 1 4 3 4 3 0 1 0 1 1 0 2 -1 8 2 8 4 0 1 2 3 4 4 2 1 4 2 4 2 0 -1 -1 -2 -3 -3
    -2 0 -3 -1 -3 -2 1 0 0 -2 -2 -3 -3 -2 -2 -4 2 -2 4 3 5 2 1 0 -4 -3 -10 -9 -9 -9 0
    0 1 1 3 1 1 1 3 2 4 2 2 0 4 1 6 4 3 3 5 4 5 3 1 -1 2 0 4 1 l2 3 -2 -3 s1 2 3 4s1
    2 3 4t1 2t8 5 c-1 -2 -2 -3 -3 -2 -2 0 -9 -6 -9 -8 1 -3 4 -2 7 1 2 2 4 3 4 2 1 -1
    1 -1 1 0 1 0 2 1 2 0 2 0 17 13 17 14 -1 1 6 5 8 5 2 1 10 3 12 4 3 1 5 1 5 0 0 -1
    2 -2 6 -3 3 -1 8 -3 10 -5 3 -2 5 -3 6 -3 1 0 1 -1 1 -1 0 -1 1 -2 1 -3 1 0 3 -4 5
    -8 2 -4 4 -7 5 -7 0 0 1 -1 2 -2 0 -2 1 -2 1 -1 1 1 0 2 -2 5 -1 2 -2 3 -1 2 1 -1 2
    -1 2 0 0 0 1 1 1 1 1 0 1 0 1 1 0 2 1 2 2 1 3 -2 4 0 1 2 -1 1 -2 3 -2 3 0 1 -1 2
    -1 3 -2 0 -2 3 0 3 2 1 2 1 1 -1 0 -3 5 -10 9 -11 1 0 2 1 1 1 0 0 1 1 2 2 0 1 1 2
    1 3 0 2 3 3 16 3 5 1 6 1 4 0 -12 0 -14 -1 -14 -3 1 -3 4 -5 6 -3 1 1 4 1 6 2 1 0 4
    0 5 1 1 0 2 0 2 -1 0 -1 0 -2 -1 -2 -1 0 -1 0 -1 -1 0 -1 1 0 2 1 2 1 3 2 2 2 0 1 1
    1 2 0 2 -1 2 -1 0 -3 -2 -1 -3 -4 -1 -3 0 1 2 0 3 -1 2 -1 3 -1 3 0 0 1 1 1 3 1 4 0
    5 1 2 3 -2 1 -2 1 0 1 2 0 3 0 4 1 0 1 1 1 1 1 1 0 0 -1 -1 -2 -1 -2 -1 -2 0 -3 1
    -1 1 -1 2 0 1 1 1 1 2 0 2 -2 5 0 5 3 -1 4 0 6 1 4 1 -1 1 -1 1 1 0 2 -1 3 -1 2 -1
    0 -1 2 -2 4 0 2 -1 3 -2 3 0 -1 -1 0 -2 1 -1 0 -1 1 -1 1 1 0 0 1 0 3 -2 3 -5 4 -5
    2 0 -1 -1 -1 -1 1 0 1 -1 1 -1 0 0 -1 0 -1 -2 0 -1 2 -4 2 -17 2 -8 0 -15 0 -16 1
    -2 0 -15 -3 -19 -4 -2 -2 -3 -1 -8 0 -4 1 -7 2 -8 1 -1 0 -2 0 -2 1 0 1 -6 3 -8 3
    -1 0 -2 0 -2 1 -1 1 -1 1 -1 0 0 -1 -2 -1 -11 0 -2 0 -2 0 1 1 3 1 2 1 -2 1 -4 -1
    -7 -1 -7 -2 0 -1 -1 -1 -2 0 -1 1 -2 1 -3 0 -2 -2 -5 -3 -3 -1 0 1 -4 1 -9 -1 -3 -1
    -5 -1 -5 0 -1 1 -3 1 -5 1 -2 0 -6 1 -9 2 -4 0 -7 1 -8 1 -1 0 -4 -1 -6 -1Q1 2 3
    4Q4 2 5 3z"""
)


class TestCloseWithAxis:
    """Test that Z replaces V or H commands for closing paths."""

    def test_close_with_h(self):
        """Test that a horizontal line is closed with Z."""
        result = get_svgd_from_cpts([[(0, 0), (1, 0)], [(1, 0), (0, 0)]])
        assert result == "M0 0H1Z"

    def test_close_with_v(self):
        """Test that a horizontal line is closed with Z."""
        result = get_svgd_from_cpts([[(0, 0), (0, 1)], [(0, 1), (0, 0)]])
        assert result == "M0 0V1Z"


class TestPotraceOutput:
    def test_cycle(self) -> None:
        iterations: list[str] = []
        iterations.append(format_svgd_relative(potrace_output))
        iterations.append(format_svgd_relative(iterations[-1]))
        assert iterations[0] == iterations[1]
