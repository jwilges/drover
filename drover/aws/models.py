import json
from datetime import datetime
from enum import Enum
from typing import Union, Sequence

from pydantic import BaseModel, Field


class LambdaLayerBaseResponse(BaseModel):
    arn: str = Field(..., alias='Arn')


class LambdaFunctionBaseResponse(BaseModel):
    function_name: str = Field(..., alias='FunctionName')
    function_arn: str = Field(..., alias='FunctionArn')
    code_sha256: str = Field(..., alias='CodeSha256')
    code_size: str = Field(..., alias='CodeSize')
    description: str = Field(..., alias='Description')
    layers: Sequence[LambdaLayerBaseResponse] = Field(..., alias='Layers')
    revision_id: str = Field(..., alias='RevisionId')
    runtime: str = Field(..., alias='Runtime')
    version: str = Field(..., alias='Version')

    @classmethod
    def from_response(cls, response: Union[bytes, str]) -> 'LambdaFunctionBaseResponse':
        parameter_body = json.loads(response)
        return cls.parse_obj(parameter_body)


class SSMParameterType(str, Enum):
    string = 'String'
    string_list = 'StringList'
    secure_string = 'SecureString'


class SSMGetParameterResponse(BaseModel):
    _type: SSMParameterType = Field(alias='Type')
    name: str = Field(alias='Name')
    value: str = Field(alias='Value')
    version: int = Field(alias='Version')
    selector: str = Field(alias='Selector')
    source_result: str = Field(alias='SourceResult')
    last_modified_date: datetime = Field(alias='LastModifiedDate')
    arn: str = Field(alias='ARN')
    data_type: str = Field(alias='DataType')

    @classmethod
    def from_response(cls, response: Union[bytes, str]) -> 'SSMGetParameterResponse':
        parameter_body = json.loads(response)
        return cls.parse_obj(parameter_body)
