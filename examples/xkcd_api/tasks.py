import sys
import tempfile
from pathlib import Path
from typing import Sequence

from invoke import task

_HERE = Path(__file__).parent.absolute()


_SOURCE_PATH = 'xkcd_api'
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


@task
def deploy(context):
    with tempfile.TemporaryDirectory(prefix='.deploy-', dir=_HERE) as deploy_path:
        deploy_path = Path(deploy_path).absolute()
        context.run(
            f'docker run -w /root -v {_HERE}:/root -v {deploy_path}:/build '
            'python:3.8-slim '
            'sh -c "set -x && '
            'pip install -c requirements.txt wheel && '
            'pip install --target /build -r requirements.txt ."')

        # The `drover` utility configuration may contain files relative to the source working directory.
        with context.cd(str(_HERE)):
            context.run(f'drover --install-path {deploy_path} production')


@task
def request(context):
    with tempfile.NamedTemporaryFile(prefix='output', dir=_HERE) as output_file:
        context.run(
            'aws --region us-east-1 lambda invoke '
            '--function-name "xkcd-api" --invocation-type "RequestResponse" '
            f'{output_file.name}')
        output_file.seek(0)
        print('Lambda Output:', output_file.read(), sep='\n')


@task
def run(context, install = False):
    if install:
        with context.cd(str(_HERE)):
            context.run("pip install -c requirements.txt uvicorn")
            context.run("pip install -c requirements.txt -e .")
    with context.cd(str(_HERE / "instance")):
        environment = {
            "API_SETTINGS_FILE": "settings.yml",
            "LOG_SETTINGS_FILE": "logging.local.yml"
        }
        context.run("uvicorn"
            f" --reload-dir {_HERE / 'xkcd_api'!s}"
            f" --reload xkcd_api.asgi:app",
        env=environment)
