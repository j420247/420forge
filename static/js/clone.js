$(document).unbind('ready');

$(document).ready(function() {
    $("#paramsForm").hide();
    var stacks = document.getElementsByClassName("selectStackOption");
    var stackName = "none";

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stackName = data.target.text;
            selectStack(stackName);
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        sendParamsAsJson();
    });
});

function selectStack(stackName) {
    $("#stackSelector").text(stackName);
    $("#stackName").text(stackName);
    $("#paramsForm").show();

    getEbsSnapshots(baseUrl, stackName);
    getRdsSnapshots(baseUrl, stackName);

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/prod/" + stackName, true);
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

    var input = document.createElement("INPUT");
    input.className = "text";
    input.id = param.ParameterKey + "Val";
    input.value = param.ParameterValue;
    div.appendChild(input);

    fieldset.appendChild(div);
}

function getEbsSnapshots(baseUrl, stackName) {
    var ebsSnapshotRequest = new XMLHttpRequest();
    ebsSnapshotRequest.open("GET", baseUrl + "/getEbsSnapshots/" + stackName, true);
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

function getRdsSnapshots(baseUrl, stackName) {
    var rdsSnapshotRequest = new XMLHttpRequest();
    rdsSnapshotRequest.open("GET", baseUrl + "/getRdsSnapshots/" + stackName, true);
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
    // collect the form data while iterating over the inputs
    var paramsArray = [];
    var params = document.getElementsByClassName("field-group");

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
    xhr.open("POST", baseUrl + "/clone", true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');

    // send the collected data as JSON
    xhr.send(JSON.stringify(paramsArray));

    // Redirect to action progress screen
    window.location = baseUrl + "/actionprogress/clone/" + document.getElementById("stacknameVal").value;
}