$(document).unbind('ready');
var action = $("meta[name=action]").attr("value");

$(document).ready(function() {
    $("#paramsForm").hide();
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackToRetrieve = "none";

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stackToRetrieve = data.target.text;
            selectStack(stackToRetrieve);
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        sendParamsAsJson();
    });
});

function selectStack(stackToRetrieve) {
    $("#stackSelector").text(stackToRetrieve);
    $("#stackName").text(stackToRetrieve);

    if (action == 'clone') {
        getEbsSnapshots(baseUrl, stackToRetrieve);
        getRdsSnapshots(baseUrl, stackToRetrieve);
    }

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + env + "/" + stackToRetrieve, true);
    stackParamsRequest.setRequestHeader("Content-Type", "text/xml");
    stackParamsRequest.onreadystatechange = function () {
        if (stackParamsRequest.readyState === XMLHttpRequest.DONE && stackParamsRequest.status === 200) {
            var product;
            params = JSON.parse(stackParamsRequest.responseText);
            params.sort(function(a, b) {
                return a.ParameterKey.localeCompare(b.ParameterKey)});

            $("#paramsList").html("");
            var fieldset = document.createElement("FIELDSET");
            fieldset.id = "fieldSet";

            for (var param in params) {
                createInputParameter(params[param], fieldset);
                if (params[param].ParameterKey == "ConfluenceVersion") {
                    product = "Confluence";
                }
            }

            var paramsList = document.getElementById("paramsList");
            paramsList.appendChild(fieldset);

            document.getElementById("CatalinaOptsVal").value += " -Datlassian.mail.senddisabled=true " +
                "-Datlassian.mail.fetchdisabled=true " +
                "-Datlassian.mail.popdisabled=true";
            if (product == "Confluence") {
                document.getElementById("CatalinaOptsVal").value += " -Dconfluence.disable.mailpolling=true";
            }
            $("#paramsForm").show();
        }
    };
    stackParamsRequest.send();

    $("#action-button").attr("aria-disabled", false);
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
        dropdownAnchor.setAttribute("aria-owns", param.ParameterKey + "Val");
        dropdownAnchor.setAttribute("aria-haspopup", "true");
        dropdownAnchor.setAttribute("href", "#" + param.ParameterKey + "Val");

        var dropdownDiv = document.createElement("DIV");
        dropdownDiv.id = param.ParameterKey + "Val";
        dropdownDiv.className = "aui-style-default aui-dropdown2";

        var ul = document.createElement("UL");
        ul.className = "aui-list-truncate";

        for (var allowedValue in param['AllowedValues']) {
            var li = document.createElement("LI");
            var liAnchor = document.createElement("A");
            console.log(param['AllowedValues'][allowedValue])
            liAnchor.setAttribute("href", "#");
            var text = document.createTextNode(param['AllowedValues'][allowedValue]);
            liAnchor.appendChild(text);
            liAnchor.addEventListener("click", function (data) {
                dropdownAnchor.text = data.target.text;
            }, false);

            li.appendChild(liAnchor);
            ul.appendChild(li);
        }
        if (param.ParameterValue)
            dropdownAnchor.text = param.ParameterValue;

        div.appendChild(dropdownAnchor);
        dropdownDiv.appendChild(ul);
        div.appendChild(dropdownDiv);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;
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
    var paramsArray = [];
    var stackNameParam = {};
    var stackNameForAction = "";
    var params = document.getElementsByClassName("field-group");

    if (action == 'update') {
        // Add stack name and env to params
        stackNameParam["ParameterKey"] = "StackName";
        stackNameParam["ParameterValue"] = $("#stackSelector").text();
        stackNameForAction = $("#stackSelector").text();
        paramsArray.push(stackNameParam);
    } else {
        stackNameForAction = document.getElementById("stacknameVal").value
    }

    for(var i = 0; i < params.length; i++) {
        var jsonParam = {};
        var param = params.item(i).getElementsByTagName("LABEL")[0].innerHTML;
        var value;

        if (param == "EBSSnapshotId") {
            value = document.getElementById("ebsSnapshotSelector").innerText;
        } else if (param == "DBSnapshotName") {
            value = document.getElementById("rdsSnapshotSelector").innerText;
        } else {
            value = params.item(i).getElementsByTagName("INPUT")[0].value;
        }

        if (param != 'EnableBanner' && param != 'EnableTCPForwarding' && param != 'NumBastionHosts' &&
            param != 'BastionAMIOS' && param != 'BastionBanner' && param != 'EnableX11Forwarding' && param != 'BastionInstanceType') {
            jsonParam["ParameterKey"] = param;
            jsonParam["ParameterValue"] = value;
            paramsArray.push(jsonParam);
        }
    }
    // construct an HTTP request
    var xhr = new XMLHttpRequest();
    xhr.open("POST", baseUrl + "/" + action, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');

    // send the collected data as JSON
    xhr.send(JSON.stringify(paramsArray));

    // Redirect to action progress screen
    window.location = baseUrl + "/actionprogress/" + action + "/" + stackNameForAction;
}