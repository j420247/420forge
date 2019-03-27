import React, { Component } from 'react';
import Page, { Grid, GridColoumn } from '@atlaskit/page';
import PageHeader from '@atlaskit/page-header';
import Form, { Field } from '@atlaskit/form';
import Spinner from '@atlaskit/spinner';
import PropTypes from 'prop-types';

import { getTemplateParamsForTemplate } from '../modules/api';

export default class ClonePage extends Component {

  static propTypes = {
    currentStack: PropTypes.string
  };

  state = {
    templateLoading: false,
    templateParameters: {},
  }

  componentDidMount() {
    this.determineFormFields();
  }

  determineFormFields() {
    this.setState({ templateLoading: true });
    getTemplateParamsForTemplate('atlassian-aws-deployments', 'JiraDataCenterQuickstartClone.template.yaml')
    .then(resJson => this.setState({ templateParameters: resJson, templateLoading: false }));
  }

  render() {
    const { currentStack } = this.props;
    const { templateLoading, templateParameters } = this.state;
    return (
      <Page>
        <PageHeader>Clone an Atlassian Product</PageHeader>
        { templateLoading ?
          <Spinner size="large" />
          :
          <Form onSubmit={data => console.log('form data', data)}>
            {({ formProps }) => (
              <form {...formProps}>

              </form>
            )}
          </Form>
        }
      </Page>
    )
  }

}