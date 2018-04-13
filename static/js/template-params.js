$(document).unbind('ready');

$(document).ready(function() {
    $("#paramsForm").hide();
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            selectTemplateForStack(data.target.text);
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        $("#paramsForm").submit();
    });

    AJS.$('#paramsForm').on('aui-valid-submit', function(event) {
        sendParamsAsJson();
        event.preventDefault();
    });
});

function selectTemplateForStack(stackToRetrieve) {
    $("#stackSelector").text(stackToRetrieve);
    $("#stackName").text(stackToRetrieve);

    if (action == 'clone') {
        getEbsSnapshots(baseUrl, stackToRetrieve);
        getRdsSnapshots(baseUrl, stackToRetrieve);
    } else{
        $('meta[name=stack_name]').attr('value', stackToRetrieve);
    }

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + env + "/" + stackToRetrieve, true);
    stackParamsRequest.setRequestHeader("Content-Type", "text/xml");
    stackParamsRequest.onreadystatechange = function () {
        if (stackParamsRequest.readyState === XMLHttpRequest.DONE && stackParamsRequest.status === 200) {
            var product;
            origParams = JSON.parse(stackParamsRequest.responseText);
            origParams.sort(function(a, b) {
                return a.ParameterKey.localeCompare(b.ParameterKey)});

            $("#paramsList").html("");
            var fieldset = document.createElement("FIELDSET");
            fieldset.id = "fieldSet";

            for (var param in origParams) {
                createInputParameter(origParams[param], fieldset);
                if (origParams[param].ParameterKey === "ConfluenceVersion") {
                    product = "Confluence";
                }
            }

            var paramsList = document.getElementById("paramsList");
            paramsList.appendChild(fieldset);

            // Disable mail by default on clones
            if (action === 'clone') {
                var commonMailDisableParams = "-Datlassian.mail.senddisabled=true " +
                    "-Datlassian.mail.fetchdisabled=true " +
                    "-Datlassian.mail.popdisabled=true";
                var confluenceMailDisableParams = " -Dconfluence.disable.mailpolling=true";
                if (document.getElementById("CatalinaOptsVal").value.indexOf(commonMailDisableParams) === -1) {
                    document.getElementById("CatalinaOptsVal").value += " " + commonMailDisableParams;
                }
                if (product == "Confluence") {
                    if (document.getElementById("CatalinaOptsVal").value.indexOf(confluenceMailDisableParams) === -1) {
                        document.getElementById("CatalinaOptsVal").value += " " + confluenceMailDisableParams;
                    }
                }
            }
            $("#paramsForm").show();
            $("#action-button").attr("aria-disabled", false);
        }
    };
    stackParamsRequest.send();
}

function createInputParameter(param, fieldset) {
    var div = document.createElement("DIV");
    div.className = "field-group";
    div.name = "parameter";

    var label = document.createElement("LABEL");
    label.htmlFor = param.ParameterKey + "Val";
    label.innerHTML = param.ParameterKey;
    div.appendChild(label);

    if (param.AllowedValues) {
        var dropdownAnchor = document.createElement("A");
        dropdownAnchor.className = "aui-button aui-style-default aui-dropdown2-trigger";
        dropdownAnchor.setAttribute("aria-owns", param.ParameterKey + "Dropdown");
        dropdownAnchor.setAttribute("aria-haspopup", "true");
        dropdownAnchor.setAttribute("href", "#" + param.ParameterKey + "Dropdown");
        dropdownAnchor.id = param.ParameterKey + "Val";

        var dropdownDiv = document.createElement("DIV");
        dropdownDiv.id = param.ParameterKey + "Dropdown";
        dropdownDiv.className = "aui-style-default aui-dropdown2";

        var ul = document.createElement("UL");
        ul.className = "aui-list-truncate";

        for (var allowedValue in param['AllowedValues']) {
            var li = document.createElement("LI");
            var liAnchor = document.createElement("A");
            var text = document.createTextNode(param['AllowedValues'][allowedValue]);
            liAnchor.appendChild(text);
            liAnchor.addEventListener("click", function (data) {
                dropdownAnchor.text = data.target.text;
                if (dropdownAnchor.id === "TomcatSchemeVal") {
                    if (data.target.text === "https") {
                        document.getElementById("TomcatProxyPortVal").value = "443";
                        document.getElementById("TomcatSecureVal").value = "true";
                    }
                    else if (data.target.text === "http") {
                        document.getElementById("TomcatProxyPortVal").value = "80";
                        document.getElementById("TomcatSecureVal").value = "false";
                    }
                }
            }, false);
            li.appendChild(liAnchor);
            ul.appendChild(li);
        }
        if (param.ParameterValue.length !== 0)
            dropdownAnchor.text = param.ParameterValue;
        else
            dropdownAnchor.text = 'Select';

        div.appendChild(dropdownAnchor);
        dropdownDiv.appendChild(ul);
        div.appendChild(dropdownDiv);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";

        // Set VPC and subnets for env
        if (param.ParameterKey === "VPC") {
            if (env === 'stg')
                input.value = "vpc-320c1355";
            else
                input.value = "vpc-dd8dc7ba";
        } else if (param.ParameterKey === "InternalSubnets" || param.ParameterKey === "ExternalSubnets") {
            if (env === 'stg')
                input.value = "subnet-df0c3597,subnet-f1fb87ab";
            else
                input.value = "subnet-eb952fa2,subnet-f2bddd95"
        } else {
            input.value = param.ParameterValue;
        }

        if (action === 'clone' && (param.ParameterKey === "DBMasterUserPassword" || param.ParameterKey === "DBPassword")) {
            input.setAttribute("data-aui-validation-field","");
            input.value = "";
            input.required = true;
        }
        div.appendChild(input);
    }
    fieldset.appendChild(div);
}

function getEbsSnapshots(baseUrl, stackToRetrieve) {
    var ebsSnapshotRequest = new XMLHttpRequest();
    ebsSnapshotRequest.open("GET", baseUrl + "/getEbsSnapshots/" + stackToRetrieve, true);
    ebsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    ebsSnapshotRequest.onreadystatechange = function () {
        if (ebsSnapshotRequest.readyState === XMLHttpRequest.DONE && ebsSnapshotRequest.status === 200) {
            var ebsSnapDropdown = document.getElementById("ebsSnapshots");
            while (ebsSnapDropdown.firstChild) {
                ebsSnapDropdown.removeChild(ebsSnapDropdown.firstChild);
            }

            var ebsSnaps = JSON.parse(ebsSnapshotRequest.responseText);
            for (var snap in ebsSnaps) {
                var li = document.createElement("LI");
                var anchor = document.createElement("A");
                anchor.className = "selectEbsSnapshotOption";
                var text = document.createTextNode(ebsSnaps[snap]);
                anchor.appendChild(text)
                li.appendChild(anchor);
                ebsSnapDropdown.appendChild(li);
            }

            var ebsSnaps = document.getElementsByClassName("selectEbsSnapshotOption");
            for (var i = 0; i < ebsSnaps.length; i++) {
                ebsSnaps[i].addEventListener("click", function (data) {
                    $("#ebsSnapshotSelector").text(data.target.text);
                }, false);
            }
        }
    };
    ebsSnapshotRequest.send();
}

function getRdsSnapshots(baseUrl, stackToRetrieve) {
    var rdsSnapshotRequest = new XMLHttpRequest();
    rdsSnapshotRequest.open("GET", baseUrl + "/getRdsSnapshots/" + stackToRetrieve, true);
    rdsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    rdsSnapshotRequest.onreadystatechange = function () {
        if (rdsSnapshotRequest.readyState === XMLHttpRequest.DONE && rdsSnapshotRequest.status === 200) {
            var rdsSnapDropdown = document.getElementById("rdsSnapshots");
            while (rdsSnapDropdown.firstChild) {
                rdsSnapDropdown.removeChild(rdsSnapDropdown.firstChild);
            }

            var rdsSnaps = JSON.parse(rdsSnapshotRequest.responseText);
            for (var snap in rdsSnaps) {
                var li = document.createElement("LI");
                var anchor = document.createElement("A");
                anchor.className = "selectRdsSnapshotOption";
                var text = document.createTextNode(rdsSnaps[snap]);
                anchor.appendChild(text);
                li.appendChild(anchor);
                rdsSnapDropdown.appendChild(li);
            }

            var rdsSnaps = document.getElementsByClassName("selectRdsSnapshotOption");
            for (var i = 0; i < rdsSnaps.length; i++) {
                rdsSnaps[i].addEventListener("click", function (data) {
                    $("#rdsSnapshotSelector").text(data.target.text);
                }, false);
            }
        }
    };
    rdsSnapshotRequest.send();
}

function sendParamsAsJson() {
    var newParamsArray = [];
    var stackNameParam = {};
    var templateNameParam = {};
    var stackNameForAction = "";
    var newParams = document.getElementsByClassName("field-group");

    if (action === 'update') {
        // Add stack name to params
        stackNameParam["ParameterKey"] = "StackName";
        stackNameParam["ParameterValue"] = $("#stackSelector").text();
        stackNameForAction = $("#stackSelector").text();
        newParamsArray.push(stackNameParam);
    } else {
        stackNameForAction = document.getElementById("StackNameVal").value
    }

    if (action === 'create') {
        // Add template name to params
        templateNameParam["ParameterKey"] = "TemplateName";
        templateNameParam["ParameterValue"] = $("#templateSelector").text();
        newParamsArray.push(templateNameParam);
    }

    for(var i = 0; i < newParams.length; i++) {
        var jsonParam = {};
        var param = newParams.item(i).getElementsByTagName("LABEL")[0].innerHTML;
        var value;

        if (param == "EBSSnapshotId") {
            if (action === 'clone')
                value = document.getElementById("ebsSnapshotSelector").innerText;
            else
                value = document.getElementById("EBSSnapshotIdVal").value;
        } else if (param == "DBSnapshotName") {
            if (action === 'clone')
                value = document.getElementById("rdsSnapshotSelector").innerText;
            else
                value = document.getElementById("DBSnapshotNameVal").value;
        } else {
            var element = document.getElementById(param + "Val");
            if (element.tagName.toLowerCase() === "a") {
                value = element.text;
            } else if (element.tagName.toLowerCase() === "input") {
                value = element.value;
            }
        }

        jsonParam["ParameterKey"] = param;
        jsonParam["ParameterValue"] = value;
        newParamsArray.push(jsonParam);
    }
    // construct an HTTP request
    var xhr = new XMLHttpRequest();
    xhr.open("POST", baseUrl + "/do" + action, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');

    // send the collected data as JSON
    var jsonArray = [];
    jsonArray.push(newParamsArray);
    jsonArray.push(origParams);
    xhr.send(JSON.stringify(jsonArray));

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stackNameForAction;
    }, 1000);
}