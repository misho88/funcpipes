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

__all__ = (
    'Pipe', 'Arguments', 'Nothing',
    'pipe', 'arguments', 'nothing', 'get', 'to', 'discard', 'collect', 'now',
    'repeat', 'ignore',
    'until', 'until_result', 'until_exception', 'until_condition', 'until_count',
    'pipify',
)


from functools import partial, cached_property, wraps
from contextlib import ExitStack
from types import ModuleType
from typing import Callable, Optional
from collections.abc import Iterable, Collection, Mapping
import itertools


def indent(text):
    import textwrap
    return textwrap.indent(str(text), '\t')


class Arguments:
    """groups arguments together

    As far as I know, Python has no other way to capture the exact way a
    function is meant to be called, and it is important that this is distinct
    from a tuple. On its own, this is more or less a "just" monad.

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
        """

        >>> a, b, c = Arguments(1, 2, 3)
        >>> a, b, c
        (1, 2, 3)
        """
        if self.kwargs:
            raise ValueError('kwargs must be empty to iterate')
        yield from self.args

    def __str__(self):
        """string representation

        >>> str(Arguments(1, 2, a=3, b=4))
        '1, 2, a=3, b=4'
        """
        args = ', '.join(repr(arg) for arg in self.args)
        kwargs = ', '.join(f'{kw}={repr(arg)}' for kw, arg in self.kwargs.items())
        comma = ', ' if args and kwargs else ''
        return f'{args}{comma}{kwargs}'

    def __repr__(self):
        """string representation

        >>> repr(Arguments(1, 2, a=3, b=4))
        'Arguments(1, 2, a=3, b=4)'
        """
        return f'{type(self).__qualname__}({str(self)})'

    def apply(self, func):
        return func(*self.args, **self.kwargs)

    def __call__(self, func):
        return self.apply(func)

    def partial(self, func):
        return partial(func, *self.args, **self.kwargs)

    def __getitem__(self, func):
        return self.partial(func)

    @classmethod
    def get(cls, *args, **kwargs):
        for arg in args:
            if isinstance(arg, Arguments):
                if len(args) != 1 or kwargs:
                    raise RuntimeError(f'{arg} must be passed on its own')
                return arg
        return cls(*args, **kwargs)


class Nothing(Arguments):
    """do nothing with a function

    This is similar to a "nothing" monad, but it can be used to carry state
    information through to the end of the pipeline if instantiated with such.
    """
    def apply(self, func):
        return self


class Pipe:
    def __init__(self, func: Callable = Arguments, name: Optional[str] = None, doc: Optional[str] = None):
        if not callable(func):
            raise ValueError(f'{repr(func)} is not callable')
        self.__func__ = func
        self.__name__ = name if name is not None else getattr(func, '__name__', None)
        self.__doc__ = doc if doc is not None else getattr(func, '__doc__', None)

    @classmethod
    def as_pipe(cls, func):
        return func if isinstance(func, cls) else cls(func)

    @property
    def func(self):
        return self.__func__

    @property
    def name(self):
        return self.__name__

    @property
    def doc(self):
        return self.__doc__

    def with_name(self, name):
        """return the pipe with a new name"""
        return Pipe(self.func, name=name, doc=self.doc)

    # important methods:

    def apply(self, *args, **kwargs):
        """apply the underlying function

        >>> Pipe(print).apply(1, 2.0, 3j)
        1 2.0 3j
        """
        return Arguments.get(*args, **kwargs).apply(self.func)

    @cached_property
    def star(self):
        """a Pipe that takes in a list (and dict) for * (and **) expansion

        >>> Pipe(print).star.apply((1, 2.0, 3j), dict(sep=','))
        1,2.0,3j
        """
        def closure(args, kwargs=None):
            return self(*args) if kwargs is None else self(*args, **kwargs)
        return Pipe(
            closure,
            name=f'-{self.name}',
            doc=f'{self.doc}\n\nWITH STAR EXPANSION',
        )

    @cached_property
    def map(self):
        """a Pipe that maps this one to a callable

        >>> tuple(Pipe(lambda x: x**2).map.apply((1, 2, 3)))
        (1, 4, 9)
        """
        return Pipe(
            partial(map, self),
            name=f'+{self.name}',
            doc=f'{self.doc}\n\nMAPPED TO EACH ARGUMENT',
        )

    def partial(self, *args, **kwargs):
        """get partial of this function (like functools.partial)

        >>> Pipe(print).partial(sep=',')(1, 2, 3)
        1,2,3
        """
        arguments = Arguments.get(*args, **kwargs)
        return Pipe(
            arguments.partial(self.func),
            name=f'{self.name}.partial({arguments})' if arguments.kwargs else f'{self.name}[{arguments}]',
            doc=f'{self.doc}\n\nWITH ARGUMENTS: {arguments}',
        )

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
        >>> div_by_2 = Pipe(lambda n, d: n / d).T(1)[2]; div_by_2(1)
        0.5
        """
        if len(set(indices)) < len(indices):
            raise ValueError('some indices are repeated')

        @wraps(self.func)
        def closure(*args, **kwargs):
            n = len(args)
            if not all(-n <= i < n for i in indices):
                raise IndexError('argument index out of range')

            mapping = { i: j % n for i, j in enumerate(indices) }
            if len(set(mapping.values())) < len(mapping):
                raise ValueError('some indices are repeated')

            j = 0
            targs = {}
            for i, arg in enumerate(args):
                while j in targs:
                    j += 1
                if i in mapping:
                    targs[mapping[i]] = arg
                else:
                    targs[j] = arg
            for i, j in enumerate(sorted(targs.keys())):
                if i != j:
                    raise TypeError(f'argument bound for index {i} is missing')
            args = (targs[i] for i in range(len(targs)))
            return self.func(*args, **kwargs)

        idx_string = ', '.join(str(i) for i in indices)
        return Pipe(
            closure,
            name=f'{self.name}.T({idx_string})',
            doc=f'{self.doc}\n\nWITH ARGUMENT ORDER: {idx_string}',
        )

    def T(self, *indices):
        return self.transpose(*indices)

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
        other = Pipe.as_pipe(other)

        def closure(*args, **kwargs):
            return other(self(*args, **kwargs))

        return Pipe(
            closure,
            name=f'{self.name} & {other.name}',
            doc=f'FIRST{indent(self.doc)}\nTHEN{indent(other.doc)}',
        )

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
        return Pipe(
            closure,
            name=f'~{self.name}',
            doc=f'{self.doc}\n\nWITH EVERY CONTEXT MANAGER ENTERED',
        )

    # operators:

    def __call__(self, *args, **kwargs):
        """apply the underlying function

        >>> Pipe(print)(1, 2.0, 3j)
        1 2.0 3j
        """
        return self.apply(*args, **kwargs)

    def __or__(self, arg):  # arg | self
        """apply the underlying function when the argument is also a pipe

        >>> (pipe | pipe)(pipe)
        Arguments(Pipe(<class '__main__.Arguments'>))
        >>> (pipe | pipe)(pipe)(pipe)
        Arguments(Pipe(<class '__main__.Arguments'>))
        """
        return arg.apply(self)

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

    def __str__(self):
        return self.name if self.name is not None else repr(self)

    def __repr__(self):
        return f'{type(self).__qualname__}({self.func})'

    def __iter__(self):
        raise TypeError(f"'{type(self).__qualname__}' object is not iterable")


class GetAttr(Pipe):
    def __getattr__(self, attr):
        getter = self.partial(attr)
        getter.__name__ = f'{self.name}.{attr}'
        getter.__doc__ = f'get the .{attr} attribute of an object'
        return getter


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


class To:
    """convenient way to create pipes

    This should not be instantiated by the user directly, but rather
    used through its only instance "to":

    >>> 'hello' | to(print)
    hello
    """

    def __call__(self, arg):
        r"""when called, to(), where to = To(), acts like Pipe()

        >>> ('hello', 'world') | -to(print).partial(sep='\n')
        hello
        world
        """
        if isinstance(arg, Pipe):
            return arg
        as_pipe = Pipe(arg)
        as_pipe.__name__ = f'to({as_pipe.name})'
        return as_pipe

    def __getattr__(self, attr):
        r"""to.attr(), where to = To(), allows calling methods

        Note the positional arguments are rearranged such that the object is
        last, i.e., to.split('X', 'aXb') is equivalent to 'aXb'.split('X') so
        that partials work like expected

        >>> 'hello world' | to.split
        ['hello', 'world']
        >>> 'helloXworld' | to.split['X']
        ['hello', 'world']
        >>> b'helloXworld' | to.split[b'X']
        [b'hello', b'world']
        """
        def closure(*args, **kwargs):
            *args, obj = args
            return getattr(obj, attr)(*args, **kwargs)
        return Pipe(closure, name=f'to.{attr}', doc=f'run the .{attr} method of an object')


to = To()
pipe = Pipe()
arguments = Arguments()
nothing = Nothing()
repeat = itertools.repeat(arguments)


@Pipe
def discard(*args, **kwargs):
    if len(args) == 1 and not kwargs:
        obj, = args
        if isinstance(obj, (str, bytes, bytearray)):
            return
        if isinstance(obj, Mapping):
            for v in obj.values():
                discard(v)
            return
        if isinstance(obj, (Collection, Iterable)) and not isinstance(obj, range):
            for item in obj:
                discard(item)
            return
        return
    for v in args:
        discard(v)
    for v in kwargs.values():
        discard(v)


@Pipe
def collect(*args, **kwargs):
    if len(args) == 1 and not kwargs:
        obj, = args
        if isinstance(obj, (str, bytes, bytearray)):
            return obj
        if isinstance(obj, Mapping):
            return type(obj)({ k: collect(v) for k, v in obj.items() })
        if isinstance(obj, Collection) and not isinstance(obj, range):
            return type(obj)(collect(item) for item in obj)
        if isinstance(obj, Iterable):
            return collect(tuple(obj))
        return obj
    if not kwargs:
        return tuple(collect(v) for v in args)
    return tuple(collect(v) for v in args), { k: collect(v) for k, v in kwargs.items() }


@Pipe
def now(*args, **kwargs):
    return collect(*args, **kwargs)
now.collect = collect  # noqa: E305
now.discard = discard  # noqa: E305


@Pipe
def until_condition(condition, iterable):
    """loop until condition is met"""
    for item in iterable:
        if condition(item):
            return
        yield item


@Pipe
def until_result(result, iterable):
    """loop until a certain result """
    return until_condition(lambda item: item == result, iterable)


@Pipe
def until_exception(*args):
    try:
        yield from args[-1]
    except args[:-1]:
        pass


@Pipe
def until_count(count, iterable):
    return (item for _, item in zip(range(count), iterable))


@Pipe
def ignore(*args):
    while True:
        yield from until_exception(*args)


@Pipe
def until(*args):
    """one of until_condition, until_result or until_exception

    This covers three common cases. One is to keep going until a result:
    >>> from itertools import count
    >>> count() | until[5] | now
    (0, 1, 2, 3, 4)

    Another is until an arbitrary condition (think if-break inside a loop):
    >>> count() | until[lambda x: x == 5] | now
    (0, 1, 2, 3, 4)

    Finally, until an exception occurs (think contextlib.suppress):
    >>> def f():
    ...     yield 1
    ...     yield 2
    ...     raise EOFError
    ...
    >>> f() | until[EOFError] | now
    (1, 2)

    """
    *events, iterable = args
    if len(events) == 1:
        event, = events
        if isinstance(event, type) and issubclass(event, BaseException):
            func = until_exception
        elif callable(event):
            func = until_condition
        else:
            func = until_result
    else:
        if not all(issubclass(e, BaseException) for e in events):
            raise ValueError('with multiple arguments, all arguments must be exceptions')
        func = until_exception
    return func(*args)


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
