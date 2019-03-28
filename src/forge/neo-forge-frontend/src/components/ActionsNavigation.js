import { AtlassianWordmark } from "@atlaskit/logo";

const stacksActionView = {
  id: "stack/actions",
  type: "container",
  getItems: () => [
    {
      type: "HeaderSection",
      id: "stack/actions:header",
      items: [
        {
          type: "Wordmark",
          wordmark: AtlassianWordmark,
          id: "atlassian-wordmark"
        },
        {
          type: "BackItem",
          id: "back-to-stacks",
          goTo: "product/home",
          text: "Back to Stacks",
          to: "/"
        }
      ]
    },
    {
      type: "MenuSection",
      nestedGroupKey: "menu",
      id: "stack/actions:menu",
      parentId: "product/home:menu",
      items: [
        {
          type: "SectionHeading",
          text: "Actions",
          id: "stack-actions-heading"
        },
        {
          type: "Item",
          text: "Clone",
          id: "clone"
        }
      ]
    }
  ]
};

export default stacksActionView;
