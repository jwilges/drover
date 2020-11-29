import pytest
from pydantic import ValidationError

from drover.models import Package


def test_package_requires_function_or_layers():
    with pytest.raises(ValueError) as e:
        Package(region_name='us-east-1')
    assert isinstance(e.value, ValidationError)
    errors = e.value.errors()
    assert len(errors) == 1
    assert 'layers' in errors[0]['loc']
