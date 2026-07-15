"""MAICA Illuminator backend library.

Call :func:`init` before using runtime services. Heavy networking and database
modules are imported lazily so metadata consumers can import ``maica.version``
without loading every optional integration.
"""

from importlib import import_module


def init(envdir: str | None = None, extra_envdir: list[str] | None = None, silent=False, ignore_envc=False, **kwargs):
    """Load configuration and initialize keys, databases, migrations, and tools."""
    from .maica_starter import check_data_init, check_params

    if ignore_envc:
        kwargs['MAICA_IS_REAL_ENV'] = '1'
    check_params(
        envdir=envdir,
        extra_envdir=extra_envdir,
        silent=silent,
        parse_cli=False,
        **kwargs,
    )
    check_data_init(exit_on_unconfigured=False)


async def start_all(start_target="chat"):
    """Start configured services after :func:`init` has completed."""
    from .maica_starter import start_all as _start_all

    return await _start_all(start_target)


def __getattr__(name):
    if name == "maica_utils":
        module = import_module(".maica_utils", __name__)
        globals()[name] = module
        return module
    if name == "silent":
        value = import_module(".maica_utils", __name__).silent
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'maica_utils',
    'init',
    'start_all',
]
