import React, { Component, Fragment } from 'react';
import Page, { Grid, GridColoumn } from '@atlaskit/page';
import PageHeader from '@atlaskit/page-header';
import Form, { HelperMessage, Field } from '@atlaskit/form';
import Spinner from '@atlaskit/spinner';
import TextField from '@atlaskit/textfield';
import Select from '@atlaskit/select';
import PropTypes from 'prop-types';

import { getTemplateParamsForTemplate } from '../modules/api';

export default class ClonePage extends Component {

  static propTypes = {
    currentStack: PropTypes.string
  };

  state = {
    templateLoading: false,
    templateParameters: [],
  }

  componentDidMount() {
    this.determineFormFields();
  }

  determineFormFields() {
    this.setState({ templateLoading: true });
    getTemplateParamsForTemplate('atlassian-aws-deployments', 'JiraDataCenterQuickstartClone.template.yaml')
    .then(resJson => this.setState({ templateParameters: resJson, templateLoading: false }));
  }

  makeCfnParamater(cfnParameter) {
    return cfnParameter.AllowedValues ? this.makeCfnParameterSelectInput(cfnParameter) : this.makeCfnParameterTextInput(cfnParameter);
  }

  makeCfnParameterSelectInput(cfnParameter) {
    const selectOptions = cfnParameter.AllowedValues.map(value => ({ label: `${value}`, value: `${value}`}));
    return (<Field
      name={cfnParameter.ParameterKey}
      label={cfnParameter.ParameterKey}
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
      label={cfnParameter.ParameterKey}
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
            <Form onSubmit={data => console.log('form data', data)}>
              {({ formProps }) => (
                <form {...formProps}>
                {
                  templateParameters.map(parameter => this.makeCfnParamater(parameter))
                }
                </form>
              )}
            </Form>
          }
        </Grid>
      </Page>
    )
  }

}