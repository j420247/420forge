var origParams;
var stack_name;

function readyTheTemplate() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stack_name = data.target.text;
            $("#aui-message-bar").hide();
            selectStack(stack_name);
            selectTemplateForStack(stack_name);
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
}

function onReady() {
    readyTheTemplate();
}

function selectTemplateForStack(stackToRetrieve) {
    if (document.getElementById("clone-params"))
        $("#clone-params").hide();
    $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");

    $("#stackSelector").text(stackToRetrieve);
    $("#stackName").text(stackToRetrieve);

    if (action == 'clone') {
        getEbsSnapshots(document.getElementById("regionSelector").innerText.trim(), stackToRetrieve);
        getRdsSnapshots(document.getElementById("regionSelector").innerText.trim(), stackToRetrieve);
    }

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + region + "/" + stackToRetrieve, true);
    stackParamsRequest.setRequestHeader("Content-Type", "text/xml");
    stackParamsRequest.onreadystatechange = function () {
        if (stackParamsRequest.readyState === XMLHttpRequest.DONE && stackParamsRequest.status === 200) {
            var product;
            origParams = JSON.parse(stackParamsRequest.responseText);
            if (origParams === 'tag-error') {
                $("#paramsList").html("");
                $("#flash-messages").html
                ("<div class=\"aui-message aui-message-error\" id=\"aui-message-bar\">\n" +
                    "    <ul style=\"list-style-type: none;\">\n" +
                    "        <li>Stack " + stack_name + " is not tagged with 'product' and/or 'environment', cannot determine template to use</li>\n" +
                    "    </ul>\n" +
                    "</div>");
                return;
            }

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
            if (document.getElementById("clone-params"))
                $("#clone-params").show();
            $("#paramsForm").show();
            $("#action-button").attr("aria-disabled", false);
        }
    };
    stackParamsRequest.send();
}

function createInputParameter(param, fieldset) {
    var div = document.createElement("DIV");
    div.className = "field-group";
    div.id = param.ParameterKey + "Div";
    div.name = "parameter";

    var label = document.createElement("LABEL");
    label.htmlFor = param.ParameterKey + "Val";
    label.innerHTML = param.ParameterKey;
    div.appendChild(label);

    if (param.AllowedValues) {
        createDropdown(param.ParameterKey, param.ParameterValue, param['AllowedValues'], div);
    } else if (param.ParameterKey === "VPC") {
        if (action === 'clone')
            region = document.getElementById("regionSelector").innerText.trim();
        getVPCs(region, div);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;

        if ((action === 'clone' || action === 'create')
            && (param.ParameterKey === "DBMasterUserPassword" || param.ParameterKey === "DBPassword")) {
            input.setAttribute("data-aui-validation-field","");
            input.type="password";
            input.value = "";
            input.required = true;
        } else if (param.ParameterKey === "KeyName") {
            input.setAttribute("data-aui-validation-field","");
            input.value = ssh_key_name;
            input.required = true;
        } else if (param.ParameterKey === "HostedZone") {
            input.value = hosted_zone;
        }
        div.appendChild(input);
    }
    fieldset.appendChild(div);
}

function getEbsSnapshots(region, stackToRetrieve) {
    var ebsSnapDropdown = document.getElementById("ebsSnapshots");
    while (ebsSnapDropdown.firstChild) {
        ebsSnapDropdown.removeChild(ebsSnapDropdown.firstChild);
    }

    var ebsSnapshotRequest = new XMLHttpRequest();
    ebsSnapshotRequest.open("GET", baseUrl + "/getEbsSnapshots/" + region + "/" + stackToRetrieve, true);
    ebsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    ebsSnapshotRequest.onreadystatechange = function () {
        if (ebsSnapshotRequest.readyState === XMLHttpRequest.DONE && ebsSnapshotRequest.status === 200) {
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

function getRdsSnapshots(region, stackToRetrieve) {
    var rdsSnapDropdown = document.getElementById("rdsSnapshots");
    while (rdsSnapDropdown.firstChild) {
        rdsSnapDropdown.removeChild(rdsSnapDropdown.firstChild);
    }

    var rdsSnapshotRequest = new XMLHttpRequest();
    rdsSnapshotRequest.open("GET", baseUrl + "/getRdsSnapshots/" + region + "/" + stackToRetrieve, true);
    rdsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    rdsSnapshotRequest.onreadystatechange = function () {
        if (rdsSnapshotRequest.readyState === XMLHttpRequest.DONE && rdsSnapshotRequest.status === 200) {
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

function getVPCs(region, div) {
    if (document.getElementById("VPCVal"))
        div.removeChild(document.getElementById("VPCVal"));
    if (document.getElementById("VPCDropdownDiv"))
        div.removeChild(document.getElementById("VPCDropdownDiv"));

    var vpcsRequest = new XMLHttpRequest();
    vpcsRequest.open("GET", baseUrl + "/getVpcs/" + region, true);
    vpcsRequest.setRequestHeader("Content-Type", "text/xml");
    vpcsRequest.onreadystatechange = function () {
        if (vpcsRequest.readyState === XMLHttpRequest.DONE && vpcsRequest.status === 200) {
            var vpcs = JSON.parse(vpcsRequest.responseText);

            // Set default VPC and subnets for region
            var defaultVpc = "";
            if (region === 'us-west-2')
                defaultVpc = us_west_2_default_vpc;
            else
                defaultVpc = us_east_1_default_vpc;
            createDropdown("VPC", defaultVpc, vpcs, div);
            setSubnets(region);
        }
    };
    vpcsRequest.send();
}

function setSubnets(region) {
    if (region === 'us-west-2') { //TODO get default subnets betterer
        document.getElementById("ExternalSubnetsVal").value = us_west_2_default_subnets;
        document.getElementById("InternalSubnetsVal").value = us_west_2_default_subnets;
    } else {
        document.getElementById("ExternalSubnetsVal").value = us_east_1_default_subnets;
        document.getElementById("InternalSubnetsVal").value = us_east_1_default_subnets;
    }
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
        } else if (param == "Region") {
            value = document.getElementById("regionSelector").innerText;
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
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stackNameForAction;
    }, 1000);
}
