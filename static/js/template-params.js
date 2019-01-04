var origParams;
var stack_name;
var externalSubnets;
var internalSubnets;

function readyTheTemplate() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            stack_name = data.target.text;
            $("#aui-message-bar").hide();
            selectStack(stack_name);
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

function getTemplates(template_type) {
    var getTemplatesRequest = new XMLHttpRequest();
    getTemplatesRequest.open("GET", baseUrl + "/getTemplates/" + template_type, true);
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
                var text = document.createTextNode(templates[template][0] + ": " + templates[template][1]);
                anchor.appendChild(text);
                li.appendChild(anchor);
                templateDropdown.appendChild(li);
            }

            var templates = document.getElementsByClassName("selectTemplateOption");
            for(var i = 0; i < templates.length; i++) {
                templates[i].addEventListener("click", function (data) {
                    var selectedTemplate = data.target.text;
                    $("#templateSelector").text(selectedTemplate);
                    if (action === 'create')
                        getTemplateParams(selectedTemplate);
                    else
                        selectTemplateForStack(stack_name, selectedTemplate);
                }, false);
            }
        }
    };
    getTemplatesRequest.send();
}

function getTemplateParams(template) {
    $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");
    $("#stack-name-input").hide();

    var repo = template.split(": ")[0];
    var template_name = template.split(": ")[1];

    var templateParamsRequest = new XMLHttpRequest();
    templateParamsRequest.open("GET", baseUrl + "/templateParams/" + repo + "/" + template_name, true);
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

function selectTemplateForStack(stackToRetrieve, templateName) {
    if (document.getElementById("clone-params"))
        $("#clone-params").hide();
    $("#paramsList").html("<aui-spinner size=\"large\"></aui-spinner>");

    $("#stackSelector").text(stackToRetrieve);
    $("#stackName").text(stackToRetrieve);

    if (action == 'clone') {
        getEbsSnapshots($("#regionSelector").text().trim(), stackToRetrieve);
        getRdsSnapshots($("#regionSelector").text().trim(), stackToRetrieve);
    }

    var stackParamsRequest = new XMLHttpRequest();
    stackParamsRequest.open("GET", baseUrl  + "/stackParams/" + region + "/" + stackToRetrieve + "/" + templateName, true);
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
            // Store subnets on update
            } else if (action === 'update') {
                for (var param in origParams) {
                    if (origParams[param].ParameterKey === "ExternalSubnets")
                        externalSubnets = origParams[param].ParameterValue.split(",");
                    else if (origParams[param].ParameterKey === "InternalSubnets")
                        internalSubnets = origParams[param].ParameterValue.split(",");
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
            getVPCs($("#regionSelector").text().trim(), div);
        else
            getVPCs(region, div, param.ParameterValue);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;

        if ((action === 'clone' || action === 'create')
            && (param.ParameterKey === "DBMasterUserPassword" || param.ParameterKey === "DBPassword")) {
            input.setAttribute("data-aui-validation-field", "");
            input.type = "password";
            input.value = "";
            input.required = true;
        } else if (param.ParameterKey === "KeyName" && ssh_key_name !== "") {
            input.value = ssh_key_name;
        } else if (param.ParameterKey === "HostedZone" && hosted_zone !== "") {
            input.value = hosted_zone;
        }
        div.appendChild(input);
    }
    if (param.ParameterDescription) {
        var description = document.createElement("DIV");
        description.className = "description";
        description.innerText = param.ParameterDescription;
        div.appendChild(description);
    }
    fieldset.appendChild(div);
}

function getEbsSnapshots(clone_region, stackToRetrieve) {
    var ebsSnapDropdown = document.getElementById("ebsSnapshots");
    while (ebsSnapDropdown.firstChild) {
        ebsSnapDropdown.removeChild(ebsSnapDropdown.firstChild);
    }

    var ebsSnapshotRequest = new XMLHttpRequest();
    ebsSnapshotRequest.open("GET", baseUrl + "/getEbsSnapshots/" + clone_region + "/" + stackToRetrieve, true);
    ebsSnapshotRequest.setRequestHeader("Content-Type", "text/xml");
    ebsSnapshotRequest.onreadystatechange = function () {
        if (ebsSnapshotRequest.readyState === XMLHttpRequest.DONE && ebsSnapshotRequest.status === 200) {
            var ebsSnaps = JSON.parse(ebsSnapshotRequest.responseText);
            for (var snap in ebsSnaps) {
                var li = document.createElement("LI");
                var anchor = document.createElement("A");
                anchor.className = "selectEbsSnapshotOption";
                var text = document.createTextNode(ebsSnaps[snap]);
                anchor.appendChild(text);
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

function getRdsSnapshots(clone_region, stackToRetrieve) {
    var rdsSnapDropdown = document.getElementById("rdsSnapshots");
    while (rdsSnapDropdown.firstChild) {
        rdsSnapDropdown.removeChild(rdsSnapDropdown.firstChild);
    }

    var rdsSnapshotRequest = new XMLHttpRequest();
    rdsSnapshotRequest.open("GET", baseUrl + "/getRdsSnapshots/" + clone_region + "/" + stackToRetrieve, true);
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

function getVPCs(vpc_region, div, existingVpc) {
    if (document.getElementById("VPCVal"))
        div.removeChild(document.getElementById("VPCVal"));
    if (document.getElementById("VPCDropdownDiv"))
        div.removeChild(document.getElementById("VPCDropdownDiv"));

    var vpcsRequest = new XMLHttpRequest();
    vpcsRequest.open("GET", baseUrl + "/getVpcs/" + vpc_region, true);
    vpcsRequest.setRequestHeader("Content-Type", "text/xml");
    vpcsRequest.onreadystatechange = function () {
        if (vpcsRequest.readyState === XMLHttpRequest.DONE && vpcsRequest.status === 200) {
            var vpcs = JSON.parse(vpcsRequest.responseText);

            // Set default VPC and subnets for region
            var defaultVpc = "";
            if (vpc_region === 'us-west-2' && us_west_2_default_vpc !== "")
                defaultVpc = us_west_2_default_vpc;
            else if (vpc_region === 'us-east-1' && us_east_1_default_vpc !== "")
                defaultVpc = us_east_1_default_vpc;
            if (existingVpc)
                defaultVpc = existingVpc;
            createDropdown("VPC", defaultVpc, vpcs, div);
            getSubnets(vpc_region, defaultVpc, false);
        }
    };
    vpcsRequest.send();
}

function getSubnets(subnets_region, vpc, updateList) {
    var subnetsRequest = new XMLHttpRequest();
    if (vpc !== "")
        subnetsRequest.open("GET", baseUrl + "/getSubnetsForVpc/" + subnets_region + "/" + vpc, true);
    else
        subnetsRequest.open("GET", baseUrl + "/getAllSubnetsForRegion/" + subnets_region, true);
    subnetsRequest.setRequestHeader("Content-Type", "text/xml");
    subnetsRequest.onreadystatechange = function () {
        if (subnetsRequest.readyState === XMLHttpRequest.DONE && subnetsRequest.status === 200) {
            var subnets = JSON.parse(subnetsRequest.responseText);
            if (updateList) {
                updateMultiSelect("ExternalSubnets", "", subnets);
                updateMultiSelect("InternalSubnets", "", subnets);
            } else {
                createMultiSelect("ExternalSubnets", "", subnets, document.getElementById("ExternalSubnetsDiv"));
                createMultiSelect("InternalSubnets", "", subnets, document.getElementById("InternalSubnetsDiv"));
            }
            if (action === "update") {
                $("#ExternalSubnetsVal").val(externalSubnets);
                $("#InternalSubnetsVal").val(internalSubnets);
            }
            else if (action === 'clone') {
                selectDefaultSubnets($("#regionSelector").text().trim())
            } else {
                selectDefaultSubnets(region);
            }
        }
    };
    subnetsRequest.send();
}

function selectDefaultSubnets(subnets_region) {
    // get defaults for regions
    if (subnets_region === 'us-west-2' && us_west_2_default_subnets !== "") { //TODO get default subnets betterer
        $("#ExternalSubnetsVal").val(us_west_2_default_subnets.split(","));
        $("#InternalSubnetsVal").val(us_west_2_default_subnets.split(","));
    } else if (subnets_region === 'us-east-1' && us_east_1_default_subnets !== "") {
        $("#ExternalSubnetsVal").val(us_east_1_default_subnets.split(","));
        $("#InternalSubnetsVal").val(us_east_1_default_subnets.split(","));
    }
}

function sendParamsAsJson() {
    var newParamsArray = [];
    var templateNameParam = {};
    var stackNameForAction = "";
    var newParams = document.getElementsByClassName("field-group");

    if (action === 'update') {
        // Add stack name to params
        var stackNameParam = {};
        stackNameParam["ParameterKey"] = "StackName";
        stackNameParam["ParameterValue"] = $("#stackSelector").text();
        stackNameForAction = $("#stackSelector").text();
        newParamsArray.push(stackNameParam);
    } else {
        stackNameForAction = document.getElementById("StackNameVal").value
    }

    // add cloned_from stackname
    if (action === 'clone') {
        var clonedFromStackParam = {};
        clonedFromStackParam["ParameterKey"] = "ClonedFromStackName";
        clonedFromStackParam["ParameterValue"] = $("#stackSelector").text();
        newParamsArray.push(clonedFromStackParam);
    }

    if ($("#templateSelector").is(':visible')) {
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
            if (action === 'clone')
                value = $("#regionSelector").text().trim();
            else
                value = region;
        } else {
            var element = document.getElementById(param + "Val");
            if (element.tagName.toLowerCase() === "a") {
                value = element.text;
            } else if (element.tagName.toLowerCase() === "input") {
                value = element.value;
            } else if (element.tagName.toLowerCase() === "select") {
                value = "";
                var selections = $("#" + param + "Val").val();
                for (var selection in selections) {
                    value = value + selections[selection];
                    if (selection < selections.length - 1) {
                        value = value + ","
                    }
                }
            }
        }
        jsonParam["ParameterKey"] = param;
        jsonParam["ParameterValue"] = value;
        newParamsArray.push(jsonParam);
    }
    var xhr = new XMLHttpRequest();
    if (action === 'update')
        xhr.open("POST", baseUrl + "/do" + action + "/" + stackNameForAction, true);
    else
        xhr.open("POST", baseUrl + "/do" + action, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');

    // send the collected data as JSON
    var jsonArray = [];
    jsonArray.push(newParamsArray);
    jsonArray.push(origParams);
    xhr.send(JSON.stringify(jsonArray));

    var appendRegion = "";
    if (action === 'clone')
        appendRegion = "&region=" + $("#regionSelector").text().trim();

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stackNameForAction + appendRegion;
    }, 1000);
}
