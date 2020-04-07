import ast
import codecs
import os.path

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
VERSION = get_version(HERE, 'basic_lambda', '__init__.py')
LONG_DESCRIPTION = read(HERE, 'README.md')


setuptools.setup(
    name='basic_lambda',
    version=VERSION,
    author='Jeffrey Wilges',
    author_email='jeffrey@wilges.com',
    description='a basic Lambda that returns its version',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/jwilges/drover',
    license='BSD',
    packages=setuptools.find_packages(exclude=['tests*']),
    python_requires='>=3.8',
    install_requires=[],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.8',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking',
    ],
)
