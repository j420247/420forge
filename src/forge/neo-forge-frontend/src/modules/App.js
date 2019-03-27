// @flow
/* eslint-disable react/no-multi-comp */

import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import HomePage from '../pages/HomePage';
import { AtlassianWordmark } from '@atlaskit/logo';
import {
  LayoutManagerWithViewController,
  NavigationProvider,
  ViewController,
  withNavigationViewController,
} from '@atlaskit/navigation-next';
import { ForgeGlobalNavigation } from '../components/GlobalNavigation';
import { LinkItem } from '../components/LinkItem';
import productHomeView from '../components/StacksNavigation';
import '@atlaskit/css-reset';

const productIssuesView = {
  id: 'product/issues',
  type: 'product',
  getItems: () => [
    {
      type: 'HeaderSection',
      id: 'product/issues:header',
      items: [
        {
          type: 'Wordmark',
          wordmark: AtlassianWordmark,
          id: 'atlassian-wordmark',
        },
        {
          type: 'BackItem',
          id: 'back-item',
          goTo: 'product/home',
          text: 'Back to Stacks',
        },
      ],
    },
    {
      type: 'MenuSection',
      nestedGroupKey: 'menu',
      id: 'product/issues:menu',
      parentId: 'product/home:stacks',
      alwaysShowScrollHint: true,
      items: [
        {
          type: 'SectionHeading',
          text: 'Issues and filters',
          id: 'issues-and-filters-heading',
        },
        {
          // Example: using LinkItem as a custom component type
          type: 'LinkItem',
          id: 'search-issues',
          text: 'Search issues',
          to: '/issues',
        },
        { type: 'GroupHeading', id: 'other-heading', text: 'Other' },
        { type: 'Item', text: 'My open issues', id: 'my-open-issues' },
        { type: 'Item', text: 'Reported by me', id: 'reported-by-me' },
        { type: 'Item', text: 'All issues', id: 'all-issues' },
        { type: 'Item', text: 'Open issues', id: 'open-issues' },
        { type: 'Item', text: 'Done issues', id: 'done-issues' },
        { type: 'Item', text: 'Viewed recently', id: 'viewed-recently' },
        { type: 'Item', text: 'Created recently', id: 'created-recently' },
        { type: 'Item', text: 'Resolved recently', id: 'resolved-recently' },
        { type: 'Item', text: 'Updated recently', id: 'updated-recently' },
        { type: 'Separator', id: 'separator' },
        { type: 'Item', text: 'View all filters', id: 'view-all-filters' },
      ],
    },
  ],
};

class DashboardsRouteBase extends Component<{
  navigationViewController: ViewController,
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(productHomeView.id);
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
    navigationViewController.setView(productIssuesView.id);
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
    navigationViewController.addView(productHomeView);
    navigationViewController.addView(productIssuesView);
  }

  render() {
    return (
      <LayoutManagerWithViewController
        customComponents={{ LinkItem }}
        globalNavigation={ForgeGlobalNavigation}
      >
        <Switch>
          <Route path="/issues" component={IssuesAndFiltersRoute} />
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