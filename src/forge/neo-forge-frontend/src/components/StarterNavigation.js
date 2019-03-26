import React, { Fragment } from 'react';
import { 
  ContainerHeader,
  GroupHeading,
  HeaderSection,
  Item,
  ItemAvatar,
  LayoutManager,
  MenuSection,
  NavigationProvider,
  Separator,
  } from '@atlaskit/navigation-next';
import GlobalNavigation from '@atlaskit/global-navigation';
import { AtlassianIcon } from '@atlaskit/logo';
import ShortcutIcon from '@atlaskit/icon/glyph/shortcut';


const MyGlobalNavigation = () => (
  <GlobalNavigation
    productIcon={() => <AtlassianIcon size="medium" />}
    onProductClick={() => {}}
  />
);

const MyContainerNavigation = () => (
  <Fragment>
    <HeaderSection>
      {({ css }) => (
        <div css={{ ...css, paddingBottom: 20 }}>
          <ContainerHeader
            before={itemState => (
              <ItemAvatar
                itemState={itemState}
                appearance="square"
                size="large"
              />
            )}
            text="Container name"
            subText="Container description"
          />
        </div>
      )}
    </HeaderSection>
    <MenuSection>
      {({ className }) => (
        <div className={className}>
          <Item text="Clone" isSelected />
        </div>
      )}
    </MenuSection>
  </Fragment>
);

export default class StarterNavigation extends React.Component {
  render() {
    return (
      <NavigationProvider>
        <LayoutManager
          globalNavigation={MyGlobalNavigation}
          productNavigation={() => null}
          containerNavigation={MyContainerNavigation}
        >
          <div css={{ padding: '32px 40px' }}>Page content goes here.</div>
        </LayoutManager>
      </NavigationProvider>
    );
  }
}
