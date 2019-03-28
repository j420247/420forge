// @flow
/* eslint-disable react/no-multi-comp */

import React, { Component } from "react";
import { Route, Switch } from "react-router-dom";
import {
  LayoutManagerWithViewController,
  NavigationProvider,
  ViewController,
  withNavigationViewController,
} from '@atlaskit/navigation-next';
import '@atlaskit/css-reset';

import ClonePage from '../pages/ClonePage';

import { ForgeGlobalNavigation } from "../components/GlobalNavigation";
import { LinkItem } from "../components/LinkItem";
import productStacksView from "../components/StacksNavigation";
import stacksActionView from "../components/ActionsNavigation";
import HomePage from "../pages/HomePage";

class DashboardsRouteBase extends Component<{
  navigationViewController: ViewController
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(productStacksView.id);
  }

  render() {
    return <HomePage />;
  }
}
const DashboardsRoute = withNavigationViewController(DashboardsRouteBase);

class IssuesAndFiltersRouteBase extends Component<{
  navigationViewController: ViewController
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(stacksActionView.id);
  }

  render() {
    return (
      <div css={{ padding: 30 }}>
        Pick an action
      </div>
    );
  }
}
const IssuesAndFiltersRoute = withNavigationViewController(
  IssuesAndFiltersRouteBase
);

class CloneStack extends Component<{
  navigationViewController: ViewController
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView(stacksActionView.id);
  }

  render() {
    return (
      <div css={{ padding: 30 }}>
        <ClonePage />
      </div>
    );
  }
}
const CloneStackRoute = withNavigationViewController(
  CloneStack
);

class App extends Component<{
  navigationViewController: ViewController
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
          <Route path="/actions/clone" component={CloneStackRoute} />
          <Route path="/actions" component={IssuesAndFiltersRoute} />
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
