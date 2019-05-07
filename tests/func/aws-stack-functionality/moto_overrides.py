import re

from boto.cloudformation.stack import Output
from moto.cloudformation.parsing import clean_json
from moto.core.exceptions import RESTError
from moto.elbv2.exceptions import InvalidTargetGroupNameError, DuplicateTargetGroupName, InvalidConditionValueError
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
