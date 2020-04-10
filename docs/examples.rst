Examples
========

A basic Lambda
--------------
This example outlines how to deploy a basic Python package with no external
dependencies.

Settings
^^^^^^^^
The following ``drover.yml`` settings file demonstrates how to configure a
``staging`` stage that may be used to deploy a Python package to a Lambda named
``basic-lambda`` in the ``us-east-1`` region:

.. code-block:: yaml

   stages:
     staging:
       region_name: us-east-1
       function_name: basic-lambda
       compatible_runtime: python3.8
       function_file_patterns:
       - '^basic_lambda.*'
       function_extra_paths:
       - instance
       upload_bucket:
       region_name: us-east-1
       bucket_name: drover-examples

The ``compatible_runtime`` value will be used to define the compatible runtime
for both the requirements layer (if present) and the Lambda function.

While processing files from the install path (see: ``--install-path`` below),
any files matching regular expressions defined in the
``function_file_patterns`` list will be included in the function; any remaining
files will be included in the requirements layer.

The ``function_extra_paths`` list may contain additional paths to include in
the function layer archive; non-absolute paths will be relative to the current
working directory.

The ``upload_bucket`` map may provide a S3 Bucket name and its associated
region for use when uploading Lambda function and layer archive files.

Command line interface
^^^^^^^^^^^^^^^^^^^^^^
Assuming a Python package exists in the ``basic_lambda`` directory, the
following commands demonstrate a simple Lambda deploy with drover::

    pip install --target install basic_lambda
    drover --install-path install staging

Assuming the Lambda is not already up to date, drover will attempt to upload
the latest source and update the Lambda function::

    Requirements digest: None
    Function digest: 0b37cf78f6ad4c137fb1f77751c0c0e759dd2d6c515937d33fae435b9e091f72
    Skipping requirements upload
    Uploading function archive...
    Failed to upload function archive to bucket; falling back to direct file upload.
    Updating function resource...
    Updated function "basic-lambda" resource; size: 1.78 KiB; ARN: arn:aws:lambda:us-east-1:977874552542:function:basic-lambda