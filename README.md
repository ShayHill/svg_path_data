# svg_path_data

Convert floats to svg-readable strings. Convert between svg path `d` strings and non-rational Bézier control points.

## format floats

`format_number` converts a float or float string to the shortest svg-readable float representation. Uses the shorter of fixed-point or exponential notation.

```python
format_number("5000")
# "5e3"

format_number("-17e+06")
# "-1.7e7"

format_number(2/3)
# ".6666666666666666"

format_number(-1/10e6)
# "-1e-7"
```

An optional but recommended `resolution` argument limits the resolution of the output. The default `None` limits information loss when converting back and forth between float and string. The resolution that makes sense for your svg will depend on the scale of your svg. Less than 1/100000-th of a unit won't be visible on any browser, and even a 600 dpi giclée print will have less that 22k dots across a yard of output. I use resultion = 6, regardless of scale, which is overkill, but aligns with other tools I use, even `format(x, "f")` in Python. This is more than a cosmetic choice, the svg path data formatting functions will identify shorthand opportunities based on this resolution, so 0.000001 and 0.000002 will be different at resolution `None`, but equivalent at resolution `6`. A path that is open at a higher resolution may be conceivably closed at a lower resolution.

```python
format_number("5000", 6)
# "5e3"

format_number("-17e+06", 6)
# "-1.7e7"

format_number(2/3, 6)
# ".666667"

format_number(-1/10e6, 6)
# "0"
```

`format_as_exponential` and `format_as_fixed_point` are available if you have a preference.


## reformat svg path data strings

`format_svgd_absolute` and `format_svgd_relative` will convert between absolute and relative path data strings and optimize\* existing path data strings.

`format_svgd_shortest` will, command by command, select the shorter of the absolute and readonly versions.

```python
input = "M50,55C50,55 52 50 55 55Q0 2 2.5 2.5L2.5 0.5ZA1 1 1 1 1 54 44"

format_svgd_relative(input, resolution=2)
# m50 55s2-5 5 0q-55-53-52.5-52.5v-2za1 1 1 1 1 4-11

format_svgd_absolute(input, resolution=2)
# M50 55S52 50 55 55Q0 2 2.5 2.5V.5ZA1 1 1 1 1 54 44

format_svgd_shortest(input, resolution=2)
# M50 55s2-5 5 0Q0 2 2.5 2.5V.5Za1 1 1 1 1 4-11
```

\* *Optimize* is subjective: `zZ` in svg is strictly shorthand for a `line` command back to the most recent `move` command, but it is a strong convention to explicitly close paths that are implicitly closed with a curve ... with a `zZ` command, which in the "closed by a curve" case is a zero-length line. All functions here add these explicit `zZ` commands.

## convert svg path data strings

`get_cpts_from_svgd` and `get_svgd_from_cpts` convert between svg path data strings and non-rational Bézier control points.

```python
cpts = (
    ((0.5, 0.5), (1/3, 0.0), (2.0, 0.0), (2.5, 0.5)),
    ((2.5, 0.5), (2/3, 2.0), (2.5, 2.5)),
    ((2.5, 2.5), (0.5, 2.5)),
    ((0.5, 2.5), (0.5, 0.5)),
)
get_svgd_from_cpts(cpts, resolution=2)
# M.5 .5C.33 0 2 0 2.5 .5Q.67 2 2.5 2.5H.5Z

get_cpts_from_svgd('M.5 .5C.33 0 2 0 2.5 .5Q.67 2 2.5 2.5H.5Z')
# cpts = [
#     [(0.5, 0.5), (0.33, 0.0), (2.0, 0.0), (2.5, 0.5)],
#     [(2.5, 0.5), (0.67, 2.0), (2.5, 2.5)],
#     [(2.5, 2.5), (0.5, 2.5)],
#     [(0.5, 2.5), (0.5, 0.5)]
# ]
```

### arc commands

`format_svgd_*` functions understand all svg commands, including the arc commands, `A` and `a`, but if you try to convert arc commands to Bézier control points, you will get a ValueError, because there is no conversion to/from a non-Rational Bézier curve and an arc.
