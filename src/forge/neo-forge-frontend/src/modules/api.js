const FORGE_API_URL = 'http://localhost:8000';

const getTemplateParamsForTemplate = (templateRepo, templateName) => {
  return fetch(`${FORGE_API_URL}/templateParams/${templateRepo}/${templateName}`)
  .then(res => res.json())
};

const cloneStack = (templateParameters) => {
  return fetch(`${FORGE_API_URL}/doClone`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(templateParameters)
  })
  .then(res => res.json);
}

export default {
  getTemplateParamsForTemplate,
  cloneStack
};