Overview
========

Background
----------
This utility aims to provide a simple, repeatable, and efficient process for
deploying a Python package as a Lambda_.

To encourage separating infrequently changing Python dependencies in a distinct
"requirements" layer, by default Drover requires a list of regular expressions
to define which files to include in the Lambda function; all other files are
placed in a requirements layer that is then attached to the Lambda function.

Next, Drover generates and stores hashes for both the Lambda function and the
requirements layer. This allows Drover to avoid redundantly updating the Lambda
function and/or requirements layer if no package contents have changed.

As much as possible, Drover avoids altering existing infrastructure.
Infrastructure utilities such as Terraform_ may be used to create a Lambda and
manage its surrounding resources and Dover may be used to update the Lambda
function as well as its layers.

.. _Lambda: https://aws.amazon.com/lambda
.. _Terraform: https://github.com/hashicorp/terraform

.. toctree::
   :maxdepth: 1
   :caption: Introduction
   :hidden:

   self
   examples

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :hidden:

   modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
