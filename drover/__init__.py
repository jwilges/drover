"""drover: a command-line utility to deploy Python packages to Lambda functions"""
import argparse
import hashlib
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable, List, Mapping, Optional, Pattern, Sequence

import botocore
import boto3
import tqdm
import yaml
from pydantic import BaseModel, ValidationError


__version__ = '0.7.0'
_logger = logging.getLogger(__name__)


class S3BucketPath(BaseModel):
    region_name: str
    bucket_name: str
    prefix: str = ''


class S3BucketFileVersion(BaseModel):
    bucket_name: str
    key: str
    version_id: Optional[str]


class Stage(BaseModel):
    region_name: str
    function_name: str
    compatible_runtime: str
    function_file_patterns: Sequence[Pattern]
    function_extra_paths: Sequence[Path] = []
    package_exclude_patterns: Sequence[Pattern] = [re.compile(r'.*__pycache__.*')]
    upload_bucket: Optional[S3BucketPath]


class Settings(BaseModel):
    stages: Mapping[str, Stage]


@dataclass
class ArchiveMapping:
    source_file_name: Path
    archive_file_name: Path


def format_file_size(size_in_bytes: float):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB'):
        if abs(size_in_bytes) < 1024.0:
            return f'{size_in_bytes:.2f} {unit}'
        size_in_bytes /= 1024.0
    return f'{size_in_bytes:.2f} YiB'


def get_relative_file_names(source_path: Path, exclude_patterns: Sequence[Pattern]) -> Iterable[Path]:
    for root, _directory_names, file_names in os.walk(source_path):
        for file_name in file_names:
            relative_file_name = Path(os.path.join(root, file_name)).relative_to(source_path)
            if not any([pattern.match(str(relative_file_name)) for pattern in exclude_patterns]):
                yield relative_file_name


def write_archive(archive_file_name: Path, archive_mappings: Iterable[ArchiveMapping]):
    with zipfile.ZipFile(archive_file_name, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for mapping in archive_mappings:
            archive.write(filename=mapping.source_file_name, arcname=mapping.archive_file_name)


class UpdateError(RuntimeError):
    """Base update error"""


class Drover:
    def __init__(self, settings: Settings, stage: str, interactive: bool = False):
        self.settings = settings
        self.stage = settings.stages[stage]
        self.interactive = interactive

        self.requirements_layer_name = f'{self.stage.function_name}-requirements'
        self.compatible_runtime_library_path = Drover._get_runtime_library_path(self.stage.compatible_runtime)

        self.lambda_client = boto3.client('lambda', region_name=self.stage.region_name)

    def update(self, install_path: Path):
        package_record_pattern = re.compile(r'\.dist-info/RECORD$')
        def package_record_digest(file_name: Path) -> bytes:
            if package_record_pattern.search(str(file_name)):
                with open(file_name, 'rb') as package_record:
                    return hashlib.sha1(package_record.read()).digest()
            return None

        def extra_file_digest(file_name: Path) -> bytes:
            file_stat = file_name.stat()
            return hashlib.sha1(f'{str(file_name)}{file_stat.st_size}{file_stat.st_mtime}'.encode()).digest()

        requirements_base_path = self.compatible_runtime_library_path
        function_file_patterns = self.stage.function_file_patterns

        requirements_digest = hashlib.sha1()
        requirements_mappings: Sequence[ArchiveMapping] = []
        function_digest = hashlib.sha1()
        function_mappings: Sequence[ArchiveMapping] = []
        for relative_file_name in sorted(get_relative_file_names(install_path, self.stage.package_exclude_patterns)):
            source_file_name = install_path / relative_file_name
            source_file_digest = package_record_digest(source_file_name)
            if any([pattern.match(str(relative_file_name)) for pattern in function_file_patterns]):
                if source_file_digest:
                    function_digest.update(source_file_digest)
                function_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=relative_file_name))
            else:
                if source_file_digest:
                    function_digest.update(source_file_digest)
                requirements_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=requirements_base_path / relative_file_name))
        for extra_path in sorted(self.stage.function_extra_paths):
            for relative_file_name in sorted(get_relative_file_names(extra_path, self.stage.package_exclude_patterns)):
                source_file_name = extra_path / relative_file_name
                source_file_digest = extra_file_digest(source_file_name)
                if source_file_digest:
                    function_digest.update(source_file_digest)
                function_mappings.append(
                    ArchiveMapping(
                        source_file_name=source_file_name,
                        archive_file_name=relative_file_name))
        requirements_digest = requirements_digest.hexdigest()
        function_digest = function_digest.hexdigest()

        _logger.debug(
            'Requirements file mappings:\n%s',
            '\n'.join(f'  {mapping.archive_file_name}: {mapping.source_file_name}' for mapping in requirements_mappings))
        _logger.debug(
            'Function file mappings:\n%s',
            '\n'.join(f'  {mapping.archive_file_name}: {mapping.source_file_name}' for mapping in function_mappings))

        _logger.info('Requirements digest: %s', requirements_digest)
        _logger.info('Function digest: %s', function_digest)

        try:
            function_response = self.lambda_client.get_function(FunctionName=self.stage.function_name)
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
            raise UpdateError(f'Unable to retrieve Lambda function "{self.stage.function_name}": {e}')

        function_arn = function_response['Configuration']['FunctionArn']
        function_layer_arns: List[str] = [layer['Arn'] for layer in function_response['Configuration'].get('Layers', [])]
        function_runtime = function_response['Configuration']['Runtime']
        function_tags: Mapping[str, str] = function_response['Tags'] or {}
        head_requirements_digest = function_tags.get('HeadRequirementsDigest')
        head_requirements_layer_arn = function_tags.get('HeadRequirementsLayerArn')
        head_function_digest = function_tags.get('HeadFunctionDigest')

        head_requirements_layer_arn_missing = True
        if head_requirements_layer_arn:
            try:
                self.lambda_client.get_layer_version_by_arn(Arn=head_requirements_layer_arn)
                head_requirements_layer_arn_missing = False
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                _logger.warning('Unable to retrieve requirements layer "%s"; forcing re-upload. Error: %s',
                                head_requirements_layer_arn, e)

        should_upload_requirements = any((
            not head_requirements_digest,
            not head_requirements_layer_arn,
            head_requirements_layer_arn_missing,
            head_requirements_digest != requirements_digest))
        if should_upload_requirements:
            requirements_layer_arn = self.upload_requirements_archive(requirements_mappings, requirements_digest)
            function_tags['HeadRequirementsDigest'] = requirements_digest
            function_tags['HeadRequirementsLayerArn'] = requirements_layer_arn
        else:
            requirements_layer_arn = head_requirements_layer_arn
            _logger.info('Skipping requirements upload')

        if function_runtime != self.stage.compatible_runtime or requirements_layer_arn not in function_layer_arns:
            try:
                function_layer_arns = [requirements_layer_arn]
                self.lambda_client.update_function_configuration(
                    FunctionName=self.stage.function_name,
                    Runtime=self.stage.compatible_runtime,
                    Layers=function_layer_arns)
                _logger.info('Updated function runtime ("%s") and layers: %s',
                             self.stage.compatible_runtime, function_layer_arns)
            except botocore.exceptions.BotoCoreError as e:
                raise UpdateError(f'Failed to set requirements layer for {self.stage.function_name}: {e}')

        if not head_function_digest or head_function_digest != function_digest:
            self.upload_function_archive(function_mappings, function_digest)
            function_tags['HeadFunctionDigest'] = function_digest
        else:
            _logger.info('Skipping function upload')

        try:
            self.lambda_client.tag_resource(Resource=function_arn, Tags=function_tags)
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
            raise UpdateError(f'Unable to update tags for Lambda function "{self.stage.function_name}": {e}')

    def upload_file_to_bucket(self, file_name: Path, file_size: float, description: str) -> S3BucketFileVersion:
        upload_bucket: S3BucketPath = self.stage.upload_bucket
        s3_client = boto3.client('s3', region_name=upload_bucket.region_name)

        if self.interactive:
            progress = tqdm.tqdm(desc=description, leave=False, total=file_size, unit='B', unit_scale=True)
            callback = progress.update
        else:
            callback = None

        key = f'{upload_bucket.prefix}{file_name.name}'
        s3_client.upload_file(
            Filename=str(file_name),
            Bucket=upload_bucket.bucket_name,
            Key=key,
            Callback=callback)
        response = s3_client.head_object(
            Bucket=upload_bucket.bucket_name,
            Key=key
        )
        return S3BucketFileVersion(
            bucket_name=upload_bucket.bucket_name,
            key=key,
            version_id=response.get('VersionId'))

    def delete_file_from_bucket(self, bucket_file: S3BucketFileVersion):
        upload_bucket = self.stage.upload_bucket
        s3_client = boto3.client('s3', region_name=upload_bucket.region_name)
        arguments = {
            'Bucket': bucket_file.bucket_name,
            'Key': bucket_file.key,
        }
        if bucket_file.version_id:
            arguments['VersionId'] = bucket_file.version_id
        s3_client.delete_object(**arguments)

    def upload_requirements_archive(self, archive_mappings: Sequence[ArchiveMapping], archive_digest: str) -> str:
        archive_handle, archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_requirements-')
        archive_file_name = Path(archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)
            archive_size = float(archive_file_name.stat().st_size)

            if self.stage.upload_bucket:
                try:
                    bucket_file = self.upload_file_to_bucket(archive_file_name, archive_size, description='Upload requirements layer')
                    file_arguments = {
                        'S3Bucket': bucket_file.bucket_name,
                        'S3Key': bucket_file.key,
                    }
                    if bucket_file.version_id:
                        file_arguments['S3ObjectVersion'] = bucket_file.version_id
                except botocore.exceptions.BotoCoreError as e:
                    _logger.error('Failed to upload requirements archive to bucket; falling back to direct file upload.', exc_info=e)
                    bucket_file = None

            if not bucket_file:
                with open(archive_file_name, 'rb') as archive_file:
                    file_arguments = {'ZipFile': archive_file.read()}

            archive_description = f'Requirements layer for {self.stage.function_name}; digest: {archive_digest}'
            try:
                response = self.lambda_client.publish_layer_version(
                    LayerName=self.requirements_layer_name,
                    Description=archive_description,
                    Content=file_arguments,
                    CompatibleRuntimes=[self.stage.compatible_runtime])
            except botocore.exceptions.BotoCoreError as e:
                raise UpdateError(f'Failed to publish requirements layer for {self.stage.function_name}: {e}')
            finally:
                if bucket_file:
                    self.delete_file_from_bucket(bucket_file)

            layer_version_arn = response['LayerVersionArn']
            layer_size_text = format_file_size(float(response['Content']['CodeSize']))
            _logger.info('Published requirements layer "%s"; size: %s; ARN: %s',
                         self.requirements_layer_name, layer_size_text, layer_version_arn)

            return layer_version_arn

        try:
            return _upload()
        finally:
            archive_file_name.unlink()

    def upload_function_archive(self, archive_mappings: Sequence[ArchiveMapping], archive_digest: str) -> str:
        archive_handle, archive_file_name = tempfile.mkstemp(suffix='.zip', prefix='_function-')
        archive_file_name = Path(archive_file_name)

        def _upload() -> str:
            try:
                write_archive(archive_file_name, archive_mappings)
            finally:
                os.close(archive_handle)
            archive_size = float(archive_file_name.stat().st_size)

            if self.stage.upload_bucket:
                try:
                    bucket_file = self.upload_file_to_bucket(archive_file_name, archive_size, description='Upload function')
                    file_arguments = {
                        'S3Bucket': bucket_file.bucket_name,
                        'S3Key': bucket_file.key,
                    }
                    if bucket_file.version_id:
                        file_arguments['S3ObjectVersion'] = bucket_file.version_id
                except botocore.exceptions.BotoCoreError as e:
                    _logger.error('Failed to upload function archive to bucket; falling back to direct file upload.', exc_info=e)
                    bucket_file = None

            if not bucket_file:
                with open(archive_file_name, 'rb') as archive_file:
                    file_arguments = {'ZipFile': archive_file.read()}

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
                    self.delete_file_from_bucket(bucket_file)

            function_arn = response['FunctionArn']
            function_size_text = format_file_size(float(response['CodeSize']))
            _logger.info('Updated function "%s"; size: %s; ARN: %s',
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


def main():
    logging.basicConfig(format='%(message)s')
    _logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description=__doc__.partition('\n')[0])
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--settings-file', default=Path('drover.yml'), type=Path,
                        help='Settings file name (default: "drover.yml")')
    parser.add_argument('--install-path', default=Path(), type=Path,
                        help='Package install path (e.g. from "pip install -t"; default: working directory)')
    parser.add_argument('stage', type=str)
    arguments = parser.parse_args()

    settings_file_name = arguments.settings_file
    install_path: Path = arguments.install_path

    settings: Settings = None
    try:
        with open(settings_file_name, 'r') as settings_file:
            settings = Settings.parse_obj(yaml.safe_load(settings_file))
    except (ValueError, ValidationError) as e:
        _logger.error('Settings file is invalid: %s', e)
        sys.exit(1)
    except FileNotFoundError as e:
        _logger.error('Settings file does not exist: %s', e)
        sys.exit(1)

    drover = Drover(settings, arguments.stage, interactive=True)
    drover.update(install_path)
