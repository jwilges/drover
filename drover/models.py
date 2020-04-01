"""Models for settings and Amazon Web Services interactions"""
import re
from pathlib import Path
from typing import Mapping, Optional, Pattern, Sequence

from pydantic import BaseModel


class S3BucketFileVersion(BaseModel):
    bucket_name: str
    key: str
    version_id: Optional[str]


class S3BucketPath(BaseModel):
    region_name: str
    bucket_name: str
    prefix: str = ''


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
