import React, { Component } from 'react';
import Page, { Grid, GridColoumn } from '@atlaskit/page';
import PageHeader from '@atlaskit/page-header';
import Form, { Field } from '@atlaskit/form';
import PropTypes from 'prop-types';

export default class ClonePage extends Component {

  static propTypes = {
    currentStack: PropTypes.string
  };

  componentDidMount() {
    
  }

  render() {
    const { currentStack } = this.props;
    return (
      <Page>
        <PageHeader>Clone an Atlassian Product</PageHeader>
        <Form onSubmit={data => console.log('form data', data)}>
          {({ formProps }) => (
            <form {...formProps}>

            </form>
          )}
        </Form>
      </Page>
    )
  }

}