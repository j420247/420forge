function onReady() {
    readyTheTemplate();
    $("#stack-name-input").hide();
    var products = document.getElementsByClassName("selectProductOption");
    for (var i = 0; i < products.length; i++) {
        products[i].addEventListener("click", function (data) {
            var product = data.target.text;
            $("#productSelector").text(product);
            getTemplates(product);
            resetForm();
        }, false);
    }
}

function getTemplates(product) {
    var getTemplatesRequest = new XMLHttpRequest();
    getTemplatesRequest.open("GET", baseUrl + "/getTemplates/" + product, true);
    getTemplatesRequest.setRequestHeader("Content-Type", "text/xml");
    getTemplatesRequest.onreadystatechange = function () {
        if (getTemplatesRequest.readyState === XMLHttpRequest.DONE && getTemplatesRequest.status === 200) {
            var templateDropdown = document.getElementById("templates");
            while (templateDropdown.firstChild) {
                templateDropdown.removeChild(templateDropdown.firstChild);
            }

            var templates = JSON.parse(getTemplatesRequest.responseText);
            for (var template in templates) {
                var li = document.createElement("LI");
                var anchor = document.createElement("A");
                anchor.className = "selectTemplateOption";
                var text = document.createTextNode(templates[template]);
                anchor.appendChild(text);
                li.appendChild(anchor);
                templateDropdown.appendChild(li);
            }

            var templates = document.getElementsByClassName("selectTemplateOption");
            for(var i = 0; i < templates.length; i++) {
                templates[i].addEventListener("click", function (data) {
                    var selectedTemplate = data.target.text;
                    $("#templateSelector").text(selectedTemplate);
                    getTemplate(selectedTemplate);
                }, false);
            }
        }
    };
    getTemplatesRequest.send();
}

function getTemplate(template) {
    $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");
    $("#stack-name-input").hide();

    var templateParamsRequest = new XMLHttpRequest();
    templateParamsRequest.open("GET", baseUrl + "/templateParams/" + template, true);
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
            $("#stack-name-input").show();
            $("#action-button").attr("aria-disabled", false);
        }
    };
    templateParamsRequest.send();
}

function resetForm() {
    $("#templateSelector").text('Select Template');
    $("#stack-name-input").hide();
    $("#paramsList").html("");
    $("#action-button").attr("aria-disabled", true);
}
