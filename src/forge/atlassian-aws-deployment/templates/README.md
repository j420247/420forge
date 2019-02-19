## Atlassian AWS CloudFormation templates

This directory contains the following AWS CloudFormation templates:

| Template Name | File Server | Database | Proxy | Documentation |
|---------------|-------------|----------|-------|---------------|
| `BitbucketServer.template` | None | PostgreSQL (onboard) | Nginx (onboard) | [Documentation](https://confluence.atlassian.com/x/wZZKLg) |
| `BitbucketDataCenter.template` | EC2 as NFS | RDS PostgreSQL | ELB | - |
| `ConfluenceDataCenter.template` | EFS* | RDS PostgreSQL | ELB | - |
| `ConfluenceDataCenterClone.template` | EC2 as NFS | RDS PostgreSQL | ELB | - |
| `CrowdDataCenter.template` | EFS* | RDS PostgreSQL | ELB | - |
| `CrowdDataCenterClone.template` | EC2 as NFS | RDS PostgreSQL | ELB | - |
| `JiraDataCenter.template` | EFS* | RDS PostgreSQL | ELB | - |
| `JiraDataCenterClone.template` | EC2 as NFS | RDS PostgreSQL | ELB | - |

\* EFS is not available in all AWS regions; check Amazon's [Regional Products and Services](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) list to ensure your target region is supported.

**Key Terms:**

| Term | Definition |
|------|------------|
| `{Productname}Server` | A single-instance deployment of `{Productname}`. May still utilize additional instances in RDS or EC2 for database or NFS usage, but the core application uses a single EC2 node and requires a "Server" license. |
| `{Productname}DataCenter` | A multi-instance (clustered) deployment of `{Productname}`. Requires "Data Center" license. |
| `{Productname}{Server/DataCenter}Clone` | A variant template specifically designed for cloning an existing production stack to a new staging or disaster recovery stack. |

### Use

To use, go to [the AWS CloudFormation console](https://console.aws.amazon.com/cloudformation/home?region=us-east-1) and click "Create New Stack" and follow the prompts.

You can also validate the template from the command line with the AWS Command Line Interface (CLI) tools. See [the AWS documentation](http://docs.aws.amazon.com/cli/latest/userguide/installing.html).

Alternatively, you can use the `test<TemplateName>.sh` scripts in `/test` to:

- Create your AWS Key Pair
- Create a VPC, subnets and an Internet Gateway
- Create the CloudFormation stack for the specified template

_Note:_ the CLI and test scripts require an access token to be available in your environment.
