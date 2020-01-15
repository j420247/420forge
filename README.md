# atl-cfn-forge

Atlassian CloudFormation Forge is a tool which enables the creation and management of CloudFormation stacks of Atlassian products by users without physical access to the underlying AWS services.

We (the IT Operations team at Atlassian) built this tool internally to unlock product teams to allow them to manage their own instances of Confluence, Jira, and Crowd without having access to AWS itself (which is managed by our team).

This README outlines how to deploy Forge to AWS and how to run locally for testing and development. For an overview of Forge itself, including a list of actions possible through Forge, see [the public announcement](https://community.atlassian.com/t5/Data-Center-articles/Introducing-Atlassian-CloudFormation-Forge/ba-p/881551).


**NOTE**:

Forge is an unsupported application developed by Atlassian for creation and management of CloudFormation stacks for our products.  Atlassian takes no responsibility for your use of Forge. The apps are often developed in conjunction with Atlassian hack-a-thons and ShipIt days and are provided to you completely “as-is”, with all bugs and errors, and are not supported by Atlassian. Unless licensed otherwise by Atlassian, Forge is subject to Section 14 of the Cloud Terms of Service – https://www.atlassian.com/legal/cloud-terms-of-service – or Section 8 of the Software License Agreement – https://www.atlassian.com/legal/software-license-agreement, as applicable, and are "No-Charge Products" as defined therein.

## Deploying to AWS

We've provided a CloudFormation template for deploying Forge to your AWS account. To deploy Forge using the template, you'll either need to create a dedicated IAM role for Forge, or just make sure the user deploying the template has an appropriate level of permissions (e.g., the "AdministratorAccess" managed policy). The template will spin up an instance of Forge via an EC2 node in a VPC of your choosing, configured via the parameters below.

### Allowing Forge access to your AWS resources

#### IAM Policy

The CloudFormation template for Forge includes an IAM profile and role that will allow Forge access to the AWS actions it needs to function. This includes everything from creating, editing, and deleting CloudFormation stacks to controlling auto-scaling for deployed EC2 nodes.

#### Status information from application nodes

Once Forge is deployed, you'll need to modify the Security Group Ingress rules for any stack that you want Forge to be able to access for things like service status checks. To do this, configure a new Security Group Ingress rule that allows traffic on whichever port you have configured for Tomcat (typically 8080) and restrict it to the IP address assigned to your Forge node.

### CloudFormation Parameters

A quick overview of the parameters for Forge's CloudFormation template. We provide sensible defaults where appropriate.

* **Analytics**  
  A boolean value that determines whether or not you allow analytics on usage data to be sent back to Atlassian via Google Analytics.

* **CidrBlock**  
  The CIDR IP range that is permitted to access Forge.

* **FlaskSecretKey**  
  The secret key passed to Flask to enable sessions ([more info][1])

* **HostedZone**  
  The domain name of the Route53 Hosted Zone in which to create CNAME records

* **InternetAccessible**  
  Whether or not the Elastic Load Balancer associated with Forge is configured to be publicly-accessible

* **KeyPairName**  
  The name of an existing EC2 KeyPair to enable SSH access to the instance

* **NodeInstanceType**  
  The instance type for Forge's EC2 node(s)

* **NodeVolumeSize**  
  The size of the EBS volume for Forge's EC2 node(s)

* **Nodes**  
  The number of Forge nodes to deploy. Note that currently, Forge does not support auto-scaling or running on multiple nodes simultaneously; this is primarily for facilitating easy node replacement (spin down to 0 and then back up to 1).

* **Regions**  
  A list of regions that Forge should allow access to, defined in a comma-delimited list in the format `aws_region: region_name`, where aws_region is an AWS region (e.g. `us-east-1`) and region_name is a display value (e.g. `US East 1` or `Staging`, etc.). The first listed region will be the default.

* **SamlMetadataUrl**  
  The metadata URL for your SAML auth provider. If you don't provide a metadata URL, SAML will not be enabled.

* **Subnet**  
  The subnet in your VPC that Forge will be deployed to.

* **VPC**  
  The VPC that Forge will be deployed to.

## Running locally

### Prerequisites

#### Python

Forge requires Python 3.

#### AWS

Your local environment must be configured with AWS environment variables, and the access keys or IAM role you're using must have enough permissions to deploy the CloudFormation stack. Generally, you'll need administrator level of access; either the AWS managed "AdministratorAccess" policy or the effective "Allow *" for at least the following services:

* EC2
* ECS
* ElasticLoadBalancing
* IAM
* CloudWatch (and Logs)
* Route53
* S3
* SSM

#### Git submodule

Forge relies on grabbing CloudFormation templates from a git repository included as a submodule of atl-cfn-forge. If you're using the templates found in [atlassian-aws-deployment](https://bitbucket.org/atlassian/atlassian-aws-deployment), no extra config is necessary; just run the following to initialize the repo:

```
git submodule update --init --recursive
```

#### SAML

To test SAML auth locally you will need to install libxml2 and xmlsec1 on your OS; when SAML auth is enabled, the app will not load if these packages/libraries are missing.

Debian:
`apt-get install libxml2 libxmlsec1`

Mac OS:
`brew install libxml2 libxmlsec1`

You'll also need to have already deployed the CloudFormation template or configured the metadata protocol and URL for your SAML provider as keys in AWS Systems Manager Parameter Store (`atl_forge_saml_metadata_protocol` and `atl_forge_saml_metadata_url`, respectively).

For information about enabling SAML auth, see [Forge: enabling SAML](https://confluence.atlassian.com/kb/forge-enabling-saml-957138587.html).

### Run

To start the app locally for development do the following in a python3 environment:

```
pip3 install pipenv
pipenv install
pipenv run forge-gunicorn
```

#### Environment Variables

* `NO_SAML=1` disables SAML auth (for local development)
* `REGION=us-east-1` defines the AWS region that Forge is operating in

#### Configuration

Forge uses 2 config files (_forge.properties_ and _permissions.json_) and 3 values in AWS Systems Manager Parameter Store.

##### _forge.properties_

Used for configuring which AWS regions are available for stack creation/management, analytics collection, and S3 bucket definitions. A version of Forge deployed with the provided CloudFormation template will create this file on the EC2 node, but to run locally you'll need to create one on your local system.

**WARNING:** It is highly-recommended to create separate S3 buckets for local development and to pass those values via your local _forge.properties_ file. Otherwise, the app will access "live" buckets on S3, which may be undesirable.

##### _permissions.json_

Used for configuring SAML permissions by AD group, AWS region, CloudFormation stack name, and Forge actions. A sample permissions.json is provided in the repo.

##### AWS Systems Manager Parameter Store

* **atl_forge_secret_key**  
  The secret key passed to Flask to enable sessions ([more info][1])

* **atl_forge_saml_metadata_protocol**  
  The protocol of the metadata URL for your SAML auth provider

* **atl_forge_saml_metadata_url**  
  The metadata URL for your SAML auth provider


[1]: https://bit.ly/2PRfJRk

##### pre-commit hooks
run `pre-commit install` within your dev environment to have our pre-commit checks automatically added to your local git repo.
