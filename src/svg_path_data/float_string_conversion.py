"""Format float numbers as svg-readable strings.

Strips as many characters and zeros as possible. Uses exponential notation when it is
shorter ("2000" will be "2e3"; "-0.2" will be the less readable "-.2"). This
decreases file size a bit but more importantly reveals bugs in downstream code that
cannot deal with the the full range of svg number formats. There are svg optimization
tools that minimize characters, so expect to encounter exponential notation and
shorthand forms "in the wild".

By default, these function will not limit float resolution (the number of digits
after the decimal point *if* the number were in fixed-point notation). This is done
to limit information loss when converting between floats and strings and when
optimizing or altering existing path data strings. However, different systems may
give different results; your svg file size will be larger for no practical gain;
floating point errors may prevent identifyling command shorthand (hHvVtTsS); and the
difference won't be visible in the svg rendering anyway. When working with float
inputs, it is a good idea to set a resolution limit.

I've read articles that recommend no more than four digits before and two digits
after the decimal point for most svg rendering. I use resolution=6, which is perhaps
too generous, but aligns with conventions in other software, including Python's
`format(x, "f")`.

:author: Shay Hill
:created: 7/26/2020
"""

from __future__ import annotations

import re


def _build_float_pattern() -> re.Pattern[str]:
    """Build a regex pattern to match float strings.

    return: A compiled regex pattern that matches four named groups:
        * negative
        * integer
        * fraction
        * exponent

    All parts are optional, so the pattern can match an empty string or just a sign.
    Guard against this.

    {sign}{integer}.{fraction}e{exponent}
    """
    sub_patterns = [
        r"(?P<negative>-?)",  # optional negative sign
        r"(?P<integer>\d+?)",  # optional integer part
        r"(?:\.(?P<fraction>\d+))?",  # optional fractional part
        r"(?:[eE](?P<exponent>[+-]?\d+))?",  # optional exponent part
    ]
    return re.compile("".join(sub_patterns))


FLOAT_PATTERN = _build_float_pattern()


def _split_float_str(
    num: str | float, resolution: int | None = None
) -> tuple[str, str, str, int]:
    """Split a float string into its sign, integer part, fractional part, and exponent.

    :param num: A string representing number (e.g., '1.23e+03', '4', or '.2')
        or just a number.
    :param resolution: optionally limit the smallest difference between two numbers
        to (1/10**resolution).
    :return: A tuple containing the integer part, fractional part, and exponent.
    :raises ValueError: If the input string is not a valid float representation.
    :raises RuntimeError: If the FLOAT_PATTERN regex does not match. This
        would indicate a bug in the regex.

    Condition the match values and guard against bad input that would still match the
    permissive regex.
    """
    try:
        _ = float(num)
    except ValueError as e:
        msg = f"Invalid num argument: {num!r}. {e}"
        raise ValueError(msg) from e

    num_str = str(num) if resolution is None else f"{float(num):.{resolution}f}"

    groups = FLOAT_PATTERN.fullmatch(num_str)
    if not groups:
        msg = "Failed to interpret valid float string '{num}' as a float."
        raise RuntimeError(msg)

    integer = (groups["integer"] or "").lstrip("0")
    fraction = (groups["fraction"] or "").rstrip("0")
    if not (integer or fraction):  # ignore sign and exponent if number is zero
        return "", "", "", 0
    sign = groups["negative"] or ""
    exponent = int(groups["exponent"] or 0)
    return sign, integer, fraction, exponent


def _format_split_as_fixed_point(split_str: tuple[str, str, str, int]) -> str:
    """Format a split float string as fixed-point notation.

    :param split_str: A tuple containing the sign, integer part, fractional part,
        and exponent of a float string.
    :return: A string representing the number in fixed-point notation.
    """
    sign, integer, fraction, exponent = split_str
    if exponent > 0:
        fraction = fraction.ljust(exponent, "0")
        integer += fraction[:exponent]
        fraction = fraction[exponent:]
    elif exponent < 0:
        integer = integer.rjust(-exponent, "0")
        fraction = integer[exponent:] + fraction
        integer = integer[:exponent]

    fraction = "." + fraction if fraction else ""
    return f"{sign}{integer}{fraction}" or "0"


def format_as_fixed_point(num: str | float, resolution: int | None = None) -> str:
    """Format a number in fixed-point notation.

    :param exp_str: A string representing a number in exponential notation
        (e.g., '1.23e+03') or just a number.
    :param resolution: optionally limit the smallest difference between two numbers
        to (1/10**resolution).
    :return: A string representing the number in fixed-point notation.
    """
    return _format_split_as_fixed_point(_split_float_str(num, resolution))


def _format_split_as_exponential(split_str: tuple[str, str, str, int]) -> str:
    """Format a split float string as exponential notation.

    :param split_str: A tuple containing the sign, integer part, fractional part,
        and exponent of a float string.
    :return: A string representing the number in exponential notation.
    """
    sign, integer, fraction, exponent = split_str
    if len(integer) > 1:
        exponent += len(integer) - 1
        fraction = (integer[1:] + fraction).rstrip("0")
        integer = integer[0]
    elif not integer and fraction:
        leading_zeroes = len(fraction) - len(fraction.lstrip("0"))
        exponent -= leading_zeroes + 1
        integer = fraction[leading_zeroes]
        fraction = fraction[leading_zeroes + 1 :]

    fraction = "." + fraction if fraction else ""
    exp_str = f"e{exponent}" if exponent else ""
    return f"{sign}{integer}{fraction}{exp_str}" or "0"


def format_as_exponential(num: str | float, resolution: int | None = None) -> str:
    """Format a number in exponential notation.

    :param num_str: A string representing a number in fixed-point notation
        (e.g., '123000') or just a number.
    :param resolution: optionally limit the smallest difference between two numbers
        to (1/10**resolution).
    :return: A string representing the number in exponential notation.
    """
    return _format_split_as_exponential(_split_float_str(num, resolution))


_MIN_EXPONENTIAL_FLOAT_STRING_LENGTH = 3


def format_number(num: float | str, resolution: int | None = None) -> str:
    """Format float strings with as few chars as possible. Optionally limit resolution.

    :param num: anything that can print as a float.
    :param resolution: optionally limit the smallest difference between two numbers
        to (1/10**resolution).
    :return: the shorter of exponential or fixed-point notation of the number.

    * reduce fp resolution to (default) 6 digits
    * remove trailing zeros
    * remove trailing decimal point
    * remove leading 0 in "0.123"
    * convert "-0" to "0"
    * use shorter of exponential or fixed-point notation
    """
    split = _split_float_str(num, resolution)
    fixed_point_str = _format_split_as_fixed_point(split)
    if len(fixed_point_str) <= _MIN_EXPONENTIAL_FLOAT_STRING_LENGTH:
        return fixed_point_str
    exponential_str = _format_split_as_exponential(split)
    if len(exponential_str) < len(fixed_point_str):
        return exponential_str
    return fixed_point_str
