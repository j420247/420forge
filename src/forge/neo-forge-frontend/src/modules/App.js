// @flow
/* eslint-disable react/no-multi-comp */

import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import HomePage from '../pages/HomePage';
import {
  LayoutManagerWithViewController,
  NavigationProvider,
  ViewController,
  withNavigationViewController,
} from '@atlaskit/navigation-next';
import { ForgeGlobalNavigation } from '../components/GlobalNavigation';
import { LinkItem } from '../components/LinkItem';
import productStacksView from '../components/StacksNavigation';
import '@atlaskit/css-reset'
import { AtlassianWordmark } from '@atlaskit/logo';


const stacksActionView = {
  id: 'stack/actions',
  type: 'container',
  getItems: () => [
    {
      type: 'HeaderSection',
      id: 'stack/actions:header',
      items: [
        {
          type: 'Wordmark',
          wordmark: AtlassianWordmark,
          id: 'atlassian-wordmark',
        },
        {
          type: 'BackItem',
          id: 'back-to-stacks',
          goTo: 'product/home',
          text: 'Back to Stacks',
          to: '/'
        },
      ],
    },
    {
      type: 'MenuSection',
      nestedGroupKey: 'menu',
      id: 'stack/actions:menu',
      parentId: 'product/home:menu',
      items: [
        {
          type: 'SectionHeading',
          text: 'Actions',
          id: 'stack-actions-heading',
        },
        {
          type: 'Item',
          text: 'Clone',
          id: 'clone',
        },
      ],
    },
  ],
};

class DashboardsRouteBase extends Component<{
  navigationViewController: ViewController,
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(productStacksView.id);
  }

  render() {
    return (
      <HomePage />
    );
  }
}
const DashboardsRoute = withNavigationViewController(DashboardsRouteBase);

class IssuesAndFiltersRouteBase extends Component<{
  navigationViewController: ViewController,
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(stacksActionView.id);
  }

  render() {
    return (
      <div css={{ padding: 30 }}>
        <h1>Issues and filters</h1>
      </div>
    );
  }
}
const IssuesAndFiltersRoute = withNavigationViewController(
  IssuesAndFiltersRouteBase,
);

class App extends Component<{
  navigationViewController: ViewController,
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.addView(productStacksView);
    navigationViewController.addView(stacksActionView);
  }

  render() {
    return (
      <LayoutManagerWithViewController
        customComponents={{ LinkItem }}
        globalNavigation={ForgeGlobalNavigation}
      >
        <Switch>
          <Route path="/stack-1" component={IssuesAndFiltersRoute} />
          <Route path="/" component={DashboardsRoute} />
        </Switch>
      </LayoutManagerWithViewController>
    );
  }
}
const AppWithNavigationViewController = withNavigationViewController(App);

export default () => (
    <NavigationProvider>
      <AppWithNavigationViewController />
    </NavigationProvider>
);