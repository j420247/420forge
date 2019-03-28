import { AtlassianWordmark } from "@atlaskit/logo";

const stacksActionView = {
  id: "forge/actions",
  type: "container",
  getItems: () => [
    {
      type: "HeaderSection",
      id: "forge/actions:header",
      items: [
        {
          type: "Wordmark",
          wordmark: AtlassianWordmark,
          id: "atlassian-wordmark"
        },
        {
          type: "BackItem",
          id: "back-to-stacks",
          goTo: "forge/home",
          text: "Back to Stacks",
          href: "/"
        }
      ]
    },
    {
      type: "MenuSection",
      nestedGroupKey: "menu",
      id: "forge/actions:menu",
      parentId: "forge/home:menu",
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
