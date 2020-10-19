r"""funcpipes - Functions for Building Data Pipelines

funcpipes defines a `Pipe` object which behaves like a Python function with
certain improvements that are useful for defining pipelines (or compositions).
When a function is used as a filter, it is common to have expressions like
    y = f(g(1, h(x), 2), 3)
where, the input is `x`; `f`, `g`, `h` and are used with some arguments used as
static parameters and one is the "true" input; and `y` is the result. With this
library, the same thing can be written as
    y = x | h | g.transpose(0, 2)[1, 2] | f.transpose(1)[3]
where `x | f` is equivalent to `f(x)`, `.transpose` rearranges arguments
and `[]` creates partial functions (e.g., in `g`, argument 0 is set to `1` and
argument 2 is set to `2`). Another option is
    y = x | h & g.transpose(0, 2)[1, 2] & f.transpose(1)[3]
where `&` denotes composition, thus one could write:
    pipeline = h & g.transpose(0, 2)[1, 2] & f.transpose(1)[3]
    y = pipeline(x)  # or x | pipeline
which cleanly and succinctly describes the processing being done. Detailed
features follow.

Firstly, a pipe behaves like its underlying function:
>>> p = Pipe(print); p
Pipe(<built-in function print>)
>>> p('hello', 'world', sep=', ', end='!\n')
hello, world!

It adds in some commonly-needed transformations as methods, the use of which
will become clear later, but for now, it's just an alternative notation:
>>> p(*('hello', 'world'))
hello world
>>> p.star(('hello', 'world'))
hello world
>>> tuple(map(p, ('hello', 'world')))
hello
world
(None, None)
>>> tuple(p.map(('hello', 'world')))
hello
world
(None, None)

It adds in the ability to create partials:
>>> p.partial('hello')
Pipe(functools.partial(<built-in function print>, 'hello'))
>>> p.partial('hello')('world')
hello world

It can chain function calls:
>>> Pipe(str.upper).chain(p)('hello world')
HELLO WORLD

It can enter contexts. To demonstrate, we create a verbose context:
>>> from contextlib import contextmanager
>>> @contextmanager
... def number(i): print('entering', i); yield i; print('exiting', i)
...
>>> with number(1) as n: print(n)
...
entering 1
1
exiting 1

If the Pipe's function is a partial whose arguments are context managers,
it will enter them. Pipe.partial can create such a pipe. There's also a
more conventient method that takes care of these steps.
>>> with p.partial(number(1), number(2)) as pp:
...     pp()
...
entering 1
entering 2
1 2
exiting 2
exiting 1
>>> p.with_context(number(1), number(2))
entering 1
entering 2
1 2
exiting 2
exiting 1

All of the above features can be accessed by operator overloads. The most
useful is `|`, which is used to call a Pipe, where the latter is postfixed
rather than prefixed to the argument. This allows shell-like piping from one
function to the next:
>>> 'hello world' | p
hello world
>>> from operator import add, mul
>>> 1 | Pipe(add).partial(2) | Pipe(mul).partial(3)
9

`[]` creates partials, which finally begins to hint as to why all of this is
useful.
>>> 1 | Pipe(add)[2] | Pipe(mul)[3]
9

& chains functions together. The following result is the same, with the
difference that the & is evaluated first, creating a new Pipe.
>>> 1 | Pipe(add)[2] & Pipe(mul)[3]
9

The `pipe` object is a do-nothing pipe, but non-pipe functions can be chained
to it, which gives it some utility as more than a placeholder:
>>> 1 | Pipe(add)[2] & Pipe(mul)[3] | pipe & str & str.isdecimal
True

The `to` object more or less returns a Pipe, i.e., to(func) and Pipe(func) do
the same thing. However, if given an attribute, it will call the corresponding
method of its argument.
>>> 1 | to(add)[2] | to(mul)[3]
9
>>> 'hello world' | to.upper
'HELLO WORLD'

The unary `+` does mapping:
>>> range(4) | +to(add)[2] | +to(mul)[3] | to(tuple)
(6, 9, 12, 15)

Notice the `to(tuple)` at the end. This is because iterators are lazily
evaluated, so something needs to force this evaluation when we want to see
a result. Since forcing the evaluation periodically happens frequently,
the `now` object is introduced, which is just `to(tuple)`.
>>> add, mul = (add, mul) | +to(Pipe)
>>> range(4) | +add[2] | +mul[3] | now
(6, 9, 12, 15)

Here are some variations that use Pipe chaining:
>>> range(4) | +add[2] & +mul[3] | now
(6, 9, 12, 15)
>>> range(4) | +(add[2] & mul[3]) | now
(6, 9, 12, 15)

Consider that the chain in the latter example may be complex and defined
beforehand for single-variable cases, whereas there is little advantage to the
version in the first example. Generally, the latter form is more useful, so
`^` is introduced and works like `|+~`, but due to operator precedence, we can
drop the parentheses:
>>> range(4) ^ add[2] & mul[3] | now
(6, 9, 12, 15)

Regarding the name `now`, it is again a functional descriptor. For example,
consider some potentially-parallel workload. Iterators are lazily evaluated,
so the worker process will not start until its result is needed. However,
adding a `now` right after its generation forces it to start right away:
>>> from time import time
>>> from subprocess import Popen
>>> cmds = tuple(['sleep', str(i)] for i in (1, 2)); cmds
(['sleep', '1'], ['sleep', '2'])
>>> start = time(); cmds | +Pipe(Popen) | +to(lambda p: p.wait()) | now; round(time() - start)
(0, 0)
3
>>> start = time(); cmds | +Pipe(Popen) | now | +to(lambda p: p.wait()) | now; round(time() - start)
(0, 0)
2

Unary `-` applies `Path.star`, i.e., an iterable is used as the
arguments to the pipe:
>>> range(4) | -to(print)
0 1 2 3

And, returning to contexts, `~` enters a context:
>>> from contextlib import contextmanager
>>> @contextmanager
... def number(i): print('entering', i); yield i; print('exiting', i)
...
>>> number(1) | ~to(print)
entering 1
1
exiting 1
>>> (1,2) | +to(number) | -~to(print)
entering 1
entering 2
1 2
exiting 2
exiting 1

This gives a fairly short way to deal with contexts without leaving the pipeline
paradigm (i.e., no need for an explicit `with`):
>>> from tempfile import TemporaryDirectory
>>> from pathlib import Path
>>> with TemporaryDirectory() as dir:
...     Path(dir, 'myfile').write_text('hello world')
...     f'{dir}/myfile' | to(open) | ~to(lambda file: file.read())
...
11
'hello world'

To put a bunch of this stuff together, we create a Pipe context manager,
and turn a few common functions into Pipes, too. Then, we create some
numbers, map them to a composition of two functions, and collect the
results to print:
>>> from contextlib import contextmanager
>>> from operator import add, mul
>>> @Pipe
... @contextmanager
... def number(i): print('entering', i); yield i; print('exiting', i)
...
>>> add, mul, print = (add, mul, print) | +to(Pipe)
>>> (range(4) | +number) ^ add[2] & mul[3] | -print
entering 0
exiting 0
entering 1
exiting 1
entering 2
exiting 2
entering 3
exiting 3
6 9 12 15
"""

__all__ = 'Pipe', 'pipe', 'get', 'to', 'now', 'Arguments', 'pipify'


from functools import partial, cached_property, wraps
from contextlib import ExitStack
from types import ModuleType


class Arguments:
    """groups arguments together

    As far as I know, Python has no other way to capture the exact way a
    function is meant to be called, and it is important that this is distinct
    from a tuple

    To the user, it's useful to initizalize a pipeline:
    >>> Arguments(1,2,3) | to(print)
    1 2 3

    It is also how a default Pipe operates so that it does nothing:
    >>> Arguments(1,2,3) | Pipe() | Pipe() | to(print)
    1 2 3
    """
    __slots__ = 'args', 'kwargs'

    def __init__(self, *args, **kwargs):
        """store arguments together

        >>> a = Arguments(1, 2, a=3, b=4); a.args, a.kwargs
        ((1, 2), {'a': 3, 'b': 4})
        """
        self.args, self.kwargs = args, kwargs

    def __iter__(self):
        """get at fields quickly

        >>> args, kwargs = Arguments(1, 2, a=3, b=4)
        >>> args
        (1, 2)
        >>> kwargs
        {'a': 3, 'b': 4}
        """
        yield self.args
        yield self.kwargs

    def __repr__(self):
        """string representation

        >>> Arguments(1, 2, a=3, b=4)
        Arguments(1, 2, a=3, b=4)
        """
        args = ', '.join(repr(arg) for arg in self.args)
        kwargs = ', '.join(f'{kw}={repr(arg)}' for kw, arg in self.kwargs.items())
        comma = ', ' if kwargs else ''
        return f'{__class__.__qualname__}({args}{comma}{kwargs})'


class Pipe:
    def __init__(self, func=Arguments):
        if not callable(func):
            raise ValueError(f'{repr(func)} is not callable')
        self.__func = func

    @property
    def func(self):
        return self.__func

    # important methods:

    def apply(self, *args, **kwargs):
        """apply the underlying function

        >>> Pipe(print).apply(1, 2.0, 3j)
        1 2.0 3j
        """
        for arg in args:
            if isinstance(arg, Arguments):
                if len(args) != 1 or kwargs:
                    raise RuntimeError(f'{arg} must be passed on its own')
                return self.func(*arg.args, **arg.kwargs)
        return self.func(*args, **kwargs)

    @cached_property
    def star(self):
        """a Pipe that takes in a list (and dict) for * (and **) expansion

        >>> Pipe(print).star.apply((1, 2.0, 3j), dict(sep=','))
        1,2.0,3j
        """
        def closure(args, kwargs=None):
            return self(*args) if kwargs is None else self(*args, **kwargs)
        return Pipe(closure)

    @cached_property
    def map(self):
        """a Pipe that maps this one to a callable

        >>> tuple(Pipe(lambda x: x**2).map.apply((1, 2, 3)))
        (1, 4, 9)
        """
        return Pipe(partial(map, self))

    def partial(self, *args, **kwargs):
        """get partial of this function (like functools.partial)

        >>> Pipe(print).partial(sep=',')(1, 2, 3)
        1,2,3
        """
        return Pipe(partial(self.func, *args, **kwargs))

    def transpose(self, *indices):
        """rearrange (some of) the arguments to a function

        This is mostly useful as a single-argument where .transpose(i)
        makes the i-th argument the 0-th argument, but .transpose(i, j)
        will make the i-th and j-th the 0-th and 1-st, respectively, etc.

        >>> Pipe(lambda n, d: n / d)(1, 2)
        0.5
        >>> Pipe(lambda n, d: n / d).transpose(1, 0)(1, 2)
        2.0
        >>> Pipe(lambda n, d: n / d).transpose(1)(1, 2)
        2.0
        """
        if len(set(indices)) < len(indices):
            raise ValueError('some indices are repeated')

        @wraps(self.func)
        def closure(*args, **kwargs):
            n = len(args)
            if not all(-n <= i < n for i in indices):
                raise IndexError('argument index out of range')
            idx = tuple(i + n if i < 0 else i for i in indices)
            rest = tuple(i for i in range(n) if i not in idx)
            return self.func(*(args[i] for i in idx + rest), **kwargs)
        return Pipe(closure)

    @cached_property
    def flip(self):
        """swap the first two argument of the function
        >>> Pipe(lambda n, d: n / d)(1, 2)
        0.5
        >>> Pipe(lambda n, d: n / d).flip(1, 2)
        2.0
        >>> Pipe(lambda n, d: n / d).flip.flip(1, 2)
        0.5
        """
        return self.transpose(1, 0)

    def chain(self, other):
        """function composition (chaining)

        >>> Pipe(str.upper).chain(str.split).apply('hello world')
        ['HELLO', 'WORLD']
        """
        def closure(*args, **kwargs):
            return Pipe(other)(self(*args, **kwargs))
        return Pipe(closure)

    @cached_property
    def with_context(self):
        """enter the contexts of arguments

        >>> from contextlib import contextmanager
        >>> @contextmanager
        ... def number(i): print('entering', i); yield i; print('exiting', i)
        ...
        >>> Pipe(print).with_context.apply(number(7))
        entering 7
        7
        exiting 7
        """
        def closure(*args, **kwargs):
            with self.partial(*args, **kwargs) as p:
                return p()
        return Pipe(closure)

    # operators:

    def __call__(self, *args, **kwargs):
        """apply the underlying function

        >>> Pipe(print)(1, 2.0, 3j)
        1 2.0 3j
        """
        return self.apply(*args, **kwargs)

    def __ror__(self, arg):  # arg | self
        """apply the underlying function

        >>> (1, 2.0, 3j) | Pipe(print).star
        1 2.0 3j
        """
        return self.apply(arg)

    def __getitem__(self, args):  # self[args]
        """get partial of this function (like functools.partial)

        >>> Pipe(print)[1, 2, 3]()
        1 2 3
        """
        return self.partial(*args) if isinstance(args, tuple) else self.partial(args)

    def __and__(self, other):  # self & other
        """function composition (chaining)

        >>> 'hello world' | Pipe(str.upper) & str.split
        ['HELLO', 'WORLD']
        """
        return self.chain(other)

    def __neg__(self):  # -self
        """a Pipe that takes in a list (and dict) for * (and **) expansion

        >>> (1, 2.0, 3j) | -Pipe(print)
        1 2.0 3j
        """
        return self.star

    def __pos__(self):  # +self
        """a Pipe that maps this one to a callable

        >>> tuple(Pipe(lambda x: x**2).map.apply((1, 2, 3)))
        (1, 4, 9)
        """
        return self.map

    def __invert__(self):  # ~self
        """enter the contexts of arguments

        >>> from contextlib import contextmanager
        >>> @contextmanager
        ... def number(i): print('entering', i); yield i; print('exiting', i)
        ...
        >>> number(7) | ~Pipe(print)
        entering 7
        7
        exiting 7
        """
        return self.with_context

    def __rxor__(self, iterable):  # iterable ^ self
        """call the mappable version of the pipe in a context

        >>> from contextlib import contextmanager
        >>> from operator import add, mul
        >>> @Pipe
        ... @contextmanager
        ... def number(i): print('entering', i); yield i; print('exiting', i)
        ...
        >>> add, mul, print = (add, mul, print) | +to(Pipe)
        >>> (range(4) | +number) ^ add[2] & mul[3] | -print
        entering 0
        exiting 0
        entering 1
        exiting 1
        entering 2
        exiting 2
        entering 3
        exiting 3
        6 9 12 15
        """
        return self.with_context.map(iterable)

    # context management

    def __enter__(self):
        stack = ExitStack()
        self.__stack = stack

        if not isinstance(self.func, partial):
            return self

        func, args, kwargs = self.func.func, self.func.args, self.func.keywords
        stack.__enter__()  # pretty sure this does nothing
        args = (
            stack.enter_context(arg) if hasattr(arg, '__enter__') else arg
            for arg in args
        )
        kwargs = {
            kw: stack.enter_context(arg) if hasattr(arg, '__enter__') else arg
            for kw, arg in kwargs.items()
        }
        return Pipe(partial(func, *args, **kwargs))

    def __exit__(self, *exc_details):
        res = self.__stack.__exit__(*exc_details)
        del self.__stack
        return res

    # miscellaneous:

    def __repr__(self):
        return f'{__class__.__qualname__}({self.func})'


class GetAttr(Pipe):
    def __getattr__(self, attr):
        return self.partial(attr)


@GetAttr
def get(name, object_or_default, *objects):
    has_default = bool(objects)
    if has_default:
        object, = objects
        default = object_or_default
    else:
        object = object_or_default

    if isinstance(name, str):
        return getattr(object, name, default) if has_default else getattr(object, name)
    return tuple(get(n, object_or_default, *objects) for n in name)


get.o = get.stdout
get.e = get.stderr
get.oe = get.partial(('stdout', 'stderr'))


class To:
    def __call__(self, arg):
        return Pipe(arg)

    def __getattr__(self, attr):
        def closure(obj):
            return getattr(obj, attr)()
        return Pipe(closure)


to = To()
pipe = Pipe()
now = to(tuple)


class NameSpace:
    def __init__(self, description=None, **kwargs):
        if description is None:
            description = kwargs.get('__name__', 'unknown')
        self.__description = description
        self.update(kwargs)

    def __repr__(self):
        return f'{__class__.__qualname__}({self.__description})'

    def update(self, mapping):
        vars(self).update(mapping)


def pipify(namespace, recurse=(ModuleType, type), max_depth=-1, parsed=None):
    """return a copy of something module-like, but with Pipes

    >>> @pipify
    ... class Funcs:
    ...     def add(x, y): return x + y
    ...     def mul(x, y): return x * y
    ...
    >>> 4 | Funcs.add[1]
    5
    >>> 4 | Funcs.mul[2]
    8
    """
    if parsed is None:
        parsed = {}

    ns = NameSpace(repr(namespace))
    parsed[namespace] = ns

    def get_attr(attr):
        if callable(attr):
            return Pipe(attr)
        try:
            return parsed[attr]
        except (KeyError, TypeError):
            pass
        if max_depth and isinstance(attr, recurse):
            return pipify(attr, recurse, max_depth - 1, parsed)
        return attr

    ns.update({
        name: get_attr(attr)
        for name, attr in vars(namespace).items()
    })
    return ns


if __name__ == '__main__':
    from doctest import testmod
    testmod()
