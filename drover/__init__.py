"""drover: a command-line utility to deploy Python packages to Lambda functions"""
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from http import HTTPStatus
from io import StringIO
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable, List, Mapping, Optional, Pattern, Sequence

import botocore
import boto3
import tqdm
from pydantic import BaseModel

from drover.io import (ArchiveMapping, FunctionLayerMappings,
                       format_file_size, get_digest, get_relative_file_names, write_archive)
from drover.models import S3BucketFileVersion, S3BucketPath, Settings, Stage

__version__ = '0.7.1'
_logger = logging.getLogger(__name__)


class SettingsError(RuntimeError):
    """Base settings error"""


class UpdateError(RuntimeError):
    """Base update error"""


class Drover:
    """An interface to efficiently publish and update a Lambda function and requirements layer
    representation of a Python package directory"""
    def __init__(self, settings: Settings, stage: str, interactive: bool = False):
        self.settings = settings
        self.interactive = interactive

        if stage not in self.settings.stages:
            raise SettingsError(f'Invalid stage name: {stage}')

        self.stage = self.settings.stages[stage]
        self.compatible_runtime_library_path = Drover._get_runtime_library_path(self.stage.compatible_runtime)
        self.lambda_client = boto3.client('lambda', region_name=self.stage.region_name)

    def _get_function_layer_mappings(self, install_path: Path) -> FunctionLayerMappings:
        requirements_base_path = self.compatible_runtime_library_path
        function_file_patterns = self.stage.function_file_patterns

        requirements_mappings: List[ArchiveMapping] = []
        function_mappings: List[ArchiveMapping] = []
        for relative_file_name in get_relative_file_names(install_path, self.stage.package_exclude_patterns):
            source_file_name = install_path / relative_file_name
            if any([pattern.match(str(relative_file_name)) for pattern in function_file_patterns]):
                function_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=relative_file_name))
            else:
                requirements_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=requirements_base_path / relative_file_name))
        for extra_path in self.stage.function_extra_paths:
            for relative_file_name in get_relative_file_names(extra_path, self.stage.package_exclude_patterns):
                source_file_name = extra_path / relative_file_name
                function_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=relative_file_name))

        requirements_digest = get_digest((mapping.source_file_name for mapping in requirements_mappings))
        function_digest = get_digest((mapping.source_file_name for mapping in function_mappings))

        if _logger.isEnabledFor(logging.DEBUG):
            def _log(header: str, mappings: Sequence[ArchiveMapping]):
                with StringIO() as message:
                    message.write(header)
                    for mapping in sorted(mappings, key=lambda item: item.archive_file_name):
                        message.write(f'  {mapping.archive_file_name}: {mapping.source_file_name}\n')
                    _logger.debug(message.getvalue())
            _log('Requirements file mappings:\n', requirements_mappings)
            _log('Function file mappings:\n', function_mappings)

        _logger.info('Requirements digest: %s', requirements_digest)
        _logger.info('Function digest: %s', function_digest)

        return FunctionLayerMappings(
            function_mappings=function_mappings,
            function_digest=function_digest,
            requirements_mappings=requirements_mappings,
            requirements_digest=requirements_digest)

    def update(self, install_path: Path) -> None:
        """Publish and/or update a Lambda function and/or requirements layer representation of a Python package directory

        Args:
            install_path: a Python package directory (e.g. via `pip install -t <install_path>`)"""

        if not install_path.is_dir():
            raise UpdateError(f'Install path is invalid: {install_path}')

        mappings = self._get_function_layer_mappings(install_path)

        try:
            function_response = self.lambda_client.get_function(FunctionName=self.stage.function_name)
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
            raise UpdateError(f'Unable to retrieve Lambda function "{self.stage.function_name}": {e}')

        function_arn = function_response['Configuration']['FunctionArn']
        function_layer_arns: List[str] = [layer['Arn'] for layer in function_response['Configuration'].get('Layers', [])]
        function_runtime = function_response['Configuration']['Runtime']
        function_tags: Mapping[str, str] = function_response.get('Tags', {})
        head_requirements_digest = function_tags.get('HeadRequirementsDigest')
        head_requirements_layer_arn = function_tags.get('HeadRequirementsLayerArn')
        head_function_layer_arns = [arn for arn in (*self.stage.supplemental_layer_arns,
                                                    head_requirements_layer_arn) if arn]
        head_function_digest = function_tags.get('HeadFunctionDigest')

        head_requirements_layer_arn_missing = True
        if head_requirements_layer_arn:
            try:
                self.lambda_client.get_layer_version_by_arn(Arn=head_requirements_layer_arn)
                head_requirements_layer_arn_missing = False
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                _logger.warning('Unable to retrieve requirements layer "%s"; forcing re-upload.',
                                head_requirements_layer_arn)
                _logger.debug('', exc_info=e)

        should_upload_requirements = mappings.requirements_mappings and any((
            not head_requirements_digest,
            not head_requirements_layer_arn,
            head_requirements_layer_arn_missing,
            head_requirements_digest != mappings.requirements_digest))
        if should_upload_requirements:
            requirements_layer_arn = self._upload_requirements_archive(mappings.requirements_mappings,
                                                                       mappings.requirements_digest)
            function_tags['HeadRequirementsDigest'] = mappings.requirements_digest
            function_tags['HeadRequirementsLayerArn'] = requirements_layer_arn
        else:
            requirements_layer_arn = head_requirements_layer_arn
            function_tags.pop('HeadRequirementsDigest', None)
            function_tags.pop('HeadRequirementsLayerArn', None)
            _logger.info('Skipping requirements upload')

        if function_runtime != self.stage.compatible_runtime or function_layer_arns != head_function_layer_arns:
            _logger.info('Updating function resource...')
            try:
                self.lambda_client.update_function_configuration(
                    FunctionName=self.stage.function_name,
                    Runtime=self.stage.compatible_runtime,
                    Layers=head_function_layer_arns)
            except botocore.exceptions.BotoCoreError as e:
                raise UpdateError(f'Failed to update function "{self.stage.function_name}" runtime and layers: {e}')
            _logger.info('Updated function "%s" resource; runtime: "%s"; layers: %s',
                         self.stage.function_name, self.stage.compatible_runtime, function_layer_arns)

        if not head_function_digest or head_function_digest != mappings.function_digest:
            self._upload_function_archive(mappings.function_mappings)
            function_tags['HeadFunctionDigest'] = mappings.function_digest
        else:
            _logger.info('Skipping function upload')

        function_tags = {key: value for key, value in function_tags.items() if value}
        if function_tags:
            try:
                self.lambda_client.tag_resource(Resource=function_arn, Tags=function_tags)
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                raise UpdateError(f'Unable to update tags for Lambda function "{self.stage.function_name}": {e}')

    def _upload_file_to_bucket(self, file_name: Path) -> S3BucketFileVersion:
        upload_bucket: S3BucketPath = self.stage.upload_bucket
        s3_client = boto3.client('s3', region_name=upload_bucket.region_name)
        file_size = float(file_name.stat().st_size)
        key = f'{upload_bucket.prefix}{file_name.name}'
        with tqdm.tqdm(total=file_size, unit='B', unit_divisor=1024, unit_scale=True, leave=True,
                       disable=not self.interactive) as progress:
            s3_client.upload_file(
                Filename=str(file_name),
                Bucket=upload_bucket.bucket_name,
                Key=key,
                Callback=progress.update)

        response = s3_client.head_object(
            Bucket=upload_bucket.bucket_name,
            Key=key
        )
        return S3BucketFileVersion(
            bucket_name=upload_bucket.bucket_name,
            key=key,
            version_id=response.get('VersionId'))

    def _delete_file_from_bucket(self, bucket_file: S3BucketFileVersion):
        upload_bucket = self.stage.upload_bucket
        s3_client = boto3.client('s3', region_name=upload_bucket.region_name)
        arguments = {
            'Bucket': bucket_file.bucket_name,
            'Key': bucket_file.key,
        }
        if bucket_file.version_id:
            arguments['VersionId'] = bucket_file.version_id
        s3_client.delete_object(**arguments)

    def _upload_requirements_archive(self, archive_mappings: Sequence[ArchiveMapping], archive_digest: str) -> str:
        archive_handle, archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_requirements-')
        archive_file_name = Path(archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)

            if self.stage.upload_bucket:
                _logger.info('Uploading requirements layer archive...')
                try:
                    bucket_file = self._upload_file_to_bucket(archive_file_name)
                    file_arguments = {
                        'S3Bucket': bucket_file.bucket_name,
                        'S3Key': bucket_file.key,
                    }
                    if bucket_file.version_id:
                        file_arguments['S3ObjectVersion'] = bucket_file.version_id
                except (botocore.exceptions.ClientError, boto3.exceptions.S3UploadFailedError) as e:
                    _logger.error('Failed to upload requirements archive to bucket; falling back to direct file upload.')
                    _logger.debug('', exc_info=e)
                    bucket_file = None

            if not bucket_file:
                with open(archive_file_name, 'rb') as archive_file:
                    file_arguments = {'ZipFile': archive_file.read()}

            archive_description = f'Requirements layer for {self.stage.function_name}; digest: {archive_digest}'
            _logger.info('Publishing requirements layer...')
            try:
                response = self.lambda_client.publish_layer_version(
                    LayerName=self.stage.requirements_layer_name,
                    Description=archive_description,
                    Content=file_arguments,
                    CompatibleRuntimes=[self.stage.compatible_runtime])
            except botocore.exceptions.BotoCoreError as e:
                raise UpdateError(f'Failed to publish requirements layer for {self.stage.function_name}: {e}')
            finally:
                if bucket_file:
                    self._delete_file_from_bucket(bucket_file)

            layer_version_arn = response['LayerVersionArn']
            layer_size_text = format_file_size(float(response['Content']['CodeSize']))
            _logger.info('Published requirements layer "%s"; size: %s; ARN: %s',
                         self.stage.requirements_layer_name, layer_size_text, layer_version_arn)

            return layer_version_arn

        try:
            return _upload()
        finally:
            archive_file_name.unlink()

    def _upload_function_archive(self, archive_mappings: Sequence[ArchiveMapping]) -> str:
        archive_handle, archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_function-')
        archive_file_name = Path(archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)

            if self.stage.upload_bucket:
                _logger.info('Uploading function archive...')
                try:
                    bucket_file = self._upload_file_to_bucket(archive_file_name)
                    file_arguments = {
                        'S3Bucket': bucket_file.bucket_name,
                        'S3Key': bucket_file.key,
                    }
                    if bucket_file.version_id:
                        file_arguments['S3ObjectVersion'] = bucket_file.version_id
                except (botocore.exceptions.ClientError, boto3.exceptions.S3UploadFailedError) as e:
                    _logger.error('Failed to upload function archive to bucket; falling back to direct file upload.')
                    _logger.debug('', exc_info=e)
                    bucket_file = None

            if not bucket_file:
                with open(archive_file_name, 'rb') as archive_file:
                    file_arguments = {'ZipFile': archive_file.read()}

            _logger.info('Updating function resource...')
            try:
                response = self.lambda_client.update_function_code(
                    FunctionName=self.stage.function_name,
                    Publish=False,
                    DryRun=False,
                    **file_arguments)
            except botocore.exceptions.BotoCoreError as e:
                raise RuntimeError(f'Failed to update function code for {self.stage.function_name}: {e}')
            finally:
                if bucket_file:
                    self._delete_file_from_bucket(bucket_file)

            function_arn = response['FunctionArn']
            function_size_text = format_file_size(float(response['CodeSize']))
            _logger.info('Updated function "%s" resource; size: %s; ARN: %s',
                         self.stage.function_name, function_size_text, function_arn)

            return function_arn

        try:
            return _upload()
        finally:
            archive_file_name.unlink()

    @staticmethod
    def _get_runtime_library_path(runtime: str) -> Path:
        python_pattern = re.compile(r'^python\d+\.\d+$')
        if python_pattern.match(runtime):
            return Path('python')
        raise NotImplementedError(f'Unsupported runtime: {runtime}')
