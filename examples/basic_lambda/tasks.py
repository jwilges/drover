import tempfile
from pathlib import Path

from invoke import task

_SOURCE_PATH = Path(__file__).parent.absolute()


@task
def deploy(context):
    build_script = '''#!/usr/bin/env sh
        set -x
        export PIP_DISABLE_PIP_VERSION_CHECK=1
        python -m venv --clear /tmp/venv
        /tmp/venv/bin/pip install wheel
        /tmp/venv/bin/pip install --target /build -r requirements.txt .
        '''
    build_script = ('\n'.join([line.strip('\t \r\n') for line in build_script.splitlines()])).encode()
    with tempfile.TemporaryDirectory(prefix='.deploy-', dir=_SOURCE_PATH) as deploy_path:
        deploy_path = Path(deploy_path).absolute()
        with tempfile.NamedTemporaryFile(prefix='.deploy-', suffix='.sh', dir=_SOURCE_PATH) as build_script_file:
            build_script_path = Path(build_script_file.name).name
            build_script_file.write(build_script)
            build_script_file.flush()
            context.run(
                f'docker run --rm -w /usr/local/src -v {_SOURCE_PATH}:/usr/local/src -v {deploy_path}:/build '
                'python:3.8-slim '
                f'sh "{build_script_path}"')

        # The `drover` utility configuration may contain files relative to the source working directory.
        with context.cd(str(_SOURCE_PATH)):
            context.run(f'drover --install-path {deploy_path} production')


@task
def request(context):
    with tempfile.NamedTemporaryFile(prefix='output', dir=_SOURCE_PATH) as output_file:
        context.run(
            'aws --region us-east-1 lambda invoke '
            '--function-name "basic-lambda" --invocation-type "RequestResponse" '
            f'{output_file.name}')
        output_file.seek(0)
        print('Lambda Output:', output_file.read(), sep='\n')
