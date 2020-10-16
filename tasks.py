import shutil
import sys
from pathlib import Path
from typing import Sequence

from invoke import call, task

_SOURCE_PATH = 'drover'
_PROXY_SEPARATOR = '--'

def add_proxy_arguments(argument: str) -> Sequence[str]:
    if _PROXY_SEPARATOR in sys.argv:
        return f'{argument} {" ".join(sys.argv[sys.argv.index(_PROXY_SEPARATOR) + 1:])}'
    return argument


@task
def bandit(context):
    excluded_paths = ','.join(('*/tests/*', ))
    context.run(add_proxy_arguments(f'bandit --exclude {excluded_paths} --recursive {_SOURCE_PATH}'))


@task
def yapf(context, check = False):
    arguments = '--recursive'
    arguments += ' --diff' if check else ' --in-place'
    context.run(add_proxy_arguments(f'yapf {arguments} {_SOURCE_PATH}'), hide='stdout' if check else None)


@task
def isort(context, check = False):
    arguments = ' --check --diff' if check else ''
    context.run(add_proxy_arguments(f'isort {arguments} --src {_SOURCE_PATH} {_SOURCE_PATH}'))


@task
def test(context):
    context.run(add_proxy_arguments('pytest'))


@task
def lint(context):
    context.run(add_proxy_arguments(f'pylint --disable C,R,fixme {_SOURCE_PATH}'))


@task
def mypy(context):
    context.run(add_proxy_arguments(f'mypy {_SOURCE_PATH}'))


@task(help={'upgrade': 'try to upgrade all dependencies to their latest versions'})
def compile_requirements(context, upgrade = False):
    """Compile requirements.txt and requirements.dev.txt from their .in specifications"""
    arguments = '-U' if upgrade else ''
    context.run(add_proxy_arguments(f'pip-compile {arguments}'))
    context.run(add_proxy_arguments(f'pip-compile {arguments} requirements.dev.in'))


def coverage_base(context, mode, run):
    if run:
        context.run(add_proxy_arguments('coverage run -m pytest'))
    context.run(f'coverage {mode}')


@task
def coverage(context, run = True):
    coverage_base(context, 'report', run)


@task
def coverage_xml(context, run = True):
    coverage_base(context, 'xml', run)


@task
def coverage_html(context, run = True):
    coverage_base(context, 'html', run)


@task(call(isort, check=True), call(yapf, check=True), lint, mypy, bandit, coverage)
def ci(context): ...


@task
def docs_html(context):
    source_path = (Path(__file__).parent / 'docs').absolute()
    context.run(f'sphinx-apidoc --force --output-dir "{str(source_path)}" "{_SOURCE_PATH}"')
    context.run('python setup.py build_sphinx')


@task
def wheel(context):
    context.run('pip install -c requirements.dev.txt wheel')
    release_paths = [Path(path) for path in ('build', 'dist')]
    for path in release_paths:
        if path.exists():
            shutil.rmtree(path)
    context.run('python setup.py sdist bdist_wheel')
