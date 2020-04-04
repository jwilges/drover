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


def coverage_base(context, mode):
    context.run(add_proxy_arguments('coverage run -m pytest'))
    context.run(f'coverage {mode}')


@task
def coverage(context):
    coverage_base(context, 'report')


@task
def coverage_xml(context):
    coverage_base(context, 'xml')


@task
def coverage_html(context):
    coverage_base(context, 'html')


@task
def wheel(context):
    context.run('pip install wheel')
    release_paths = [Path(path) for path in ('build', 'dist')]
    for path in release_paths:
        if path.exists():
            shutil.rmtree(path)
    context.run('python setup.py sdist bdist_wheel')
