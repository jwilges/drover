import json
from typing import Mapping, Optional, Sequence

import boto3
import botocore
from pydantic import BaseModel, Field

from drover.aws.models import LambdaFunctionBaseResponse, SSMGetParameterResponse
from drover.models import Package
from drover.packaging import PackageArchiveMetadata, LayerArchiveMetadata


DEPLOYMENT_STATE_PARAMETER_PREFIX = '/drover'


class DeploymentStateRetrievalError(RuntimeError):
    """Error retrieving deployment state"""


class DeploymentMetadata(BaseModel):
    function_digest: Optional[str]
    layer_digests: Mapping[str, str] = Field(default_factory=dict)

    def is_function_stale(self, local_metadata: PackageArchiveMetadata) -> bool:
        """True if deployed function digest does not match local function digest"""
        local_function_digest = local_metadata.function.archive.digest if local_metadata.function else None
        return local_function_digest == self.function_digest

    def get_stale_layer_names(self, local_metadata: PackageArchiveMetadata) -> Sequence[str]:
        """Names of deployed layers with digests that do not match local layer digests"""
        stale_layer_names = []
        for local_layer_metadata in local_metadata.layers:
            local_layer_name = local_layer_metadata.layer.name
            if local_layer_metadata.archive.digest != self.layer_digests.get(local_layer_name):
                stale_layer_names.append(local_layer_name)
        return stale_layer_names


class DeploymentState(BaseModel):
    metadata: Optional[DeploymentMetadata]
    function: Optional[LambdaFunctionBaseResponse]
    # layers: Sequence[str] = Field(default_factory=list)

    def get_stale_function_attributes(self) -> Sequence[str]:
        pass


class Deployment:
    def __init__(self, aws_client_config: botocore.config.Config, package: Package, package_name: str):
        self.aws_client_config = aws_client_config
        self.package = package
        self.package_name = package_name

    def _get_lambda_function_state(self) -> Optional[LambdaFunctionBaseResponse]:
        if not self.package.function:
            return None

        function_name = self.package.function.name

        lambda_client = boto3.client('lambda', config=self.aws_client_config)
        try:
            response = lambda_client.get_function(FunctionName=function_name)
        except lambda_client.exceptions.ResourceNotFoundException:
            return None
        except botocore.exceptions.ClientError as e:
            raise DeploymentStateRetrievalError(f'Unable to retrieve Lambda function "{function_name}": {e}') from e
        else:
            return LambdaFunctionBaseResponse.from_response(response['Configuration'])

    def _get_deployment_metadata(self) -> Optional[DeploymentMetadata]:
        ssm_client = boto3.client('ssm', config=self.aws_client_config)
        try:
            response = ssm_client.get_parameter(Name=f'{DEPLOYMENT_STATE_PARAMETER_PREFIX}/{self.package_name}')
        except (ssm_client.exceptions.InvalidKeyId,
                ssm_client.exceptions.ParameterNotFound,
                ssm_client.exceptions.ParameterVersionNotFound):
            return None
        else:
            state = SSMGetParameterResponse.from_response(response)
        try:
            state_value = json.loads(state.value)
        except json.JSONDecodeError as e:
            raise DeploymentStateRetrievalError(f'Unable to parse deployment state: {e}') from e
        return DeploymentMetadata.parse_obj(state_value)

    def get_state(self) -> DeploymentState:
        return DeploymentState(
            metadata=self._get_deployment_metadata(),
            function=self._get_lambda_function_state(),
        )
