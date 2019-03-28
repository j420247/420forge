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
          id: "forge/actions:back",
          goTo: "forge/home",
          text: "Back to Stacks"
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
          id: "forge/actions:heading"
        },
        {
          type: "LinkItem",
          text: "Clone",
          id: "forge/actions:clone",
          to: "/actions/clone"
        }
      ]
    }
  ]
};

export default stacksActionView;
