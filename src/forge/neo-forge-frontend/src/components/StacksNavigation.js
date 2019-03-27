import { AtlassianWordmark } from '@atlaskit/logo';
import { LinkItem } from '../components/LinkItem';

const productStacksView = {
    id: 'product/home',
    type: 'product',
    getItems: () => [
      {
        type: 'HeaderSection',
        id: 'product/home:header',
        items: [
          {
            type: 'Wordmark',
            wordmark: AtlassianWordmark,
            id: 'atlassian-wordmark',
          },
        ],
      },
      {
        type: 'MenuSection',
        id: 'product/issues:stacks-menu',
        items: [
          { type: 'SectionHeading', id: 'stacks-heading', text: 'Stacks' },
          {
            type: 'InlineComponent',
            component: LinkItem,
            id: 'stack-1',
            text: 'Stack 1',
            to: '/stack-1'
          },
        ],
      },
    ],
  };

  export default productStacksView;