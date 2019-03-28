import React from "react";
import ContentWrapper from "../components/ContentWrapper";
import PageTitle from "../components/PageTitle";

const HomePage = () => (
  <ContentWrapper>
    <PageTitle>Forge</PageTitle>
    <section style={{ marginBottom: "10px" }}>
      <p>
        This is a tool to help you manage your Atlassian (server or data centre)
        application instances.
      </p>
      <p>To get started select a stack to manage on the left.</p>
    </section>
  </ContentWrapper>
);

export default HomePage;
