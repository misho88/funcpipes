# funcpipes
Functions for Building Data Pipelines

funcpipes defines a `Pipe` object which behaves like a Python function with
certain improvements that are useful for defining pipelines (or compositions).
When a function is used as a filter, it is common to have expressions like
```
y = f(g(1, h(x), 2), 3)
```
where, the input is `x`; `f`, `g`, `h` and are used with some arguments used as
static parameters and one is the "true" input; and `y` is the result. With this
library, the same thing can be written as
```
y = x | h | g.transpose(0, 2)[1, 2] | f.transpose(1)[3]
```
where `x | f` is equivalent to `f(x)`, `.transpose` rearranges arguments
and `[]` creates partial functions (e.g., in `g`, argument 0 is set to `1` and
argument 2 is set to `2`). Another option is
```
y = x | h & g.transpose(0, 2)[1, 2] & f.transpose(1)[3]
```
where `&` denotes composition, thus one could write:
```
pipeline = h & g.transpose(0, 2)[1, 2] & f.transpose(1)[3]
y = pipeline(x)  # or x | pipeline
```
which cleanly and succinctly describes the processing being done. See the
module's docstring for details.
