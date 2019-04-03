function onReady() {
  readyTheTemplate();
  $("#stack-name-input").hide();
  var products = document.getElementsByClassName("selectProductOption");
  for (var i = 0; i < products.length; i++) {
    products[i].addEventListener(
      "click",
      function(data) {
        var product = data.target.text;
        $("#productSelector").text(product);
        getTemplates(product);
        resetForm();
      },
      false
    );
  }
}

function resetForm() {
  $("#templateSelector").text("Select Template");
  $("#stack-name-input").hide();
  $("#paramsList").html("");
  $("#action-button").attr("aria-disabled", true);
}
