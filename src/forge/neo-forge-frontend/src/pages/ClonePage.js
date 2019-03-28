import React, { Component, Fragment } from 'react';
import Button from '@atlaskit/button';
import Page, { Grid, GridColoumn } from '@atlaskit/page';
import PageHeader from '@atlaskit/page-header';
import Form, { HelperMessage, Field, FormFooter } from '@atlaskit/form';
import Spinner from '@atlaskit/spinner';
import TextField from '@atlaskit/textfield';
import Select from '@atlaskit/select';
import PropTypes from 'prop-types';

import api from '../modules/api';

export default class ClonePage extends Component {

  static propTypes = {
    currentStack: PropTypes.string
  };

  state = {
    submitting: false,
    templateLoading: false,
    templateParameters: [],
  }

  componentDidMount() {
    this.determineFormFields();
  }

  determineFormFields() {
    this.setState({ templateLoading: true });
    api.getTemplateParamsForTemplate('atlassian-aws-deployments', 'JiraDataCenterQuickstartClone.template.yaml')
    .then(resJson => this.setState({ templateParameters: resJson, templateLoading: false }));
  }

  transformFormValuesForClone(formData) {
    let payload = [];
    for (let key in formData) {
      // Value from select inputs is { label, value } tuple and needs to be extracted. Otherwise just take value.
      const value = formData[key].value !== undefined ? formData[key].value : formData[key]
      payload.push({
        "ParameterKey": key,
        // API expects strings
        "ParameterValue": `${value}`
      });
    }
    return payload;
  }

  submitClone(templateParameters) {
    this.setState({ submitting: true });
    const payload = this.transformFormValuesForClone(templateParameters);
    api.cloneStack([
      ...payload,
      {
        "ParameterKey": "TemplateName",
        "ParameterValue": "atlassian-aws-deployment: JiraDataCenterQuickstartClone.template.yaml"
      },
      {
        "ParameterKey": "ClonedFromStackName",
        "ParameterValue": "DCD-JIRA-DEV"
      }
    ]).then(resJson => {
      this.setState({ submitting: false });
      console.log(resJson);
    });
  }

  makeCfnParamater(cfnParameter) {
    return cfnParameter.AllowedValues ? this.makeCfnParameterSelectInput(cfnParameter) : this.makeCfnParameterTextInput(cfnParameter);
  }

  makeCfnParameterSelectInput(cfnParameter) {
    const selectOptions = cfnParameter.AllowedValues.map(value => ({ label: `${value}`, value: `${value}`}));
    return (<Field
      name={cfnParameter.ParameterKey}
      label={cfnParameter.ParameterLabel}
      key={cfnParameter.ParameterKey}
      defaultValue={selectOptions.find(option => option.value === `${cfnParameter.ParameterValue}`)}
    >
      {({ fieldProps, error, meta }) => (
          <Fragment>
          <Select {...fieldProps}
            options={selectOptions}
          />
        </Fragment>
      )}
    </Field>
    );
  }

  makeCfnParameterTextInput(cfnParameter) {
    return (<Field
      name={cfnParameter.ParameterKey}
      label={cfnParameter.ParameterLabel}
      key={cfnParameter.ParameterKey}
      defaultValue={cfnParameter.ParameterValue}
    >
      {({ fieldProps, error, meta }) => (
        <Fragment>
          <TextField type={cfnParameter.MaskedParameter === true ? "password" : ""} {...fieldProps}/>
          {!error && (
            <HelperMessage>
              {cfnParameter.ParameterDescription}
            </HelperMessage>
          )}
        </Fragment>
      )}
    </Field>
    );
  }

  render() {
    const { currentStack } = this.props;
    const { templateLoading, templateParameters } = this.state;
    return (
      <Page>
        <Grid>
          <PageHeader>Clone an Atlassian Product</PageHeader>
          { templateLoading ?
            <Spinner size="large" />
            :
            <Form onSubmit={data => this.submitClone(data)}>
              {({ formProps, submitting }) => (
                <form {...formProps}>
                  <Field
                    name="StackName"
                    label="Stack Name"
                    key="StackName"
                    defaultValue=""
                  >
                    {({ fieldProps, error, meta }) => (
                      <Fragment>
                        <TextField {...fieldProps}/>
                        {!error && (
                          <HelperMessage>
                            The name to give the created stack
                          </HelperMessage>
                        )}
                      </Fragment>
                    )}
                  </Field>
                  <Field
                    name="Region"
                    label="Region"
                    key="Region"
                    defaultValue="us-west-2"
                  >
                    {({ fieldProps, error, meta }) => (
                      <Fragment>
                        <TextField {...fieldProps}/>
                        {!error && (
                          <HelperMessage>
                            The AWS region to deploy the clone in (must have an existing ASI)
                          </HelperMessage>
                        )}
                      </Fragment>
                    )}
                  </Field>
                  {templateParameters.map(parameter => this.makeCfnParamater(parameter))}
                  <FormFooter>
                      <Button type="submit" appearance="primary" isLoading={submitting}>
                        Clone
                      </Button>
                  </FormFooter>
                </form>
              )}
            </Form>
          }
        </Grid>
      </Page>
    )
  }

}