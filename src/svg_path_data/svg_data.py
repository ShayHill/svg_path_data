"""Convert between control points and SVG path data.

The functions you may need:

`get_svgd_from_cpts(cpts: Iterable[Sequence[Sequence[float]]]) -> str`
    - Convert a list of lists of Bezier control points to an SVG path data string.

`get_cpts_from_svgd(svgd: str) -> list[list[tuple[float, float]]`
    - Convert an SVG path data string to a list of lists of Bezier control points.

`format_svgd_absolute(svgd: str) -> str`
    - Convert an SVG path data string to a relative one.

`format_svgd_relative(svgd: str) -> str`
    - Convert an SVG path data string to an absolute one.

`format_svgd_shortest(svgd: str) -> str`
    - Convert an SVG path data string to the shortest form.

:author: Shay Hill
:created: 2025-06-18
"""

from __future__ import annotations

import enum
import functools as ft
import itertools as it
from string import ascii_lowercase
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from svg_path_data.float_string_conversion import format_number
from svg_path_data.string_ops import (
    get_shortest_svgd,
    svgd_join,
    svgd_join_commands,
    svgd_split,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

_T = TypeVar("_T")

# number of points in a linear command (L, H, V, Z)
_N_LINEAR = 4


class RelativeOrAbsolute(str, enum.Enum):
    """Enum to indicate whether a path is relative or absolute or a combination."""

    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    SHORTEST = "shortest"


def _comp_iterables(a_iter: Iterable[Any], b_iter: Iterable[Any]) -> bool:
    """Compare two iterables for equality.

    :param a_iter: first iterable
    :param b_iter: second iterable
    :return: True if the iterables are equal, False otherwise
    """
    return all(a == b for a, b in it.zip_longest(a_iter, b_iter, fillvalue=None))


def _chunk_pairs(items: Sequence[_T]) -> Iterator[tuple[_T, _T]]:
    """Yield pairs of items from a sequence.

    :param items: a sequence of items
    :return: None
    :yield: pairs (without overlap) of items from the sequence
    :raises ValueError: if the number of items is not even
    """
    if len(items) % 2 != 0:
        msg = f"Expected an even number of items, got {len(items)}."
        raise ValueError(msg)
    for i in range(0, len(items), 2):
        yield (items[i], items[i + 1])


# What is the degree of each basic command? For selecting a command in
# PathCommand.__init__
_N_2_CMD = {2: "L", 4: "Q", 6: "C"}

# How many floats does each command take? For popping floats from a split SVG path
# datastring.
# fmt: off
_CMD_2_N = {
    "a": 7, "c": 6, "h": 1, "l": 2, "m": 2,
    "q": 4, "s": 4, "t": 2, "v": 1, "z": 0
}
# fmt: on


def _take_n_floats(parts: list[str], n: int) -> Iterable[float]:
    """Pop n floats from a list of strings.

    :param parts: a list of strings
    :param n: the number of floats to pop
    :return: a tuple of the remaining parts and the popped floats
    """
    return map(float, (parts.pop() for _ in range(n)))


def _is_monotonic(seq: Sequence[float]) -> bool:
    """Check if a list is monotonic (entirely non-increasing or non-decreasing)."""
    increasing = decreasing = True
    for left, right in it.pairwise(seq):
        if left > right:
            decreasing = False
        elif left < right:
            increasing = False
    return increasing or decreasing


def _is_linear(
    pts: list[tuple[float, float]], formatter: Callable[[str | float], str]
) -> bool:
    """Check if a set of points is linear.

    :param pts: a list of tuples of the x and y coordinates of the points
    :param formatter: a function to format numbers to strings. This effectively
        rounds the results to provide an epsilon.
    :return: True if the points are linear, False otherwise
    """
    if len(pts) < 3:
        return True
    xs = [float(formatter(x)) for x, _ in pts]
    ys = [float(formatter(y)) for _, y in pts]
    if not (_is_monotonic(xs) and _is_monotonic(ys)):
        return False
    vx = float(xs[-1]) - float(xs[0])
    vy = float(ys[-1]) - float(ys[0])
    if vx == 0 or vy == 0:
        return True
    for x, y in zip(xs[1:-1], ys[1:-1], strict=True):
        xt = (float(x) - float(xs[0])) / vx
        yt = (float(y) - float(ys[0])) / vy
        if formatter(yt) != formatter(xt):
            return False
    return True


class PathCommand:
    """A command with points.

    The str properties strip out unnecessary commands and points.
    """

    def __init__(
        self,
        cmd: str | None,
        vals: Iterable[float],
        prev: PathCommand | None = None,
        resolution: int | None = None,
    ) -> None:
        """Create a command with points.

        :param cmd: the SVG command (e.g. "M", "L", "Q", "C")
        :param vals: float after the svg command
        :param prev: the previous command in the linked list

        Accepts any command known to SVG, "mMlLhHvVcCsSqQtTaAzZ", but will convert
        all commands to "mMlLQqCcAa".
        """
        self.__rel_vals: list[float] = []
        self.__abs_vals: list[float] = []
        self.__rel_strs: list[str] = []
        self.__abs_strs: list[str] = []

        if cmd and cmd[0] in ascii_lowercase:
            self.__rel_vals = list(vals)
            self.cmd = cmd.upper()
        else:
            self.__abs_vals = list(vals)
            self.cmd = cmd or _N_2_CMD[self._n]

        # update values inherited from the previous command
        self.prev = prev
        if self.cmd == "M" and prev and prev.cmd == "M":
            self.prev = prev.prev  # skip redundant move commands
        self.next: PathCommand | None = None

        if prev:
            prev.next = self
            self.resolution = resolution or prev.resolution
            self._current_point = prev.abs_vals[-2], prev.abs_vals[-1]
            self._current_point_str = prev.abs_strs[-2], prev.abs_strs[-1]

        else:
            self.resolution = resolution
            self._current_point = 0.0, 0.0
            self._current_point_str = "0", "0"

        # expand shorthand
        if self.cmd in "TS":
            self.__abs_vals = [*self._implied_cpt, *self.abs_vals]
            self.__rel_vals = []
            self.cmd = {"T": "Q", "S": "C"}[self.cmd]
        if self.cmd == "V":
            self.__abs_vals = [self._current_point[0], *self.abs_vals]
            self.__rel_vals = []
            self.cmd = "L"
        if self.cmd == "H":
            self.__abs_vals = [*self.abs_vals, self._current_point[1]]
            self.__rel_vals = []
            self.cmd = "L"

        # identify linear curves
        if self.cmd in "QC" and _is_linear(self.cpts, self.format_number):
            self.cmd = "L"
            self.__abs_vals = self.__abs_vals[-2:]
            self.__rel_vals = []

        self.path_open = self._get_path_open()

    @classmethod
    def append(
        cls,
        cmd: str | None,
        vals: Iterable[float],
        prev: PathCommand | None = None,
        resolution: int | None = None,
    ) -> PathCommand:
        """Append a command to the CommandList linked list.

        Init has several quality checks, but it does not have the remedy of skipping
        a node. This method will create a candidate next node and potentially skip
        it.
        """
        vals = tuple(vals)
        instance = cls(cmd, vals, prev, resolution)
        if prev is None:
            return instance
        # If the previous command was closed by an (arguably unnecessary) Z, insert a
        # move command to the current point.
        if (
            instance.cmd != "M"
            and prev.get_svgd(RelativeOrAbsolute.ABSOLUTE)[-1] == "Z"
        ):
            prev = cls("m", [0, 0], prev, resolution)
            instance = cls(cmd, vals, prev, resolution)

        if instance.cmd in "MA":
            return instance
        if (
            instance.cmd == "L"
            and prev.cmd == "L"
            and _is_linear([*prev.cpts, instance.cpts[1]], instance.format_number)
        ):
            # skip previous L command
            return cls(cmd, vals, prev.prev, resolution)
        if all(x == "0" for x in instance._rel_strs):
            # zero-length command; remove it from the linked list
            prev.next = instance.next
            return prev
        return instance

    def __repr__(self) -> str:
        """Get the SVG command and points for this command.

        :return: the SVG command and points as a string
        """
        return f"Command('{self.cmd}', {self.abs_vals})"

    def format_number(self, number: float | str) -> str:
        """Format a number to a string with the correct precision.

        :param number: the number to format
        :return: the formatted number as a string
        """
        return format_number(number, self.resolution)

    @property
    def _n(self) -> int:
        """Get the number of float values in this command.

        :return: the degree of the command
        """
        return max(len(self.__abs_vals), len(self.__rel_vals))

    def _get_path_open(self) -> tuple[float, float]:
        """Get the x and y coordinates of the last movement command.

        :return: a tuple of the x and y coordinates of the first point

        This is used to determine when a command closes a path so a closing L can
        become a Z or a closing curve will be followed by an explicit Z.
        """
        if self.cmd in "mM":
            x, y = self.abs_vals[:2]
            return x, y
        if self.prev is None:
            msg = "Invalid path command. Starts with a non-move command."
            raise ValueError(msg)
        return self.prev.path_open

    @property
    def does_close(self) -> bool:
        """Check if this command closes the path.

        :return: True if this command closes the path, False otherwise
        """
        if self.cmd == "M":
            return False
        return _comp_iterables(self.abs_vals[-2:], self.path_open)

    @property
    def _extended_current_point(self) -> Iterator[float]:
        """Extend the current point over all values in the command.

        :return: a tuple of the x and y coordinates of the last point in the previous
            command, extended to the current command's degree. This is used to
            convert between absolute and relative coordinates.
        """
        if self.cmd == "A":
            yield from (0, 0, 0, 0, 0, *self._current_point)
        elif self.cmd == "V":
            yield self._current_point[1]
        else:
            yield from it.islice(it.cycle(self._current_point), self._n)

    @property
    def _implied_cpt(self) -> tuple[float, float]:
        """Get point that would be injected in a tTsS command.

        :return: a tuple of the x and y coordinates of the last control point of the
        previous curve projected through current point OR the current point if the
        commands are not adjacent curve commands with the same degree.
        """
        if self.cmd not in "QTCS":
            msg = "Request for implied control point on non-curve command."
            raise AttributeError(msg)
        if (
            self.prev
            and self.prev.cmd in "QTCS"
            and (self.prev.cmd in "QT") == (self.cmd in "QT")
        ):  # adjacent curve commands with the same degree
            x0, y0, x1, y1 = self.prev.abs_vals[-4:]
            tan_x, tan_y = x1 - x0, y1 - y0
            cur_x, cur_y = self._current_point
            return cur_x + tan_x, cur_y + tan_y
        return self._current_point

    @ft.cached_property
    def implied_cpt_str(self) -> tuple[str, str]:
        """Get the implied control point as a string.

        :return: the implied control point as a string. For comparison with Q or C
        point strings to determine if a T or S shortcut command can be used.
        """
        x, y = map(self.format_number, self._implied_cpt)
        return x, y

    @property
    def abs_vals(self) -> list[float]:
        """Get the absolute values of the points.

        :return: the absolute values of the points

        At least one of a or r will ALWAYS be a float. The `or 0` is for the linter.
        """
        if self.__abs_vals:
            return self.__abs_vals
        self.__abs_vals = [
            r + c
            for r, c in zip(self.__rel_vals, self._extended_current_point, strict=True)
        ]
        return self.__abs_vals

    @property
    def abs_strs(self) -> list[str]:
        """Get the relative values of the points as strings.

        :return: the relative values of the points as strings
        """
        if self.__abs_strs:
            return self.__abs_strs
        self.__abs_strs = [self.format_number(x) for x in self.abs_vals]
        return self.__abs_strs

    @property
    def _rel_vals(self) -> list[float]:
        """Get the relative values of the points.

        :return: the relative values of the points
        """
        if self.__rel_vals:
            return self.__rel_vals
        self.__rel_vals = [
            a - c
            for a, c in zip(self.__abs_vals, self._extended_current_point, strict=True)
        ]
        return self.__rel_vals

    @property
    def _rel_strs(self) -> list[str]:
        """Get the relative values of the points as strings.

        :return: the relative values of the points as strings
        """
        if self.__rel_strs:
            return self.__rel_strs
        self.__rel_strs = [self.format_number(x) for x in self._rel_vals]
        return self.__rel_strs

    @ft.cached_property
    def _str_cmd(self) -> str:
        """Get the SVG command for this command as it will be used in the SVG data.

        :return: the SVG command (e.g. "M", "L", "Q", "C", "V", "H", ...)

        If a path command can be shortened, return the shorthand SVG command.

        :param cmd: the command to check
        :return: the input cmd.cmd or a shorthand replacement ("H", "V", "T", "S", "Z")
        """
        if self.cmd in "QC" and _comp_iterables(
            self.abs_strs[:2], self.implied_cpt_str
        ):
            return "T" if self.cmd == "Q" else "S"
        if self.cmd == "L":
            if self.does_close:
                return "Z"
            if self.abs_strs[0] == self._current_point_str[0]:
                return "V"
            if self.abs_strs[1] == self._current_point_str[1]:
                return "H"
        return self.cmd

    @property
    def cpts(self) -> list[tuple[float, float]]:
        """Get the control points for this command.

        :return: a list of tuples of the x and y coordinates of the control points
        :raises ValueError: if the command is not a curve command
        """
        if self.cmd == "M":
            return []
        if self.cmd == "A":
            msg = "Arc commands cannot be converted to Bezier control points."
            raise ValueError(msg)
        vals = [*self._current_point, *self.abs_vals]
        return list(_chunk_pairs(vals))

    def _iter_str_pts(
        self,
        relative_or_absolute: Literal[
            RelativeOrAbsolute.RELATIVE, RelativeOrAbsolute.ABSOLUTE
        ],
    ) -> Iterator[str]:
        """Iterate over the points in this command as strings.

        :param relative_or_absolute: whether to return relative or absolute coordinates
        :return: an iterator over the points as strings
        :raises ValueError: if the relative_or_absolute value is unknown
        """
        if relative_or_absolute == RelativeOrAbsolute.ABSOLUTE:
            strs = self.abs_strs
        elif relative_or_absolute == RelativeOrAbsolute.RELATIVE:
            strs = self._rel_strs
        else:
            msg = f"Unknown relative_or_absolute value: {relative_or_absolute}"
            raise ValueError(msg)

        if self._str_cmd == "Z":
            return

        if self._str_cmd == "V":
            yield strs[1]
        elif self._str_cmd == "H":
            yield strs[0]
        elif self._str_cmd in "TS":
            yield from strs[2:]
        else:
            yield from strs

        if self.does_close:  # path was closed with an arc or curve.
            yield "Z" if relative_or_absolute == RelativeOrAbsolute.ABSOLUTE else "z"

    def get_svgd(self, relative_or_absolute: RelativeOrAbsolute) -> str:
        """Get the SVG command and points as a string.

        :param relative_or_absolute: whether to return relative or absolute coordinates
        :return: the SVG command and points as a string
        """
        if relative_or_absolute == RelativeOrAbsolute.RELATIVE:
            str_cmd = self._str_cmd.lower()
            return svgd_join(str_cmd, *self._iter_str_pts(relative_or_absolute))
        if relative_or_absolute == RelativeOrAbsolute.ABSOLUTE:
            str_cmd = self._str_cmd
            return svgd_join(str_cmd, *self._iter_str_pts(relative_or_absolute))
        if relative_or_absolute == RelativeOrAbsolute.SHORTEST:
            relative = self.get_svgd(relative_or_absolute.RELATIVE)
            absolute = self.get_svgd(relative_or_absolute.ABSOLUTE)
        if len(relative) < len(absolute):
            return relative
        return absolute


class PathCommands:
    """A linked list of commands.

    This class is used to create a linked list of _Command objects. It is used to
    convert a list of control points to an SVG path data string.
    """

    def __init__(self, cmd: PathCommand) -> None:
        """Create a linked list of commands.

        :param cmd: the first command in the linked list
        """
        while cmd.prev is not None:
            cmd = cmd.prev
        self.head = cmd

    def __iter__(self) -> Iterator[PathCommand]:
        """Iterate over the commands in the linked list.

        :return: an iterator over the commands in the linked list
        """
        cmd: PathCommand | None = self.head
        while cmd is not None:
            yield cmd
            cmd = cmd.next

    @classmethod
    def from_cpts(
        cls, cpts: Iterable[Iterable[Iterable[float]]], resolution: int | None = None
    ) -> PathCommands:
        """Create a linked list of commands from a list of tuples.

        :param cpts: a list of curves, each a list of xy control points
        :return: an instance of PathCommands linked list
        :raises ValueError: if no commands can be created from the control points
        """
        if not cpts:
            return cls(PathCommand("M", [0, 0], resolution=resolution))
        formatted_cpts = [[(x, y) for x, y in c] for c in cpts if c]

        node = PathCommand.append("M", formatted_cpts[0][0], resolution=resolution)
        for curve in formatted_cpts:
            curve_0_strs = map(node.format_number, curve[0])
            is_disjoint = (  # try to short circuit before any string conversions
                not _comp_iterables(node.abs_vals[-2:], curve[0])
                and not _comp_iterables(node.abs_strs[-2:], curve_0_strs)
            )
            if is_disjoint:
                node = PathCommand.append("M", curve[0], node)
            node = PathCommand.append(None, it.chain(*curve[1:]), node)

        return cls(node)

    @classmethod
    def from_svgd(cls, svgd: str, resolution: int | None = None) -> PathCommands:
        """Create a linked list of commands from an SVG path data string.

        :param svgd: an ABSOLUTE SVG path data string
        :return: the first command in the linked list
        :raises ValueError: if the SVG data string contains arc commands
        """
        parts = svgd_split(svgd)[::-1]  # e.g., ["M", "0", "0", "H", "1", "V", "2"]
        if not parts:
            return cls(PathCommand("M", [0, 0], resolution=resolution))

        cmd_str = parts.pop()
        node = PathCommand.append(
            cmd_str, _take_n_floats(parts, 2), resolution=resolution
        )
        while parts:
            cmd_str = {"m": "l", "M": "L"}.get(cmd_str, cmd_str)
            if parts[-1].lower() in _CMD_2_N:
                cmd_str = parts.pop()
            num_args = _CMD_2_N[cmd_str.lower()]
            nums = list(_take_n_floats(parts, num_args))
            if cmd_str in "Zz":  # close with a line if not already closed
                if node.does_close:
                    continue
                node = PathCommand.append("L", node.path_open, node)
            else:
                node = PathCommand.append(cmd_str, nums, node)
        return cls(node)

    def _get_svgd(self, relative_or_absolute: RelativeOrAbsolute) -> str:
        """Get the SVG path data string for the commands in the linked list.

        :param relative_or_absolute: whether to return relative or absolute coordinates
        :return: an SVG path data string
        """
        if all(x.cmd == "M" for x in self):
            return ""
        if relative_or_absolute != RelativeOrAbsolute.SHORTEST:
            return svgd_join_commands(*(x.get_svgd(relative_or_absolute) for x in self))

        absolutes = [x.get_svgd(RelativeOrAbsolute.ABSOLUTE) for x in self]
        skip_1st = it.islice(self, 1, None)
        relatives = [None, *(x.get_svgd(RelativeOrAbsolute.RELATIVE) for x in skip_1st)]
        return get_shortest_svgd(absolutes, relatives)

    @property
    def svgd(self) -> str:
        """Get the SVG path data string for the commands in the linked list.

        :return: an SVG path data string
        """
        return self._get_svgd(RelativeOrAbsolute.SHORTEST)

    @property
    def abs_svgd(self) -> str:
        """Get the absolute SVG path data string for the commands in the linked list.

        :return: an ABSOLUTE SVG path data string
        """
        return self._get_svgd(RelativeOrAbsolute.ABSOLUTE)

    @property
    def rel_svgd(self) -> str:
        """Get the relative SVG path data string for the commands in the linked list.

        :return: a RELATIVE SVG path data string
        """
        return self._get_svgd(RelativeOrAbsolute.RELATIVE)

    @property
    def cpts(self) -> list[list[tuple[float, float]]]:
        """Get the control points from the commands in the linked list.

        :return: a list of lists of control points
        :raises ValueError: if the first command is not a move command
        """
        per_cmd = (x.cpts for x in self)
        return [x for x in per_cmd if x]


def format_svgd_relative(svgd: str, resolution: int | None = None) -> str:
    """Convert an absolute SVG path data string to a relative one.

    :param svgd: an ABSOLUTE SVG path data string
    :return: a RELATIVE SVG path data string
    """
    return PathCommands.from_svgd(svgd, resolution=resolution).rel_svgd


def format_svgd_absolute(svgd: str, resolution: int | None = None) -> str:
    """Convert a relative SVG path data string to an absolute one.

    :param svgd: a RELATIVE SVG path data stming
    :return: an ABSOLUTE SVG path data string
    """
    return PathCommands.from_svgd(svgd, resolution=resolution).abs_svgd


def format_svgd_shortest(svgd: str, resolution: int | None = None) -> str:
    """Convert an SVG path data string to the shortest form.

    :param svgd: an SVG path data string
    :return: a shortest SVG path data string
    """
    return PathCommands.from_svgd(svgd, resolution=resolution).svgd


def get_cpts_from_svgd(
    svgd: str, resolution: int | None = None
) -> list[list[tuple[float, float]]]:
    """Get a list of lists of Bezier control points from an SVG path data string.

    :param svgd: an absolute or relative SVG path data string
    :return: a list of curves, each a list of xy tuples.
    """
    return PathCommands.from_svgd(svgd, resolution=resolution).cpts


def get_svgd_from_cpts(
    cpts: Iterable[Iterable[Iterable[float]]], resolution: int | None = None
) -> str:
    """Get an SVG path data string for a list of list of Bezier control points.

    :param cpts: a list of curves, each a list of xy control points
    :return: SVG path data string
    """
    return PathCommands.from_cpts(cpts, resolution=resolution).svgd
