# atl-cfn-forge

Atlassian Cloudformation Forge is a tool which enables the creation and management of Cloudformation stacks of Atlassian products by users without "physical" access to the underlying AWS services.

This README outlines how to run Forge locally for testing and development. For more complete documentation, including instructions for deploying Forge to your AWS account, see [link here](https://some.url.here).

## Prerequisites

### Python

Forge requires Python 3.

### AWS

Your local environment must be configured with AWS environment variables, and the access keys or IAM role you're using must have the permissions outlined in _filenamehere.json_. Generally, you'll need "administrator" access; either the AWS-managed "AdministratorAccess" policy or the effective "Allow *" for the following services:

* EC2
* ECS
* ElasticLoadBalancing
* IAM
* CloudWatch
* Route53
* S3

### Git submodule

Forge relies on grabbing your CloudFormation templates from a git repository included as a submodule of atl-cfn-forge. If you're using the templates found in [atlassian-aws-deployment](https://bitbucket.org/atlassian/atlassian-aws-deployment), no extra config is necessary.

If you prefer to substitute your own repository of CloudFormation templates, you'll need to:

1. Clone this repository
2. Replace the git submodule
3. Build your own version of the Docker image and push it somewhere
4. Provide the URL and/or image name for your custom Docker repo to the Forge CFN template

### SAML

To test SAML auth locally you will need to install libxml2 and xmlsec1 on your OS; when SAML auth is enabled, the app will not load if these packages/libararies are missing.

Debian:
`apt-get install libxml2 libxmlsec1`

Mac OS:
`brew install libxml2 libxmlsec1`

Additionally, you must set the `ATL_FORGE_SAML_METADATA_URL` environment variable, pass the `--saml` arg to _acforge.py_, and configure permissions by group in config.yml.

## Run

To start the app locally for development do the following in a python3 enviroment: 

```
git submodule update --init --recursive
pip3 install -r requirements.txt
python3 acforge.py
```

### Command-line args

* `--saml` specifies the use of SAML auth (see "SAML" in Prerequisites above)
* `--dev` runs the Flask app in debug mode for local development

### Config file

Forge uses a config file (config.yml) for configuring which AWS regions are available for stack creation/management, and for defining SAML permissions by group. A deployed version of Forge will pull this config from an S3 bucket, but you can override this by creating a local file (rename config_sample.yml to config.yml).

### Environment variables

| `ATL_FORGE_ANALYTICS_UA` | The Google Analytics UA number for collecting analytics on Forge usage in your org |
| `ATL_FORGE_FLASK_SECRET` | Secret passed to Flask app initialization |
| `ATL_FORGE_PORT` | Override the port that Forge runs on; defaults to 8000 |
| `ATL_FORGE_S3_CONFIG` | The name of an S3 bucket used for reading configuration files |
| `ATL_FORGE_S3_DIAGNOSTICS` | The name of an S3 bucket used for CloudFormation stack diagnostic information |
| `ATL_FORGE_S3_STACKLOGS` | The name of an S3 bucket used for log storage |
| `ATL_FORGE_S3_TEMPLATES` | The name of an S3 bucket used for the uploading and storage of CloudFormation templates |
| `ATL_FORGE_SAML_METADATA_URL` | Metadata URL for SAML auth |

*WARNING:* It is highly-recommended to create separate S3 buckets for local development and to pass those values via the env vars above; otherwise, the app will try to use the default naming patterns and/or will access "live" buckets on S3.
