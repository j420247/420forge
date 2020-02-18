import base64
import hashlib
import hmac
import json
import time
from botocore.vendored import requests
from os import getenv


""" 
This is an example lambda to consume Forge's SNS messages and use them to create Ops Notes in LogicMonitor
It can be modified to send events to other services.
"""


def lambda_handler(event, context):
    message = json.loads(event['Records'][0]['Sns']['Message'])
    stack_name = message['stack']
    note = f"{message['msg']} by {message['user']}"
    resource_group = get_lm_resource_group(stack_name)
    if resource_group is None:
        print(f'Resource group for stack {stack_name} not found')
        return 'Failed'
    status_code = logicmonitor_register_opsnote(resource_group, note, message["timestamp"], message["tags"])
    return status_code


def logicmonitor_register_opsnote(logicmonitor_resource_group, note, timestamp, tags):
    data = f'{{"note":"{note}","happenOnInSec":"{timestamp}","scopes":[{{"type":"deviceGroup","groupId":{logicmonitor_resource_group}}}],"tags":[{tags}]}}'
    print(data)
    resource_path = '/setting/opsnotes'
    query_params = ''
    headers = logicmonitor_generate_headers(data, resource_path, 'POST')
    response = requests.post(logicmonitor_generate_url(resource_path, query_params), data=data, headers=headers,)
    print('Response Status:', response.status_code)
    return response.status_code


def logicmonitor_generate_headers(data, resource_path, method):
    # You will need to add the following environment variables in the lambda config
    access_id = getenv('LM_API_ACCESSID')
    access_key = getenv('LM_API_ACCESSKEY')
    epoch = str(int(time.time() * 1000))
    request_vars = method + epoch + data + resource_path
    # Construct signature
    hmac_var = hmac.new(access_key.encode(), msg=request_vars.encode(), digestmod=hashlib.sha256).hexdigest()
    signature = base64.b64encode(hmac_var.encode())
    # Construct headers
    auth = f'LMv1 {access_id}:{signature.decode()}:{epoch}'
    headers = {'Content-Type': 'application/json', 'Authorization': auth}
    return headers


def logicmonitor_generate_url(resource_path, query_params):
    url = f'https://atlassian.logicmonitor.com/santaba/rest{resource_path}{query_params}'
    return url


def get_lm_resource_group(stack_name):
    # Add your stack names and corresponding resource group IDs here
    stacks = [
        {"site": "my_device_group", "logicmonitor_resource_group": "123",},
    ]
    for stack in stacks:
        if stack['site'] == stack_name:
            return stack['logicmonitor_resource_group']
