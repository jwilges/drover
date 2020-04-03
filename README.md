# drover
*drover: a command-line utility to deploy Python packages to Lambda functions*

[![circleci](https://circleci.com/gh/jwilges/drover/tree/master.svg?style=shield)](https://circleci.com/gh/jwilges/drover/tree/master)
[![codecov](https://codecov.io/gh/jwilges/drover/branch/master/graph/badge.svg)](https://codecov.io/gh/jwilges/drover/branch/master)

## Supported Platforms
This utility has been tested on macOS Catalina 10.15.

## Usage
### Development Environment
Initialize a development environment by executing `nox -s dev-3.8`; the
`drover` utility will be installed in the `.nox/dev-3-8` Python virtual
environment binary path.