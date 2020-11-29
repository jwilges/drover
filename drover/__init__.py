"""drover: a command-line utility to deploy Python packages to Lambda functions"""
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import boto3
import botocore
import tqdm
from pydantic import BaseModel

from drover.io import (
    ArchiveFileMapping,
    format_file_size,
    write_archive,
)
from drover.models import S3BucketFileVersion, S3BucketPath, Settings, Package, PackageFunction, PackageLayer
from drover.deployment import Deployment
from drover.packaging import get_package_archive_metadata

_logger = logging.getLogger(__name__)


class SettingsError(RuntimeError):
    """Base settings error"""


class UpdateError(RuntimeError):
    """Base update error"""


@dataclass
class LambdaFunctionDescriptor:
    arn: str
    layer_arns: Sequence[str]
    runtime: str
    tags: Mapping[str, str]

    @property
    def digest(self) -> str:
        return self.tags.get('HeadFunctionDigest') or ''


class Drover:
    """An interface to efficiently publish and update a Lambda function and requirements layer
    representation of a Python package directory"""
    def __init__(self, settings: Settings, package_name: str, interactive: bool = False):
        self.settings = settings
        self.package_name = package_name
        self.interactive = interactive

        if package_name not in self.settings.packages:
            raise SettingsError(f'Invalid package name: {package_name}')

        self.package = self.settings.packages[package_name]
        self.aws_client_config = botocore.config.Config(
            region_name=self.package.region_name,
            retries={
                'max_attempts': 10,
                'mode': 'standard'
            }
        )
        self.lambda_client = boto3.client('lambda', config=self.aws_client_config)

    def update(self, install_path: Path) -> None:
        """Publish and/or update a Lambda function and/or requirements layer representation of a Python package directory

        Args:
            install_path: a Python package directory (e.g. via `pip install -t <install_path>`)"""

        if not install_path.is_dir():
            raise UpdateError(f'Install path is invalid: {install_path}')

        local_metadata = get_package_archive_metadata(self.package, install_path)
        deployment = Deployment(self.aws_client_config, self.package, self.package_name)
        deployment_state = deployment.get_state()
        # write_archive(Path(__file__).parent / 'fun.zip', extra.mappings + function.mappings)
        # write_archive(Path(__file__).parent / 'req.zip', layer.mappings)

        stale_layer_names: Sequence[str]
        if not deployment_state or not deployment_state.metadata:
            is_function_stale = self.package.function is not None
            is_function_config_stale = is_function_stale
            stale_layer_names = [layer.name for layer in self.package.layers if isinstance(layer, PackageLayer)]
        else:
            is_function_stale = deployment_state.metadata.is_function_stale(local_metadata)
            is_function_config_stale = len(deployment_state.get_stale_function_attributes()) > 0
            stale_layer_names = deployment_state.metadata.get_stale_layer_names(local_metadata)

        # if function_runtime != self.stage.compatible_runtime or function_layer_arns != head_function_layer_arns:
        #     _logger.info('Updating function resource...')
        #     try:
        #         self.lambda_client.update_function_configuration(
        #             FunctionName=self.stage.function_name,
        #             Runtime=self.stage.compatible_runtime,
        #             Layers=head_function_layer_arns)
        #     except botocore.exceptions.BotoCoreError as e:
        #         raise UpdateError(f'Failed to update function "{self.stage.function_name}" runtime and layers: {e}') from e
        #     _logger.info('Updated function "%s" resource; runtime: "%s"; layers: %s',
        #                  self.stage.function_name, self.stage.compatible_runtime, head_function_layer_arns)

        # if not head_function_digest or head_function_digest != mappings.function_digest:
        #     self._upload_function_archive(mappings.function_mappings)
        #     function_tags['HeadFunctionDigest'] = mappings.function_digest
        # else:
        #     _logger.info('Skipping function upload')

        # write_archive(Path(__file__).parent / 'req.zip', layer.mappings)

        # function_name = self.package.function.name if self.package.function else ''
        # function_state = None
        # if function_name:
        #     try:
        #         function_response = self.lambda_client.get_function(FunctionName=function_name)
        #     except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        #         raise UpdateError(f'Unable to retrieve Lambda function "{function_name}": {e}') from e
        #     else:
        #         function_state = LambdaFunctionDescriptor(
        #             arn=function_response['Configuration']['FunctionArn'],
        #             layer_arns=[layer['Arn'] for layer in function_response['Configuration'].get('Layers') or []],
        #             runtime=function_response['Configuration']['Runtime'],
        #             tags=function_response.get('Tags') or {}
        #         )
        # head_requirements_digest = function_tags.get('HeadRequirementsDigest')
        # head_requirements_layer_arn = function_tags.get('HeadRequirementsLayerArn')
        # head_function_digest = function_tags.get('HeadFunctionDigest')

        # head_requirements_layer_arn_missing = True
        # if head_requirements_layer_arn:
        #     try:
        #         self.lambda_client.get_layer_version_by_arn(Arn=head_requirements_layer_arn)
        #         head_requirements_layer_arn_missing = False
        #     except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        #         _logger.warning('Unable to retrieve requirements layer "%s"; forcing re-upload.',
        #                         head_requirements_layer_arn)
        #         _logger.debug('', exc_info=e)

        # should_upload_requirements = mappings.requirements_mappings and any((
        #     not head_requirements_digest,
        #     not head_requirements_layer_arn,
        #     head_requirements_layer_arn_missing,
        #     head_requirements_digest != mappings.requirements_digest))
        # if should_upload_requirements:
        #     requirements_layer_arn = self._upload_requirements_archive(mappings.requirements_mappings,
        #                                                                mappings.requirements_digest)
        #     function_tags['HeadRequirementsDigest'] = mappings.requirements_digest
        #     function_tags['HeadRequirementsLayerArn'] = requirements_layer_arn
        # else:
        #     requirements_layer_arn = head_requirements_layer_arn
        #     function_tags.pop('HeadRequirementsDigest', None)
        #     function_tags.pop('HeadRequirementsLayerArn', None)
        #     _logger.info('Skipping requirements upload')

        # head_function_layer_arns = [arn for arn in (*self.stage.supplemental_layer_arns,
        #                                             head_requirements_layer_arn) if arn]

        # if function_runtime != self.stage.compatible_runtime or function_layer_arns != head_function_layer_arns:
        #     _logger.info('Updating function resource...')
        #     try:
        #         self.lambda_client.update_function_configuration(
        #             FunctionName=self.stage.function_name,
        #             Runtime=self.stage.compatible_runtime,
        #             Layers=head_function_layer_arns)
        #     except botocore.exceptions.BotoCoreError as e:
        #         raise UpdateError(f'Failed to update function "{self.stage.function_name}" runtime and layers: {e}') from e
        #     _logger.info('Updated function "%s" resource; runtime: "%s"; layers: %s',
        #                  self.stage.function_name, self.stage.compatible_runtime, head_function_layer_arns)

        # if not head_function_digest or head_function_digest != mappings.function_digest:
        #     self._upload_function_archive(mappings.function_mappings)
        #     function_tags['HeadFunctionDigest'] = mappings.function_digest
        # else:
        #     _logger.info('Skipping function upload')

        # function_tags = {key: value for key, value in function_tags.items() if value}
        # if function_tags:
        #     try:
        #         self.lambda_client.tag_resource(Resource=function_arn, Tags=function_tags)
        #     except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        #         raise UpdateError(f'Unable to update tags for Lambda function "{self.stage.function_name}": {e}') from e

    def _upload_file_to_bucket(self, upload_bucket: S3BucketPath, file_name: Path) -> S3BucketFileVersion:
        s3_client = boto3.client('s3', config=self.aws_client_config, region_name=upload_bucket.region_name)
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

    def _delete_file_from_bucket(self, upload_bucket: S3BucketPath, bucket_file: S3BucketFileVersion):
        s3_client = boto3.client('s3', config=self.aws_client_config, region_name=upload_bucket.region_name)
        arguments = {
            'Bucket': bucket_file.bucket_name,
            'Key': bucket_file.key,
        }
        if bucket_file.version_id:
            arguments['VersionId'] = bucket_file.version_id
        s3_client.delete_object(**arguments)

    def _upload_requirements_archive(self, archive_mappings: Sequence[ArchiveFileMapping], archive_digest: str) -> str:
        archive_handle, _archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_requirements-')
        archive_file_name = Path(_archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)

            if self.stage.upload_bucket:
                _logger.info('Uploading requirements layer archive...')
                try:
                    bucket_file = self._upload_file_to_bucket(self.stage.upload_bucket, archive_file_name)
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
                raise UpdateError(f'Failed to publish requirements layer for {self.stage.function_name}: {e}') from e
            finally:
                if self.stage.upload_bucket and bucket_file:
                    self._delete_file_from_bucket(self.stage.upload_bucket, bucket_file)

            layer_version_arn = response['LayerVersionArn']
            layer_size_text = format_file_size(float(response['Content']['CodeSize']))
            _logger.info('Published requirements layer "%s"; size: %s; ARN: %s',
                         self.stage.requirements_layer_name, layer_size_text, layer_version_arn)

            return layer_version_arn

        try:
            return _upload()
        finally:
            archive_file_name.unlink()

    def _upload_function_archive(self, archive_mappings: Sequence[ArchiveFileMapping]) -> str:
        archive_handle, _archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_function-')
        archive_file_name = Path(_archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)

            if self.stage.upload_bucket:
                _logger.info('Uploading function archive...')
                try:
                    bucket_file = self._upload_file_to_bucket(self.stage.upload_bucket, archive_file_name)
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
                raise RuntimeError(f'Failed to update function code for {self.stage.function_name}: {e}') from e
            finally:
                if self.stage.upload_bucket and bucket_file:
                    self._delete_file_from_bucket(self.stage.upload_bucket, bucket_file)

            function_arn = response['FunctionArn']
            function_size_text = format_file_size(float(response['CodeSize']))
            _logger.info('Updated function "%s" resource; size: %s; ARN: %s',
                         self.stage.function_name, function_size_text, function_arn)

            return function_arn

        try:
            return _upload()
        finally:
            archive_file_name.unlink()

    def _publish(self, function_sha256: str, function_revision_id: str, description: str):
        return self.lambda_client.publish_version(
            FunctionName=self.package.function.name,
            CodeSha256=function_sha256,
            RevisionId=function_revision_id,
            Description=description,
        )
