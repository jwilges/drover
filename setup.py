import ast
import codecs
import distutils
import os.path
import subprocess
import sys

import setuptools


def read(*path_parts, iterate_lines=False):
    source_file_name = os.path.join(*path_parts)
    if not os.path.isfile(source_file_name):
        raise FileNotFoundError(source_file_name)
    with codecs.open(source_file_name, 'r') as source_file:
        return source_file.readlines() if iterate_lines else source_file.read()


def get_version(*path_parts) -> str:
    # See: <https://packaging.python.org/guides/single-sourcing-package-version/>
    for line in read(*path_parts, iterate_lines=True):
        if line.startswith('__version__'):
            return ast.parse(line).body[0].value.s
    raise RuntimeError('Unable to determine version.')


HERE = os.path.abspath(os.path.dirname(__file__))
VERSION = get_version(HERE, 'drover', '__init__.py')
LONG_DESCRIPTION = read(HERE, 'README.md')


class ValidateTagCommand(distutils.cmd.Command):
    """A validator that ensures the package version matches the current git tag"""
    description = 'validate that the package version matches the current git tag'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run command."""
        git_tag_process = subprocess.run(['git', 'tag', '--list', '--points-at', 'HEAD'],
                                         check=False, capture_output=True, universal_newlines=True)

        if git_tag_process.returncode != 0:
            self.warn(f'failed to execute `git tag` command')
            sys.exit(git_tag_process.returncode)

        git_tags = [tag.strip().lstrip('v') for tag in git_tag_process.stdout.splitlines()]
        if VERSION not in git_tags:
            self.warn(f'package version ({VERSION}) does not match any HEAD git tag version (tag versions: {git_tags})')
            sys.exit(1)


setuptools.setup(
    name='drover',
    version=VERSION,
    author='Jeffrey Wilges',
    author_email='jeffrey@wilges.com',
    description='a command-line utility to deploy Python packages to Lambda functions',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/jwilges/drover',
    license='BSD',
    packages=setuptools.find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': ['drover=drover.cli:main'],
    },
    python_requires='>=3.6',
    install_requires=[
        'boto3>=1.12',
        'botocore>=1.15',
        'pydantic>=1.4',
        'pyyaml>=5.3',
        'tqdm>=4.44',
        'dataclasses; python_version < "3.7"'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Environment :: Console',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities'
    ],
    cmdclass={
        'validate_tag': ValidateTagCommand
    }
)
