import itertools
import logging
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import List, Optional, Sequence

from drover.io import (
    ArchiveDescriptor,
    ArchiveFileMapping,
    ArchiveMapResult,
    get_digest,
    iter_file_names,
    map_archive,
)
from drover.models import Package, PackageFunction, PackageLayer, UnmappedFileBehavior

_logger = logging.getLogger(__name__)


@dataclass
class FunctionArchiveMetadata:
    function: PackageFunction
    archive: ArchiveDescriptor


@dataclass
class LayerArchiveMetadata:
    layer: PackageLayer
    archive: ArchiveDescriptor


@dataclass
class PackageArchiveMetadata:
    """Function and layer archive metadata (e.g. file mappings and digests)"""
    function: Optional[FunctionArchiveMetadata]
    layers: Sequence[LayerArchiveMetadata] = field(default_factory=list)


class AWS:
    @staticmethod
    def get_runtime_library_path(runtime: str) -> Path:
        python_pattern = re.compile(r'^python\d+\.\d+$')
        if python_pattern.match(runtime):
            return Path('python')
        raise NotImplementedError(f'Unsupported runtime: {runtime}')

    @classmethod
    def get_common_runtime_library_path(cls, runtimes: Sequence[str]) -> Path:
        distinct_paths = {cls.get_runtime_library_path(runtime) for runtime in runtimes}
        if len(distinct_paths) > 1:
            root_paths = ', '.join(str(path) for path in distinct_paths)
            raise ValueError(f'Runtimes map to multiple root paths: {root_paths}')
        return distinct_paths.pop() if distinct_paths else Path()


def get_package_archive_metadata(package: Package, install_path: Path) -> PackageArchiveMetadata:
    def _log(header: str, mappings: Sequence[ArchiveFileMapping]):
        with StringIO() as message:
            message.write(header)
            for mapping in sorted(mappings, key=lambda item: item.archive_file_name):
                message.write(f'  {mapping.archive_file_name}: {mapping.source_file_name}\n')
            _logger.debug(message.getvalue())

    def map_extra(extra_path: Path) -> Optional[ArchiveMapResult]:
        if not extra_path or not extra_path.exists():
            return None
        if extra_path.is_dir():
            return map_archive(iter_file_names(extra_path), extra_path, Path('/'))
        elif extra_path.is_file():
            return map_archive([extra_path], extra_path, Path('/'))
        return None

    function_metadata: Optional[FunctionArchiveMetadata] = None
    layers_metadata: List[LayerArchiveMetadata] = []

    function = package.function
    if function:
        extra_contents = filter(
            None, (map_extra(extra_path) for extra_path in function.extra_paths)
        )
        function_map_all = package.unmapped_file_behavior == UnmappedFileBehavior.map_to_function
        function_content = map_archive(
            iter_file_names(install_path),
            install_path,
            Path('/'),
            include_patterns=function.includes if not function_map_all else [],
            exclude_patterns=function.excludes if not function_map_all else [],
        )
        function_mappings = list(
            itertools.chain(
                function_content.mappings,
                *(extra_content.mappings for extra_content in extra_contents)
            )
        )
        function_source_file_names = [mapping.source_file_name for mapping in function_mappings]
        function_metadata = FunctionArchiveMetadata(
            function=function,
            archive=ArchiveDescriptor(function_mappings, get_digest(function_source_file_names))
        )

    layer_file_names: Sequence[Path] = []
    if function:
        if function_content.unmapped_files:
            if package.unmapped_file_behavior == UnmappedFileBehavior.map_to_layer:
                layer_file_names = function_content.unmapped_files
            elif package.unmapped_file_behavior == UnmappedFileBehavior.error:
                raise RuntimeError(f'Package has unmapped files: {function_content.unmapped_files}')
            elif package.unmapped_file_behavior == UnmappedFileBehavior.ignore:
                _logger.debug('Ignoring unmapped files: %s', function_content.unmapped_files)
    else:
        layer_file_names = list(iter_file_names(install_path))
    package_layers: List[PackageLayer] = [
        layer for layer in package.layers if isinstance(layer, PackageLayer)
    ]
    for layer in package_layers:
        # TODO: Document how all compatible runtimes must resolve to one common library path.
        layer_root_path = AWS.get_common_runtime_library_path(layer.compatible_runtimes)
        layer_content = map_archive(
            layer_file_names,
            install_path,
            layer_root_path,
            include_patterns=layer.includes,
            exclude_patterns=layer.excludes,
        )
        layer_file_names = [mapping.source_file_name for mapping in layer_content.mappings]
        layer_metadata = LayerArchiveMetadata(
            layer=layer,
            archive=ArchiveDescriptor(layer_content.mappings, get_digest(layer_file_names))
        )
        layers_metadata.append(layer_metadata)

    if _logger.isEnabledFor(logging.DEBUG):
        if function_metadata:
            _log(
                f'Function file mappings: {function_metadata.function.name}\n',
                function_metadata.archive.file_mappings
            )
        for metadata in layers_metadata:
            _log(f'Layer file mappings: {metadata.layer.name}:\n', metadata.archive.file_mappings)

    if function_metadata:
        _logger.info(
            'Function digest: %s: %s', function_metadata.function.name,
            function_metadata.archive.digest
        )
    for metadata in layers_metadata:
        _logger.info('Layer digest: %s: %s', metadata.layer.name, metadata.archive.digest)

    return PackageArchiveMetadata(function_metadata, layers_metadata)
