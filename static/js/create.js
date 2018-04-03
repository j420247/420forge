$(document).ready(function() {
    var products = document.getElementsByClassName("selectProductOption");
    for (var i = 0; i < products.length; i++) {
        products[i].addEventListener("click", function (data) {
            var product = data.target.text;
            $("#productSelector").text(product);

            var templates = document.getElementsByClassName("selectTemplateOption");
            for(var i = 0; i < templates.length + 1; i++) {
                debugger;
                if (templates[i].text.toLowerCase().indexOf(product.toLowerCase()) > -1) {
                    templates[i].removeAttribute("style");
                    templates[i].addEventListener("click", function (data) {
                        var selectedTemplate = data.target.text;
                        $("#templateSelector").text = selectedTemplate;
                        getTemplate(selectedTemplate);
                    }, false);
                }
                else {
                    templates[i].style.display = "none";
                }
            }
        }, false);
    }
});

function getTemplate(template) {
    var templateParamsRequest = new XMLHttpRequest();
    templateParamsRequest.open("GET", baseUrl + "/templateParams/" + templateName, true);
    templateParamsRequest.setRequestHeader("Content-Type", "text/xml");
    templateParamsRequest.onreadystatechange = function () {
        if (templateParamsRequest.readyState === XMLHttpRequest.DONE && templateParamsRequest.status === 200) {
            var product;
            origParams = JSON.parse(templateParamsRequest.responseText);
            origParams.sort(function (a, b) {
                return a.ParameterKey.localeCompare(b.ParameterKey)
            });

            $("#paramsList").html("");
            var fieldset = document.createElement("FIELDSET");
            fieldset.id = "fieldSet";

            for (var param in origParams)
                createInputParameter(origParams[param], fieldset);

            var paramsList = document.getElementById("paramsList");
            paramsList.appendChild(fieldset);
            $("#paramsForm").show();
            $("#action-button").attr("aria-disabled", false);
        }
    };
    templateParamsRequest.send();
}