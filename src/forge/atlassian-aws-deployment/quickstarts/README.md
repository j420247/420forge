## Atlassian AWS CloudFormation Quickstart templates

This directory contains the following AWS CloudFormation Quickstart templates:

| Template Name | Purpose |
|---------------|-------------|
| `quickstart-vpc-for-atlassian-services.yaml` | This quickstart spins up an Atlassian Services VPC + bastion only
| `quickstart-for-atlassian-services.yaml` | This quickstart spins up Atlassian Services Vpc + bastion with an optional forge and backmac. From there you can use the product VPC's or the forge UI to spin up Atlassian product instances
| `quickstart-backmac-for-atlassian-services.yaml` | This quickstart spins up Backmac in a pre-existing Atlassian Service VPC only
| `quickstart-bastion-for-atlassian-services.yaml` | This quickstart spins up a ssh bastion host in a pre-existing Atlassian Service VPC only
| `quickstart-confluence-master.template.yaml` | This quickstart spins up a Confluence instance in a pre-existing Atlassian Service VPC only
| `quickstart-crowd-master.template.yaml` | This quickstart spins up a Crowd instance in a pre-existing Atlassian Service VPC only
| `quickstart-forge-for-atlassian-services.yaml` | This quickstart spins up Forge in a pre-existing Atlassian Service VPC only
| `quickstart-jira-master.template.yaml` | This quickstart spins up a Jira instance in a pre-existing Atlassian Service VPC only


**Key Terms:**

| Term | Definition |
|------|------------|
| `backmac` | [Backmac](https://community.atlassian.com/t5/Data-Center-articles/Introducing-Atlassian-CloudFormation-Backup-Machine/ba-p/881556#M25) is the backup machine toolset for automating the backup of atlassian product Cloudformation stacks and is required for stack replication and DR to alternate regions |
| `bastion` | An ec2 node with sshd and a public IP that allows you to connect to other resources inside the Atlassian Services VPC. |
| `forge` | [Forge](https://community.atlassian.com/t5/Data-Center-articles/Introducing-Atlassian-CloudFormation-Forge/ba-p/881551) is a Cloudformation automation tool, which consolidates and simplifies most of the tasks you would need to do on atlassian products in AWS in a single webUI  |

### Use

Note: You must create either `quickstart-for-atlassian-services` or `quickstart-vpc-for-atlassian-services` first as they create the network structure required by the other Quickstarts 

To use, go to [the AWS EC2 console - Key Pairs](https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#KeyPairs:sort=keyName) 

* Switch to the region in which you will deploy your quickstart(s)
* Create your AWS Key Pair.

Go to [the AWS CloudFormation console](https://console.aws.amazon.com/cloudformation/home?region=us-east-1)

* Click "Create New Stack".
* Click "Choose file" and select the Quickstart you want to deploy.
* Follow the prompts.

