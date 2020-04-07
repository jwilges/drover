# basic_lambda
A basic Lambda that returns its version; this Lambda intentionally has no external dependencies.

## Prerequisites
Before running this example, ensure:
- to install the `drover` and `invoke` Python packages (e.g. via `pip`),
- `~/.aws/credentials` contains a feasible profile named `examples`,
- a Lambda named `basic-lambda` exists in `us-east-1`, and
- the `basic-lambda` handler is set to `basic_lambda.lambda_handler`.

## Sample deploy
Assuming the AWS profile `examples` has sufficient privileges, the command:

`AWS_PROFILE=examples invoke deploy`

should deploy the `basic_lambda` example:

```
+ python -m venv --clear /tmp/venv
+ /tmp/venv/bin/pip install wheel
Collecting wheel
  Downloading https://files.pythonhosted.org/packages/8c/23/848298cccf8e40f5bbb59009b32848a4c38f4e7f3364297ab3c3e2e2cd14/wheel-0.34.2-py2.py3-none-any.whl
Installing collected packages: wheel
Successfully installed wheel-0.34.2
+ /tmp/venv/bin/pip install --target /build -r requirements.txt .
Processing /var/task
Building wheels for collected packages: basic-lambda
  Building wheel for basic-lambda (setup.py): started
  Building wheel for basic-lambda (setup.py): finished with status 'done'
  Created wheel for basic-lambda: filename=basic_lambda-0.0.1-cp38-none-any.whl size=1596 sha256=ed817c51edb7bb61a21bb96bd0f81674248af6815ae4728512668d6bfad0bc87
  Stored in directory: /tmp/pip-ephem-wheel-cache-12e6237i/wheels/87/fe/86/32f1e59dd6105e277388fa8d76ea702b40d0d4e6f71aad7438
Successfully built basic-lambda
Installing collected packages: basic-lambda
Successfully installed basic-lambda-0.0.1
Requirements digest: None
Function digest: 0b37cf78f6ad4c137fb1f77751c0c0e759dd2d6c515937d33fae435b9e091f72
Skipping requirements upload
Uploading function archive...
Failed to upload function archive to bucket; falling back to direct file upload.
Updating function resource...
Updated function "basic-lambda" resource; size: 1.78 KiB; ARN: arn:aws:lambda:us-east-1:977874552542:function:basic-lambda
```

## Sample synchronous request
Assuming the AWS profile `examples` has sufficient privileges, the command:

`AWS_PROFILE=examples invoke request`

should synchronously invoke the deployed Lambda and return its response:

```
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}
Lambda Output:
b'"0.0.1"'
```