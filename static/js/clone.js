$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackName = "none";

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            selectStack(stackName);
        }, false);
    }
})

function selectStack(stackName) {
    $("#stackSelector").text(stackName);
    $("#stackName").text(stackName);

    var baseUrl = window.location .protocol + "//" + window.location.host;
    var env = 'prod';

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + env + "/" + stackName, true);
    stackParamsRequest.setRequestHeader("Content-Type", "text/xml");
    stackParamsRequest.onreadystatechange = function () {
        if (stackParamsRequest.readyState === XMLHttpRequest.DONE && stackParamsRequest.status === 200) {
            params = JSON.parse(stackParamsRequest.responseText);
            params.sort(function(a, b) {
                return a.ParameterKey.localeCompare(b.ParameterKey)});

            var product;

            $("#paramsForm").html("");
            $("#paramsForm").className = "aui long-label";

            var fieldset = document.createElement("FIELDSET");
            fieldset.id = "fieldSet";

            var stackNameParam = {
                "ParameterKey": "StackName",
                "ParameterValue": ""
            };
            createInputParameter(stackNameParam, fieldset);

            for (var param in params) {
                createInputParameter(params[param], fieldset);
                if (params[param].ParameterKey == "ConfluenceVersion") {
                    product = "Confluence";
                }
            }

            var paramsForm = document.getElementById("paramsForm");
            paramsForm.appendChild(fieldset);

            document.getElementById("CatalinaOptsVal").value += "-Datlassian.mail.senddisabled=true " +
                "-Datlassian.mail.fetchdisabled=true " +
                "-Datlassian.mail.popdisabled=true";
            if (product == "Confluence") {
                document.getElementById("CatalinaOptsVal").value += " -Dconfluence.disable.mailpolling=true";
            }
        }
    };
    stackParamsRequest.send();

    function createInputParameter(param, fieldset) {
        var div = document.createElement("DIV");
        div.className = "field-group";
        div.id = "fieldGroup";

        var label = document.createElement("LABEL");
        label.htmlFor = param.ParameterKey + "Val";
        label.innerHTML = param.ParameterKey;
        div.appendChild(label);

        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;
        div.appendChild(input);

        fieldset.appendChild(div);
    }
}