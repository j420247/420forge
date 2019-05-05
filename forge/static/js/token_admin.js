function onReady() {
  $('#stackInformation')
    .parent()
    .hide();
  $('#action-button').hide();
  $('#stackSelector').hide();
  $('#tokenDisplayMessage').hide();

  let createTokenButton = document.getElementById('createTokenButton');
  createTokenButton.addEventListener('click', createToken);
}

function createToken() {
  send_http_post_request(baseUrl + '/createToken/token_auth', {}, displayToken);
}

function displayToken(responseText) {
  let token = JSON.parse(responseText);
  $('#tokenContent').html(token);
  $('#tokenDisplayMessage').show();
}
