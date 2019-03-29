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
import { AtlassianWordmark } from "@atlaskit/logo";


import api from './api';
import ClonePage from '../pages/ClonePage';
import { ForgeGlobalNavigation } from "../components/GlobalNavigation";
import { LinkItem } from "../components/LinkItem";
import stacksActionView from "../components/ActionsNavigation";
import HomePage from "../pages/HomePage";

class DashboardsRouteBase extends Component<{
  navigationViewController: ViewController
}> {
  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.setView("forge/home");
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

  state = {
    stackNames: [],
  };

  getStacksView = () => ({
    id: "forge/home",
    type: "product",
    getItems: () => {
      let stacks = this.state.stackNames.map(
        name => ({
          type: "Item",
          id: "forge/home/stacks:" + name,
          text: name,
          goTo: "forge/actions",
        })
      );
      return (
        [
          {
            type: "HeaderSection",
            id: "forge/home:header",
            items: [
              {
                type: "Wordmark",
                wordmark: AtlassianWordmark,
                id: "atlassian-wordmark"
              }
            ]
          },
          {
            type: "MenuSection",
            id: "forge/home:stacks-menu",
            items: [
              {
                type: "SectionHeading",
                id: "forge/home:stacks-heading",
                text: "Stacks"
              },
              ...stacks
            ]
          }
        ]
      );
    }
  });

  componentDidMount() {
    const { navigationViewController } = this.props;
    navigationViewController.addView(this.getStacksView());
    navigationViewController.addView(stacksActionView);

    api.getStacks().then(result => {
      this.setState({ stackNames: result })
      this.props.navigationViewController.addView(this.getStacksView());
    });
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
