import tempfile
from pathlib import Path

from invoke import task

_SOURCE_PATH = Path(__file__).parent.absolute()


@task
def deploy(context):
    with tempfile.TemporaryDirectory(prefix='.deploy-', dir=_SOURCE_PATH) as deploy_path:
        deploy_path = Path(deploy_path).absolute()
        context.run(
            f'docker run -v {_SOURCE_PATH}:/var/task -v {deploy_path}:/build '
            'lambci/lambda:build-python3.8 '
            'sh -c "set -x && '
            'python -m venv --clear /tmp/venv && '
            '/tmp/venv/bin/pip install wheel && '
            '/tmp/venv/bin/pip install --target /build -r requirements.txt ."')

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
