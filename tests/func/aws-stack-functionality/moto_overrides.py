import json
import re

from boto.cloudformation.stack import Output
from moto.cloudformation.parsing import clean_json
from moto.cloudformation.responses import CREATE_CHANGE_SET_RESPONSE_TEMPLATE
from moto.core.exceptions import RESTError
from moto.elbv2.exceptions import DuplicateTargetGroupName, InvalidConditionValueError, InvalidTargetGroupNameError
from moto.elbv2.models import FakeTargetGroup
from moto.elbv2.utils import make_arn_for_target_group


# cloudformation parsing.py
def parse_condition(condition, resources_map, condition_map):
    if isinstance(condition, bool):
        return condition

    condition_operator = list(condition.keys())[0]

    condition_values = []
    for value in list(condition.values())[0]:
        # Check if we are referencing another Condition
        if isinstance(value, dict) and 'Condition' in value:
            condition_values.append(condition_map[value['Condition']])
        else:
            condition_values.append(clean_json(value, resources_map))

    if condition_operator == "Fn::Equals":
        return condition_values[0] == condition_values[1]
    elif condition_operator == "Fn::Not":
        return not parse_condition(condition_values[0], resources_map, condition_map)
    elif condition_operator == "Fn::And":
        return all([parse_condition(condition_value, resources_map, condition_map) for condition_value in condition_values])
    elif condition_operator == "Fn::Or":
        return any([parse_condition(condition_value, resources_map, condition_map) for condition_value in condition_values])


# cloudformation responses.py
# adds support for "use_previous_value"
def create_change_set(self):
    stack_name = self._get_param("StackName")
    change_set_name = self._get_param("ChangeSetName")
    stack_body = self._get_param("TemplateBody")
    stack = self.cloudformation_backend.get_stack(stack_name)
    if self._get_param('UsePreviousTemplate') == "true":
        stack_body = stack.template
    template_url = self._get_param("TemplateURL")
    role_arn = self._get_param("RoleARN")
    update_or_create = self._get_param("ChangeSetType", "CREATE")
    parameters_list = self._get_list_prefix("Parameters.member")
    tags = dict((item["key"], item["value"]) for item in self._get_list_prefix("Tags.member"))
    parameters = {param["parameter_key"]: param["parameter_value"] for param in parameters_list if "parameter_value" in param}
    previous = dict([(param["parameter_key"], stack.parameters[param["parameter_key"]]) for param in parameters_list if "use_previous_value" in param])
    parameters.update(previous)
    if template_url:
        stack_body = self._get_stack_from_s3_url(template_url)
    stack_notification_arns = self._get_multi_param("NotificationARNs.member")
    change_set_id, stack_id = self.cloudformation_backend.create_change_set(
        stack_name=stack_name,
        change_set_name=change_set_name,
        template=stack_body,
        parameters=parameters,
        region_name=self.region,
        notification_arns=stack_notification_arns,
        tags=tags,
        role_arn=role_arn,
        change_set_type=update_or_create,
    )
    if self.request_json:
        return json.dumps({"CreateChangeSetResponse": {"CreateChangeSetResult": {"Id": change_set_id, "StackId": stack_id}}})
    else:
        template = self.response_template(CREATE_CHANGE_SET_RESPONSE_TEMPLATE)
        return template.render(stack_id=stack_id, change_set_id=change_set_id)


# elbv2 models.py
def create_target_group(self, name, **kwargs):
    if len(name) > 32:
        raise InvalidTargetGroupNameError("Target group name '%s' cannot be longer than '32' characters" % name)
    if not re.match('^[a-zA-Z0-9\-]+$', name):
        raise InvalidTargetGroupNameError("Target group name '%s' can only contain characters that are alphanumeric characters or hyphens(-)" % name)

    # undocumented validation
    if not re.match('(?!.*--)(?!^-)(?!.*-$)^[A-Za-z0-9-]+$', name):
        raise InvalidTargetGroupNameError(
            "1 validation error detected: Value '%s' at 'targetGroup.targetGroupArn.targetGroupName' failed to satisfy constraint: Member must satisfy regular expression pattern: (?!.*--)(?!^-)(?!.*-$)^[A-Za-z0-9-]+$"
            % name
        )

    if name.startswith('-') or name.endswith('-'):
        raise InvalidTargetGroupNameError("Target group name '%s' cannot begin or end with '-'" % name)
    for target_group in self.target_groups.values():
        if target_group.name == name:
            raise DuplicateTargetGroupName()

    valid_protocols = ['HTTPS', 'HTTP', 'TCP']
    if kwargs.get('healthcheck_protocol') and kwargs['healthcheck_protocol'] not in valid_protocols:
        raise InvalidConditionValueError(
            "Value {} at 'healthCheckProtocol' failed to satisfy constraint: " "Member must satisfy enum value set: {}".format(kwargs['healthcheck_protocol'], valid_protocols)
        )
    if kwargs.get('protocol') and kwargs['protocol'] not in valid_protocols:
        raise InvalidConditionValueError(
            "Value {} at 'protocol' failed to satisfy constraint: " "Member must satisfy enum value set: {}".format(kwargs['protocol'], valid_protocols)
        )

    if kwargs.get('matcher') and FakeTargetGroup.HTTP_CODE_REGEX.match(str(kwargs['matcher']['HttpCode'])) is None:
        raise RESTError('InvalidParameterValue', 'HttpCode must be like 200 | 200-399 | 200,201 ...')

    arn = make_arn_for_target_group(account_id=1, name=name, region_name=self.region_name)
    target_group = FakeTargetGroup(name, arn, **kwargs)
    self.target_groups[target_group.arn] = target_group
    return target_group
