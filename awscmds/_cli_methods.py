import inspect
import sys, os
import textwrap
from inspect import signature
from typing import Callable, Optional


# todo package?

def _frame_to_funcname(frame_info: inspect.FrameInfo) -> str:
    """Returns module.function or module.class.function"""
    # todo test
    if not isinstance(frame_info, inspect.FrameInfo):
        raise TypeError
    module = inspect.getmodule(frame_info.frame)
    if module is None:
        return frame_info.function  # test
    module_name = module.__name__
    return f'{module_name}.{frame_info.function}'


def _func_to_funcname(func: Callable) -> str:
    """Returns module.function or module.class.function"""
    if not callable(func):
        raise TypeError
    # noinspection PyUnresolvedReferences
    return f'{func.__module__}.{func.__name__}'


def _minimize_spaces(s):
    return " ".join(s.split())


def methods_cli(obj: object, exit=True) -> None:
    """Converts an object to an application CLI.

    Every public method of the object that does not require arguments becomes
    a command to run.
    """

    stack_funcnames = {_frame_to_funcname(frame_info) for frame_info in
                       inspect.stack()}

    # finding all public methods that do not require args
    methods = []
    for x in dir(obj):
        method = getattr(obj, x)
        # skipping non-methods
        if not callable(method):
            continue
        # skipping private methods
        if method.__name__.startswith("_"):
            continue
        # skipping constructor
        if method.__name__ == obj.__class__.__name__:
            continue

        # skipping all the functions the actually calling this function now.
        # So if an object defines .main(self) method that calls
        # methods_cli(self), the .main() method will not be a command
        if _func_to_funcname(method) in stack_funcnames:
            continue

        if signature(method).parameters:  # if has args
            continue
        methods.append(method)

    command: Optional[str] = None
    if len(sys.argv) >= 2:
        command = sys.argv[1].strip().replace('-', '_')
        for method in methods:
            if command == method.__name__:
                method()
                if exit:
                    sys.exit(0)

    print(f"Usage: {os.path.basename(sys.argv[0])} COMMAND")
    if command is not None:
        print()
        print(f"Unexpected command: '{command}'")
    print()
    print("Commands:")
    for method in methods:
        if method.__doc__:
            doc = _minimize_spaces(method.__doc__)
        else:
            doc = ''
        print(f"  {method.__name__.replace('_', '-')}")
        if doc:
            print(textwrap.indent(textwrap.fill(doc, 60), ' ' * 4))
    sys.exit(2)
