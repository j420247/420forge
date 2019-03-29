import FORGE_API_URL from '../config';

const getTemplateParamsForTemplate = (templateRepo, templateName) => {
  return fetch(`${FORGE_API_URL}/templateParams/${templateRepo}/${templateName}`)
  .then(res => res.json())
};

const cloneStack = (templateParameters) => {
  // Api JSON array containing a single element which is an array of { ParameterKey, ParamaterValue } tuples.
  return fetch(`${FORGE_API_URL}/doclone`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify([templateParameters])
  })
  .then(res => res.json());
}

const getStacks = () => {
  return fetch(`${FORGE_API_URL}/getStacks`, {
    method: "GET",
  })
  .then(result => result.json());
}

export default {
  getTemplateParamsForTemplate,
  cloneStack,
  getStacks
};