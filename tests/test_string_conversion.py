"""Test functions in string_conversion.py.

:author: Shay Hill
:created: 2023-09-23
"""

# pyright: reportPrivateUsage=false

import itertools as it
import random
from collections.abc import Iterator
from decimal import Decimal

import pytest

import svg_path_data.float_string_conversion as mod

_FLOAT_ITERATIONS = 100


def random_floats() -> Iterator[float]:
    """Yield random float values within(-ish) precision limits.

    Value may exceed the precision limits of the system.
    """
    for _ in range(_FLOAT_ITERATIONS):
        yield random.uniform(1e-20, 1e20)


def low_numbers() -> Iterator[float]:
    """Yield random float values below precision limits.

    Value may exceed the precision limits of the system.
    """
    for _ in range(_FLOAT_ITERATIONS):
        yield random.uniform(1e-25, 1e-24)


def high_numbers() -> Iterator[float]:
    """Yield random float values above precision limits.

    Value may exceed the precision limits of the system.
    """
    for _ in range(_FLOAT_ITERATIONS):
        yield random.uniform(1e24, 1e25)


def one_significant_digit() -> Iterator[float]:
    """Yield random float values with one significant digit."""
    for _ in range(_FLOAT_ITERATIONS):
        yield float("0" * random.randint(1, 10) + str(random.randint(1, 9)))


def random_ints() -> Iterator[int]:
    """Yield random integer values."""
    big_int = 2**63 - 1
    for _ in range(_FLOAT_ITERATIONS):
        yield random.randint(-big_int, big_int)
    yield from range(-15, 16)  # Include small integers for testing


def random_numbers() -> Iterator[float]:
    """Yield random numbers values."""
    yield from it.chain(
        random_floats(),
        low_numbers(),
        high_numbers(),
        one_significant_digit(),
        random_ints(),
    )


class TestSplitFloatStr:
    """Test _split_float_str."""

    def test_empty_string(self):
        """Empty string returns empty parts."""
        with pytest.raises(ValueError) as excinfo:
            _ = mod._split_float_str("")
        assert "could not convert" in str(excinfo.value)

    def test_no_fraction(self):
        """No fraction returns empty fraction."""
        assert mod._split_float_str("1") == ("", "1", "", 0)

    def test_no_exponent(self):
        """No exponent returns empty exponent."""
        assert mod._split_float_str("1.2") == ("", "1", "2", 0)

    def test_negative(self):
        """Negative number returns negative sign."""
        assert mod._split_float_str("-1.2e3") == ("-", "1", "2", 3)

    def test_negative_exponent(self):
        """Exponent is parsed correctly."""
        assert mod._split_float_str("1.2e-3") == ("", "1", "2", -3)

    def test_no_negative_zero(self):
        """Negative zero is not returned."""
        assert mod._split_float_str("-00") == ("", "", "", 0)


class TestFormatNumber:
    def test_negative_zero(self):
        """Remove "-" from "-0"."""
        assert mod.format_number(-0.0000000001, 6) == "0"

    def test_round_to_int(self):
        """Round to int if no decimal values !- 0."""
        assert mod.format_number(1.0000000001, 6) == "1"

    def test_use_negative_exponent(self):
        """Use negative exponent for small numbers."""
        assert mod.format_number(0.0001) == "1e-4"

    @pytest.mark.parametrize("num", random_numbers())
    def test_exp_vs_fp_notation(self, num: float):
        """Exponential and fp notation have the same value.

        The first assertion is a sanity check.
        """
        expect = float(str(num))
        assert expect == float(Decimal(num))
        assert expect == float(mod.format_as_fixed_point(str(num)))
        assert expect == float(mod.format_as_exponential(str(num)))

    @pytest.mark.parametrize("num", random_numbers())
    def test_exponent_integer_part_is_len_1_or_stripped(self, num: float):
        """Integer part is one digit."""
        exponential = mod.format_as_exponential(num)
        # Result is exactly one digit
        if "." not in exponential:
            pos = exponential.lstrip("-")
            # result in 0-9 or formatted like 1e-3
            assert pos.isdigit() or pos.split("e")[0].isdigit()
        else:
            # no 0.n or .n in exponential notation
            integer = exponential.split(".")[0].lstrip("-")
            assert not integer or integer in "123456789"

    def test_select_shorter(self):
        """Select shorter representation."""
        # fixed-point is shorter than exponential
        assert mod.format_number("2") == "2"
        assert mod.format_number("20") == "20"
        assert mod.format_number("200") == "200"
        # fixed-point if length is the same
        assert mod.format_number("200") == "200"
        # now exponential is shorter
        assert mod.format_number("2000") == "2e3"
