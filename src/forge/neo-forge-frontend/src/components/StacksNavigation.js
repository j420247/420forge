import { AtlassianWordmark } from "@atlaskit/logo";

const productStacksView = {
  id: "forge/home",
  type: "product",
  getItems: () => [
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
          id: "stacks-heading",
          text: "Stacks"
        },
        {
          type: "Item",
          id: "stack-1",
          text: "Stack 1",
          goTo: "forge/actions"
        }
      ]
    }
  ]
};

export default productStacksView;
