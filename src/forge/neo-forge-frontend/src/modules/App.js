// @flow
/* eslint-disable react/no-multi-comp */

import React, { Component } from "react";
import { Route, Switch } from "react-router-dom";
import {
  LayoutManagerWithViewController,
  NavigationProvider,
  ViewController,
  withNavigationViewController
} from "@atlaskit/navigation-next";
import "@atlaskit/css-reset";

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
        <h1>Issues and filters</h1>
      </div>
    );
  }
}
const IssuesAndFiltersRoute = withNavigationViewController(
  IssuesAndFiltersRouteBase
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
