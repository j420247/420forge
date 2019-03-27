import React from 'react'
import GlobalNavigation from '@atlaskit/global-navigation';
import { AtlassianIcon } from '@atlaskit/logo';

export const ForgeGlobalNavigation = () => (
    <GlobalNavigation
      productIcon={() => <AtlassianIcon size="medium" />}
      onProductClick={() => {}}
    />
);