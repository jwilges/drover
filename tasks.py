import shutil
import sys
from pathlib import Path
from typing import Sequence

from invoke import task


_PROXY_SEPARATOR = '--'
def add_proxy_arguments(argument: str) -> Sequence[str]:
    if _PROXY_SEPARATOR in sys.argv:
        return f'{argument} {" ".join(sys.argv[sys.argv.index(_PROXY_SEPARATOR) + 1:])}'
    return argument


@task
def test(context):
    context.run('pytest')


@task
def lint(context):
    context.run('pylint --disable C,R drover')


@task
def coverage(context):
    context.run(add_proxy_arguments('coverage run -m pytest'))
    context.run('coverage report')


@task
def coverage_xml(context):
    context.run(add_proxy_arguments('coverage run -m pytest'))
    context.run('coverage xml')


@task
def wheel(context):
    release_paths = [Path(path) for path in ('build', 'dist')]
    for path in release_paths:
        if path.exists():
            shutil.rmtree(path)
    context.run('python setup.py sdist bdist_wheel')
