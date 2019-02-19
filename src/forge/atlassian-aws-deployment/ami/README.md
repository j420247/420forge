# Atlassian AMIs

This repository contains scripts and templates for building the Atlassian Amazon Machine
Images (AMIs) for use in Amazon Web Services (AWS).

## Prerequisites to building AMIs

- AWS Account with permission to launch EC2 instances and create IAM roles
- VPC + Subnet

Do one of the following:
* go to [AWS Console](https://aws.amazon.com/console/) and log in
* use the [AWS CLI](https://aws.amazon.com/cli/)


## Building AMIs

Building requires the [Packer](http://packer.io) tool, [jq](https://github.com/stedolan/jq) and [AWS CLI](https://aws.amazon.com/cli/) as well as Python and Perl.

To build AMIs in a VPC in the Sydney region, copy to all other regions,
and update the CloudFormation templates with the new AMI IDs:
```
./bin/build-ami.sh -p Bitbucket -r ap-southeast-2 -v <your_vpc_id> -s <your_subnet_id> -c -u
./bin/build-ami.sh -p JIRA      -r ap-southeast-2 -v <your_vpc_id> -s <your_subnet_id> -c -u
```

For more information, run [`./bin/build-ami.sh`](bin/build-ami.sh); usage information will be printed to stdout.

## Launching an AMI

```
./bin/run-bitbucket.sh -r ap-southeast-2 -v <your_vpc_id> -a <REGION_SPECIFIC_AMI_ID> -k <SECURITY_GROUP_ID> -s <SSH_KEY_NAME>
```

For more information, run [`./bin/run-ami.sh`](bin/run-ami.sh); usage information will be printed to stdout.
