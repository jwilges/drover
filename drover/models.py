"""Models for settings and Amazon Web Services interactions"""
import re
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional, Pattern, Sequence, Union

from pydantic import BaseModel, Field, validator


DEFAULT_EXCLUDES_BY_RUNTIME: Mapping[Pattern, Sequence[Pattern]] = {
    re.compile(r'^python\d+\.\d+$'): [re.compile(r'.*__pycache__.*')],
}


class S3BucketFileVersion(BaseModel):
    bucket_name: str
    key: str
    version_id: Optional[str]


class S3BucketPath(BaseModel):
    region_name: str
    bucket_name: str
    prefix: str = ''


class UnmappedFileBehavior(str, Enum):
    ignore = 'ignore'
    error = 'error'
    map_to_function = 'map_to_function'
    map_to_layer = 'map_to_layer'


class PackageFunction(BaseModel):
    name: str
    compatible_runtime: str
    includes: Sequence[Pattern] = Field(default_factory=list)
    excludes: Sequence[Pattern] = Field(default_factory=list)
    extra_paths: Sequence[Path] = Field(default_factory=list)


class PackageLayer(BaseModel):
    name: str
    compatible_runtimes: Sequence[str] = Field(default_factory=list)
    includes: Sequence[Pattern] = Field(default_factory=list)
    excludes: Sequence[Pattern] = Field(default_factory=list)


class PackageLayerReference(BaseModel):
    arn: str


class Package(BaseModel):
    region_name: str
    function: Optional[PackageFunction]
    layers: Sequence[Union[PackageLayer, PackageLayerReference]] = Field(default_factory=list)
    unmapped_file_behavior: UnmappedFileBehavior = UnmappedFileBehavior.ignore
    upload_bucket: Optional[S3BucketPath]
    publish: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.unmapped_file_behavior == UnmappedFileBehavior.map_to_layer:
            if self.function:
                unmapped_file_layer_name = f'{self.function.name}-other'
                unmapped_file_runtimes = [self.function.compatible_runtime]
            else:
                unmapped_file_layer_name = f'{self.layers[0].name}-other'
                unmapped_file_runtimes = self.layers[0].compatible_runtimes
            self.layers += [
                PackageLayer(
                    name=unmapped_file_layer_name, compatible_runtimes=unmapped_file_runtimes
                )
            ]

        package_layers = [layer for layer in self.layers if isinstance(layer, PackageLayer)]
        for layer in package_layers:
            if not layer.compatible_runtimes:
                layer.compatible_runtimes = [self.function.compatible_runtime] if self.function else []

        if self.function and not self.function.excludes:
            default_excludes = []
            for runtime_pattern, runtime_excludes in DEFAULT_EXCLUDES_BY_RUNTIME.items():
                if runtime_pattern.match(self.function.compatible_runtime):
                    default_excludes.extend(runtime_excludes)
            self.function.excludes = default_excludes

    @validator('layers', always=True)
    @classmethod
    def validate_function_or_layers_exist(cls, layers, values):
        function = values.get('function')
        if not layers and not function:
            raise ValueError('at least one layer must be defined if no function is defined')
        return layers


class Settings(BaseModel):
    packages: Mapping[str, Package]
