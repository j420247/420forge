const FORGE_API_URL = 'http://localhost:8000';

const getTemplateParamsForTemplate = (templateRepo, templateName) => {
  return fetch(`${FORGE_API_URL}/templateParams/${templateRepo}/${templateName}`)
  .then(res => res.json())
};

export {
  getTemplateParamsForTemplate
};