import codecs
import re
import sys
from pathlib import Path
from typing import List, MutableMapping, Optional, Sequence, Tuple, Type

import setuptools


def _read(source_file_name: Path):
    if not source_file_name.is_file():
        raise FileNotFoundError(source_file_name)
    with codecs.open(str(source_file_name), 'r') as source_file:
        return source_file.read()


HERE = Path().parent.absolute()
PACKAGE_PATH = HERE / 'drover'

LONG_DESCRIPTION = _read(HERE / 'README.md')
METADATA = {
    'name': 'drover',
    'author': 'Jeffrey Wilges',
    'author_email': 'jeffrey@wilges.com',
    'description': 'drover is a command-line utility for deploying Python packages to Lambda functions.',
    'url': 'https://github.com/jwilges/drover',
    'license': 'BSD'
}
METADATA_TEMPLATE = '\n'.join((
    "VERSION = '{version}'",
    *(
        f"{key.upper()} = '{value.replace('{', '{{').replace('}', '}}')}'"
        for key, value in METADATA.items()
    ),
    '' # final newline
))

OPTIONAL_COMMAND_CLASSES: MutableMapping[str, Type] = {}
OPTIONAL_COMMAND_OPTIONS: MutableMapping[str, MutableMapping[str, Sequence[str]]] = {}

try:
    from sphinx.setup_command import BuildDoc
    OPTIONAL_COMMAND_CLASSES['build_sphinx'] = BuildDoc
    OPTIONAL_COMMAND_OPTIONS['build_sphinx'] = {
        'source_dir': ('setup.py', 'docs'),
        'build_dir': ('setup.py', 'docs/_build')
    }
except ImportError:
    pass


class ValidateTagCommand(setuptools.Command):
    """A validator that ensures the package version both is in the canonical form per
    PEP-440 and matches the current git tag"""
    description = 'validate that the package version matches the current git tag'
    user_options: List[Tuple[str, Optional[str], str]] = [
        ('output-azure-variables', None, 'Output Azure Pipeline version variables'),
    ]

    VERSION_PATTERN = r'''
        v?
        (?:
            (?:(?P<epoch>[0-9]+)!)?                           # epoch
            (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
            (?P<pre>                                          # pre-release
                [-_\.]?
                (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
                [-_\.]?
                (?P<pre_n>[0-9]+)?
            )?
            (?P<post>                                         # post release
                (?:-(?P<post_n1>[0-9]+))
                |
                (?:
                    [-_\.]?
                    (?P<post_l>post|rev|r)
                    [-_\.]?
                    (?P<post_n2>[0-9]+)?
                )
            )?
            (?P<dev>                                          # dev release
                [-_\.]?
                (?P<dev_l>dev)
                [-_\.]?
                (?P<dev_n>[0-9]+)?
            )?
        )
        (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
    '''
    VERSION_FORMAT = re.compile(
        r'^\s*' + VERSION_PATTERN + r'\s*$',
        re.VERBOSE | re.IGNORECASE,
    )

    def initialize_options(self):
        self.output_azure_variables = False

    def finalize_options(self):
        pass

    def run(self):
        """Warn and exit if the package version either:
            a) is not in the canonical format per PEP-440 or,
            b) does not match any HEAD git tag version."""
        import setuptools_scm
        version = setuptools_scm.get_version(relative_to=Path(__file__))

        if self.output_azure_variables:
            print(f'##vso[task.setvariable variable=is_prerelease;isOutput=true;]{self.is_prerelease(version)!s}')

        if not self.is_canonical(version):
            self.warn(f'package version ({version}) is not in the canonical format per PEP-440')
            sys.exit(1)

    @classmethod
    def is_prerelease(cls, version: str) -> bool:
        """Return true if `version` is a 'pre', 'dev', or 'local' release per PEP-440."""
        version_match = cls.VERSION_FORMAT.match(version)
        return (
            version_match is None or
            any(
                value for key, value in version_match.groupdict().items()
                if key in ('pre', 'dev', 'local')
            )
        )

    @staticmethod
    def is_canonical(version: str) -> bool:
        """Return true if `version` is canonical per PEP-440."""
        return re.match(r'^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$', version) is not None


setuptools.setup(
    **METADATA,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': ['drover=drover.cli:main'],
    },
    use_scm_version={
        'relative_to': Path(__file__),
        'write_to': PACKAGE_PATH / '__metadata__.py',
        'write_to_template': METADATA_TEMPLATE,
    },
    setup_requires=['setuptools_scm'],
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
        'Environment :: Console',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Networking',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities'
    ],
    cmdclass={
        'validate_tag': ValidateTagCommand,
        **OPTIONAL_COMMAND_CLASSES
    },
    command_options={
        **OPTIONAL_COMMAND_OPTIONS
    },
)
